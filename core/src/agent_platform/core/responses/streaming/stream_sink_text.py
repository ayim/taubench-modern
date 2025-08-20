from collections.abc import Awaitable, Callable

from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)


async def _on_start_noop(
    text: str,
) -> None:
    """A no-op on_text_start callback."""
    pass


async def _on_partial_noop(
    text: str,
) -> None:
    """A no-op on_text_partial callback."""
    pass


async def _on_complete_noop(
    text: str,
) -> None:
    """A no-op on_text_complete callback."""
    pass


class TextResponseStreamSink(NoOpResponseStreamSink):
    """
    This stream sink will call:

    - on_text_start()       : whenever we first see a new text content
    - on_text_partial(...)  : whenever a text content is updated in stream
    - on_text_complete()    : when a text content is fully parsed and complete
    """

    def __init__(
        self,
        on_text_start: Callable[
            [str],
            Awaitable[None],
        ] = _on_start_noop,
        on_text_partial: Callable[
            [str],
            Awaitable[None],
        ] = _on_partial_noop,
        on_text_complete: Callable[
            [str],
            Awaitable[None],
        ] = _on_complete_noop,
    ):
        self.on_text_start = on_text_start
        self.on_text_partial = on_text_partial
        self.on_text_complete = on_text_complete

    async def on_text_content_begin(
        self,
        idx: int,
        text: ResponseTextContent,
    ) -> None:
        await self.on_text_start(text.text)

    async def on_text_content_partial(
        self,
        idx: int,
        old_content: ResponseTextContent,
        new_content: ResponseTextContent,
    ) -> None:
        # Only fire if we have more text
        old_text = old_content.text
        new_text = new_content.text
        if len(new_text) > len(old_text):
            await self.on_text_partial(new_text[len(old_text) :])

    async def on_text_content_end(
        self,
        idx: int,
        final_content: ResponseTextContent,
    ) -> None:
        await self.on_text_complete(final_content.text)
