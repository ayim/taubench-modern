from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.architectures.experimental.violet.widgets.manager import InlineWidgetManager
from agent_platform.core.kernel import Kernel
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.responses.content import (
    ResponseReasoningContent,
    ResponseTextContent,
)
from agent_platform.core.responses.streaming import ReasoningResponseStreamSink
from agent_platform.core.thread.content import ThreadVegaChartContent

logger = logging.getLogger(__name__)


class WidgetTaskRunner:
    """
    Orchestrates async widget generation tasks (charts).
    """

    def __init__(
        self,
        kernel: Kernel,
        state: VioletState,
        message: ThreadMessageWithThreadState,
        manager: InlineWidgetManager,
        *,
        max_retries: int = 2,
    ) -> None:
        self.kernel = kernel
        self.state = state
        self.message = message
        self.manager = manager
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._max_retries = max_retries

    def spawn_chart_task(self, widget_id: str, description: str) -> None:
        if widget_id in self._tasks:
            return
        task = asyncio.create_task(self._run_chart_task(widget_id, description))
        self._tasks[widget_id] = task

    async def wait_for_all(self) -> None:
        if not self._tasks:
            return
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    def cancel_all(self) -> None:
        for task in self._tasks.values():
            if not task.done():
                task.cancel()

    async def _run_chart_task(  # noqa: C901, PLR0915
        self, widget_id: str, description: str
    ) -> None:
        """
        Run a chart-generation prompt with retries and stream thoughts to metadata.
        """
        from agent_platform.architectures.experimental.violet.widgets.prompts import (
            build_chart_prompt,
        )

        try:
            self.manager.update_status(widget_id, "generating")
            await self.message.stream_delta()

            error_hint: str | None = None
            last_exception: Exception | None = None
            for attempt in range(1, self._max_retries + 1):
                try:
                    platform, model = await self.kernel.get_platform_and_model(
                        model_type="llm",
                        # Charts can be tricky, we'll use codex max
                        direct_model_name="gpt-5-1-codex-max",
                    )
                    prompt = await build_chart_prompt(
                        kernel=self.kernel,
                        state=self.state,
                        description=description,
                        error_hint=error_hint,
                        partial_agent_reply=self.message.get_text_content(),
                    )
                except Exception as exc:  # formatting error; do not retry
                    logger.exception("Failed to format chart prompt: %s", exc)
                    self.manager.set_error(widget_id, "Chart prompt failed to format.")
                    await self.message.stream_delta()
                    return

                async def _append_thinking(reasoning: str) -> None:
                    self.manager.append_thinking(widget_id, reasoning)
                    await self.message.stream_delta()

                async def _complete_thinking(
                    reasoning: str, content: ResponseReasoningContent
                ) -> None:
                    self.manager.append_thinking(widget_id, reasoning)
                    if content.response_id:
                        self.state.ignored_reasoning_ids.append(content.response_id)
                    await self.message.stream_delta()

                reasoning_sink = ReasoningResponseStreamSink(
                    on_reasoning_start=_append_thinking,
                    on_reasoning_partial=_append_thinking,
                    on_reasoning_complete=_complete_thinking,
                )

                try:
                    async with platform.stream_response(prompt, model) as stream:
                        await stream.pipe_to(reasoning_sink)
                    response = stream.reassembled_response
                except Exception as exc:
                    last_exception = exc
                    error_hint = f"Streaming failed ({exc})"
                    logger.warning(
                        "Chart generation attempt %s failed: %s", attempt, exc, exc_info=True
                    )
                    continue

                if not response:
                    error_hint = "Model returned no response"
                    continue

                # Extract text blocks
                text_parts = [
                    c.text for c in response.content if isinstance(c, ResponseTextContent)
                ]
                raw_text = "\n".join(text_parts).strip()
                if not raw_text:
                    error_hint = "Model returned empty text"
                    continue

                chart_content = self._try_parse_chart_spec(raw_text)
                if chart_content is None:
                    error_hint = f"Invalid chart spec (attempt {attempt})"
                    continue

                # Success: append content and finish
                await self.manager.apply_final_chart(
                    widget_id,
                    chart_content,
                    description=description,
                )
                return

            # All attempts failed
            final_error = error_hint or (str(last_exception) if last_exception else "Unknown error")
            self.manager.set_error(widget_id, final_error)
            await self.message.stream_delta()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Chart generation task failed")
            self.manager.set_error(widget_id, "Chart generation failed unexpectedly.")
            await self.message.stream_delta()

    def _try_parse_chart_spec(self, raw_text: str) -> ThreadVegaChartContent | None:
        """
        Attempt to extract and validate a Vega/Vega-Lite spec.
        """
        cleaned = self._strip_code_fences(raw_text)
        try:
            parsed = json.loads(cleaned)
        except Exception:
            return None

        schema = parsed.get("$schema", "")
        sub_type = (
            "vega-lite" if isinstance(schema, str) and "vega-lite" in schema.lower() else "vega"
        )

        try:
            # Let ThreadVegaChartContent validate and normalize.
            return ThreadVegaChartContent(
                chart_spec_raw=json.dumps(parsed),
                sub_type=sub_type,  # type: ignore[arg-type]
            )
        except Exception as exc:
            logger.warning("Chart spec validation failed: %s", exc)
            return None

    async def _append_chart_content(
        self,
        chart: ThreadVegaChartContent,
        *,
        widget_id: str,
        description: str,
    ) -> None:
        """
        Append a chart content item to the in-flight message and stream the delta.
        """
        try:
            widget = self.manager.get_widget(widget_id)
            chart.completed = True
            chart.widget_id = widget_id
            chart.description = description
            if widget:
                chart.status = widget.status
                chart.thinking = widget.thinking
                chart.error = widget.error
            self.message._message.content.append(chart)
            await self.message.stream_delta()
        except Exception:
            logger.exception("Failed to append chart content to message.")
            return

    def _strip_code_fences(self, text: str) -> str:
        if "```" not in text:
            return text
        parts = text.split("```")
        if len(parts) < 2:  # noqa: PLR2004
            return text
        candidate = parts[1]
        if candidate.strip().startswith(("json", "vega", "vega-lite")):
            candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        return candidate.strip()
