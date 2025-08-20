from collections.abc import Awaitable, Callable

from agent_platform.core.responses.content.reasoning import (
    ResponseReasoningContent,
)
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)


async def _on_start_noop(
    reasoning: str,
) -> None:
    """A no-op on_reasoning_start callback."""
    pass


async def _on_partial_noop(
    reasoning: str,
) -> None:
    """A no-op on_reasoning_partial callback."""
    pass


async def _on_complete_noop(
    reasoning: str,
    content: ResponseReasoningContent,
) -> None:
    """A no-op on_reasoning_complete callback."""
    pass


class ReasoningResponseStreamSink(NoOpResponseStreamSink):
    """
    This stream sink will call:

    - on_reasoning_start()       : whenever we first see a new reasoning content
    - on_reasoning_partial(...)  : whenever a reasoning content is updated in stream
    - on_reasoning_complete()    : when a reasoning content is fully parsed and complete
    """

    def __init__(
        self,
        on_reasoning_start: Callable[
            [str],
            Awaitable[None],
        ] = _on_start_noop,
        on_reasoning_partial: Callable[
            [str],
            Awaitable[None],
        ] = _on_partial_noop,
        on_reasoning_complete: Callable[
            [str, ResponseReasoningContent],
            Awaitable[None],
        ] = _on_complete_noop,
    ):
        self.on_reasoning_start = on_reasoning_start
        self.on_reasoning_partial = on_reasoning_partial
        self.on_reasoning_complete = on_reasoning_complete
        self._last_reasoning_text = ""

    def _get_reasoning_text(self, reasoning: ResponseReasoningContent) -> str:
        reasoning_text = ""
        if reasoning.reasoning:
            reasoning_text = reasoning.reasoning
        elif reasoning.summary:
            reasoning_text = "\n\n".join(reasoning.summary)
        elif reasoning.content:
            reasoning_text = "\n\n".join(reasoning.content)
        return reasoning_text.strip()

    async def on_reasoning_content_begin(
        self,
        idx: int,
        reasoning: ResponseReasoningContent,
    ) -> None:
        self._last_reasoning_text = self._get_reasoning_text(reasoning)
        await self.on_reasoning_start(self._last_reasoning_text)

    async def on_reasoning_content_partial(
        self,
        idx: int,
        old_content: ResponseReasoningContent,
        new_content: ResponseReasoningContent,
    ) -> None:
        # Only fire if we have more reasoning text
        new_text = self._get_reasoning_text(new_content)
        old_text = self._get_reasoning_text(old_content)
        delta_text = new_text[len(old_text) :]
        if delta_text:
            await self.on_reasoning_partial(delta_text)
            self._last_reasoning_text = new_text

    async def on_reasoning_content_end(
        self,
        idx: int,
        final_content: ResponseReasoningContent,
    ) -> None:
        new_text = self._get_reasoning_text(final_content)
        delta_text = new_text[len(self._last_reasoning_text) :]
        await self.on_reasoning_complete(
            delta_text,
            final_content,
        )
