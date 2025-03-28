from collections.abc import Awaitable, Callable

from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


async def _on_start_noop(
    content: ResponseToolUseContent,
    tool_def: ToolDefinition | None,
) -> None:
    """A no-op on_tag_open callback."""
    pass


async def _on_partial_noop(
    content: ResponseToolUseContent,
    tool_def: ToolDefinition | None,
) -> None:
    """A no-op on_tag_partial callback."""
    pass


async def _on_complete_noop(
    content: ResponseToolUseContent,
    tool_def: ToolDefinition | None,
) -> None:
    """A no-op on_tag_complete callback."""
    pass


class ToolUseResponseStreamSink(NoOpResponseStreamSink):
    """
    This stream sink will call:

    - on_tool_start()       : whenever we first see a new tool use
    - on_tool_partial(...)  : whenever a tool use is updated in stream
    - on_tool_complete()    : when a tool use is fully parsed and complete
    """

    def __init__(
        self,
        on_tool_start: Callable[
            [ResponseToolUseContent, ToolDefinition | None],
            Awaitable[None],
        ] = _on_start_noop,
        on_tool_partial: Callable[
            [ResponseToolUseContent, ToolDefinition | None],
            Awaitable[None],
        ] = _on_partial_noop,
        on_tool_complete: Callable[
            [ResponseToolUseContent, ToolDefinition | None],
            Awaitable[None],
        ] = _on_complete_noop,
    ):
        self.on_tool_start = on_tool_start
        self.on_tool_partial = on_tool_partial
        self.on_tool_complete = on_tool_complete

    async def on_tool_use_content_begin(
        self,
        idx: int,
        content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        await self.on_tool_start(content, tool_def)

    async def on_tool_use_content_partial(
        self,
        idx: int,
        old_content: ResponseToolUseContent,
        new_content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        await self.on_tool_partial(new_content, tool_def)

    async def on_tool_use_content_end(
        self,
        idx: int,
        final_content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        await self.on_tool_complete(final_content, tool_def)
