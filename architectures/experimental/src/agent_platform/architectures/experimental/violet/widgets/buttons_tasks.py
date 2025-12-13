from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.architectures.experimental.violet.widgets.manager import InlineWidgetManager
from agent_platform.core.kernel import Kernel
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.responses.content import ResponseReasoningContent, ResponseTextContent
from agent_platform.core.responses.streaming import ReasoningResponseStreamSink
from agent_platform.core.thread.content import (
    ThreadQuickActionContent,
    ThreadQuickActionsContent,
)

logger = logging.getLogger(__name__)


class ButtonTaskRunner:
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

    def spawn_buttons_task(self, widget_id: str, description: str) -> None:
        if widget_id in self._tasks:
            return
        task = asyncio.create_task(self._run_buttons_task(widget_id, description))
        self._tasks[widget_id] = task

    async def wait_for_all(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    def cancel_all(self) -> None:
        for task in self._tasks.values():
            if not task.done():
                task.cancel()

    async def _run_buttons_task(self, widget_id: str, description: str) -> None:
        from agent_platform.architectures.experimental.violet.widgets.prompts import (
            build_buttons_prompt,
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
                        # We'll use the weaker gpt-5-mini to drive the buttons task
                        direct_model_name="gpt-5-mini",
                    )
                    prompt = await build_buttons_prompt(
                        kernel=self.kernel,
                        state=self.state,
                        description=description,
                        error_hint=error_hint,
                        partial_agent_reply=self.message.get_text_content(),
                    )
                except Exception as exc:
                    logger.exception("Failed to format buttons prompt: %s", exc)
                    self.manager.set_error(widget_id, "Buttons prompt failed to format.")
                    await self.message.stream_delta()
                    return

                async def _append_thinking(reasoning: str) -> None:
                    self.manager.append_thinking(widget_id, reasoning)
                    await self.message.stream_delta()

                async def _complete_thinking(reasoning: str, content: ResponseReasoningContent) -> None:
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
                    logger.warning("Buttons generation attempt %s failed: %s", attempt, exc, exc_info=True)
                    continue

                if not response:
                    error_hint = "Model returned no response"
                    continue

                text_parts = [c.text for c in response.content if isinstance(c, ResponseTextContent)]
                raw_text = "\n".join(text_parts).strip()
                if not raw_text:
                    error_hint = "Model returned empty text"
                    continue

                content = self._parse_buttons(raw_text)
                if content is None:
                    error_hint = f"Invalid buttons spec (attempt {attempt})"
                    continue

                await self.manager.apply_final_buttons(
                    widget_id,
                    content,
                    description=description,
                )
                return

            final_error = error_hint or (str(last_exception) if last_exception else "Unknown error")
            self.manager.set_error(widget_id, final_error)
            await self.message.stream_delta()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Buttons generation task failed")
            self.manager.set_error(widget_id, "Buttons generation failed unexpectedly.")
            await self.message.stream_delta()

    def _parse_buttons(self, raw_text: str) -> ThreadQuickActionsContent | None:
        cleaned = self._strip_code_fences(raw_text)
        try:
            parsed = json.loads(cleaned)
        except Exception:
            return None

        if not isinstance(parsed, list):
            return None

        actions: list[ThreadQuickActionContent] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("label") or ""
            message = item.get("message") or item.get("value") or ""
            icon = item.get("iconName")
            if not title or not message:
                continue
            actions.append(
                ThreadQuickActionContent(
                    label=str(title),
                    value=str(message),
                    icon=str(icon) if icon else None,
                )
            )

        if not actions:
            return None

        try:
            return ThreadQuickActionsContent(actions=actions, completed=True, status="done")
        except Exception:
            return None

    def _strip_code_fences(self, text: str) -> str:
        if "```" not in text:
            return text
        parts = text.split("```")
        if len(parts) < 2:
            return text
        candidate = parts[1]
        if candidate.strip().startswith(("json", "buttons")):
            candidate = candidate.split("\n", 1)[1] if "\n" in candidate else candidate
        return candidate.strip()
