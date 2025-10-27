from typing import TYPE_CHECKING

from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.responses.content.reasoning import ResponseReasoningContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import TokenUsage
from agent_platform.core.responses.streaming import (
    ReasoningResponseStreamSink,
    StopReasonGuardSink,
    TextResponseStreamSink,
    ToolUseResponseStreamSink,
    UsageResponseStreamSink,
    XmlTagResponseStreamSink,
)
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.utils.partial_json import clean_json_string

if TYPE_CHECKING:
    from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState

logger: BoundLogger = get_logger(__name__)


class ThreadStateSinks:
    """A class that contains the sinks for the message."""

    def __init__(
        self,
        message: "ThreadMessageWithThreadState",
        content_tag: str = "response",
        thoughts_tag: str = "thinking",
        tag_expected_past_response: str | None = "step",
        tag_expected_pre_response: str | None = "thinking",
    ):
        self._message = message
        self._content_tag = content_tag
        self._thoughts_tag = thoughts_tag
        self._tag_expected_past_response = tag_expected_past_response
        self._tag_expected_pre_response = tag_expected_pre_response

    @property
    def content(self) -> XmlTagResponseStreamSink:
        """The sink for the content of the message."""

        async def _append_content(tag: str, content: str) -> None:
            self._message.append_content(content)
            await self._message.stream_delta()

        async def _complete_content(tag: str, content: str) -> None:
            self._message.append_content("", complete=True)
            await self._message.stream_delta()

        return XmlTagResponseStreamSink(
            tag=self._content_tag,
            expected_next_tag=self._tag_expected_past_response,
            expected_preceding_tag=self._tag_expected_pre_response,
            on_tag_partial=_append_content,
            on_tag_complete=_complete_content,
        )

    @property
    def raw_content(self) -> TextResponseStreamSink:
        """The sink for the raw content of the message."""

        async def _append_content(text: str) -> None:
            self._message.append_content(text)
            await self._message.stream_delta()

        async def _complete_content(text: str) -> None:
            self._message.append_content("", complete=True)
            await self._message.stream_delta()

        return TextResponseStreamSink(
            on_text_start=_append_content,
            on_text_partial=_append_content,
            on_text_complete=_complete_content,
        )

    @property
    def reasoning(self) -> ReasoningResponseStreamSink:
        """The sink for the reasoning of the message."""

        async def _append_reasoning(reasoning: str) -> None:
            self._message.append_thought(reasoning)
            await self._message.stream_delta()

        async def _complete_reasoning(
            reasoning: str,
            content: ResponseReasoningContent,
        ) -> None:
            self._message.append_thought(
                reasoning,
                complete=True,
                extras=content.model_dump(),
            )
            await self._message.stream_delta()

        return ReasoningResponseStreamSink(
            on_reasoning_start=_append_reasoning,
            on_reasoning_partial=_append_reasoning,
            on_reasoning_complete=_complete_reasoning,
        )

    @property
    def thoughts(self) -> XmlTagResponseStreamSink:
        """The sink for the thoughts of the message."""

        async def _append_thought(tag: str, content: str) -> None:
            self._message.append_thought(content)
            await self._message.stream_delta()

        async def _complete_thought(tag: str, content: str) -> None:
            self._message.append_thought("", complete=True)
            await self._message.stream_delta()

        return XmlTagResponseStreamSink(
            tag=self._thoughts_tag,
            expected_next_tag=self._content_tag,
            on_tag_partial=_append_thought,
            on_tag_complete=_complete_thought,
        )

    def tool_calls(
        self,
        forward_to_content: str | None = None,
        content_from_key: str | None = None,
    ) -> ToolUseResponseStreamSink:
        """The sink for the tool calls of the message."""

        async def _update_tool_use(
            content: ResponseToolUseContent,
            tool_def: ToolDefinition | None,
        ) -> None:
            self._message.update_tool_use(content, tool_def)
            if tool_def and tool_def.name == forward_to_content:
                forwarded_content = content.tool_input_raw
                if content_from_key:
                    forwarded_content = clean_json_string(forwarded_content, content_from_key)
                self._message.append_content(forwarded_content, incremental=True)

            await self._message.stream_delta()

        async def _update_tool_use_final(
            content: ResponseToolUseContent,
            tool_def: ToolDefinition | None,
        ) -> None:
            self._message.update_tool_use(content, tool_def, completed=True)
            if tool_def and tool_def.name == forward_to_content:
                final_content = (
                    content.tool_input.get(content_from_key, "No reply provided.")
                    if content_from_key
                    else content.tool_input_raw
                )
                self._message.append_content(
                    final_content,
                    overwrite=True,
                    complete=True,
                )

            await self._message.stream_delta()

        return ToolUseResponseStreamSink(
            on_tool_partial=_update_tool_use,
            on_tool_complete=_update_tool_use_final,
        )

    @property
    def usage(self) -> UsageResponseStreamSink:
        """The sink for the usage of the message."""

        async def _append_usage(usage: TokenUsage) -> None:
            if "total_usage" not in self._message.agent_metadata:
                self._message.agent_metadata["total_usage"] = usage.model_dump()
            else:
                try:
                    as_token_usage = TokenUsage.model_validate(
                        self._message.agent_metadata["total_usage"],
                    )
                    self._message.agent_metadata["total_usage"] = (
                        as_token_usage + usage
                    ).model_dump()
                except Exception as ex:
                    logger.warning(
                        f"Failed to add usage to total usage, resetting to new usage: {ex!r}"
                    )
                    self._message.agent_metadata["total_usage"] = usage.model_dump()
            await self._message.stream_delta()

        return UsageResponseStreamSink(
            on_usage_received=_append_usage,
        )

    @property
    def stop_reason_guard(self) -> StopReasonGuardSink:
        """A sink that raises immediately when stop reason == 'max_tokens'."""
        return StopReasonGuardSink()
