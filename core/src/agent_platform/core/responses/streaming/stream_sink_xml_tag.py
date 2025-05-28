from collections.abc import Awaitable, Callable

from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)


async def _on_start_noop() -> None:
    """A no-op on_tag_open callback."""
    pass


async def _on_partial_noop(tag: str, content: str) -> None:
    """A no-op on_tag_partial callback."""
    pass


async def _on_close_noop() -> None:
    """A no-op on_tag_close callback."""
    pass


async def _on_complete_noop(tag: str, content: str) -> None:
    """A no-op on_tag_complete callback."""
    pass


class XmlTagResponseStreamSink(NoOpResponseStreamSink):
    """
    This stream sink will call:

    - on_tag_open()        : whenever we first see <tag>
    - on_tag_partial(...)  : whenever new text inside <tag> ... </tag> arrives
    - on_tag_close()       : when </tag> is encountered
    - on_tag_complete(...) : after closing tag is fully parsed,
                             with the entire text between <tag> and </tag>.

    It supports chunked/streamed text, partial tags spanning multiple chunks,
    and multiple occurrences of the same tag in a single or across multiple chunks.
    """

    def __init__(
        self,
        tag: str,
        on_tag_open: Callable[[], Awaitable[None]] = _on_start_noop,
        on_tag_partial: Callable[[str, str], Awaitable[None]] = _on_partial_noop,
        on_tag_close: Callable[[], Awaitable[None]] = _on_close_noop,
        on_tag_complete: Callable[[str, str], Awaitable[None]] = _on_complete_noop,
    ):
        # Normalize user-provided tag to ensure it has <...> form:
        if not tag.startswith("<"):
            tag = f"<{tag}"
        if not tag.endswith(">"):
            tag = f"{tag}>"

        self.tag = tag
        # For example, if self.tag = "<my-tag>", self.as_closing_tag = "</my-tag>"
        self.as_closing_tag = "</" + self.tag[1:]

        self.on_tag_open = on_tag_open
        self.on_tag_partial = on_tag_partial  # (tag_str, chunk_of_text)
        self.on_tag_close = on_tag_close
        self.on_tag_complete = on_tag_complete  # (tag_str, all_text_inside)

        # Internal state
        self.parse_buffer = ""  # Accumulates partial data across callbacks
        self.is_open = False  # Are we currently inside <tag> ... </tag>?
        self.tag_content = ""  # Accumulates text inside the open tag

    async def on_text_content_begin(
        self,
        idx: int,
        content: ResponseTextContent,
    ) -> None:
        # Reset parsing state at the start of a new text block
        self.parse_buffer = ""
        self.is_open = False
        self.tag_content = ""

        await self._process_delta(content.text)

    async def on_text_content_partial(
        self,
        idx: int,
        old_content: ResponseTextContent,
        new_content: ResponseTextContent,
    ) -> None:
        # The newly arrived text is whatever's new in new_content vs old_content
        delta = new_content.text[len(old_content.text) :]
        await self._process_delta(delta)

    async def on_text_content_end(
        self,
        idx: int,
        final_content: ResponseTextContent,
    ) -> None:
        # Usually, the last delta has been processed in on_text_content_partial.
        # Nothing special needed here unless you're doing final checks.
        pass

    async def _process_delta(self, delta: str) -> None:
        """
        Accumulate new text in parse_buffer, then repeatedly search for
        open/close tags to properly dispatch the relevant callbacks.
        """
        self.parse_buffer += delta

        while True:
            if not self.is_open:
                # We are outside of our <tag>, look for the opening tag
                open_idx = self.parse_buffer.find(self.tag)
                if open_idx == -1:
                    # No opening tag found; keep partial data for next time
                    break
                else:
                    # Found the opening tag
                    self.is_open = True
                    await self.on_tag_open()

                    # Discard everything up to and including the opening tag
                    self.parse_buffer = self.parse_buffer[open_idx + len(self.tag) :]

                    # Clear the content buffer for the new tag
                    self.tag_content = ""
            else:
                # We are currently inside <tag> ... look for the closing tag
                close_idx = self.parse_buffer.find(self.as_closing_tag)
                if close_idx == -1:
                    # Closing tag not found yet
                    #
                    # We need to keep any possible partial match of as_closing_tag
                    # at the end of parse_buffer in case it's split across chunks.
                    closing_tag_len = len(self.as_closing_tag)
                    # We'll keep up to closing_tag_len - 1 characters at the end
                    potential_partial_start = max(
                        0,
                        len(self.parse_buffer) - (closing_tag_len - 1),
                    )

                    # The definitely-safe chunk is everything *before* that
                    chunk = self.parse_buffer[:potential_partial_start]
                    if chunk:
                        self.tag_content += chunk
                        await self.on_tag_partial(self.tag, chunk)

                    # Keep the tail in parse_buffer for a possible closing-tag fragment
                    self.parse_buffer = self.parse_buffer[potential_partial_start:]

                    # Wait for more data
                    break
                else:
                    # Found the closing tag
                    chunk = self.parse_buffer[:close_idx]
                    if chunk:
                        self.tag_content += chunk
                        await self.on_tag_partial(self.tag, chunk)

                    # We have a full open/close pair now
                    await self.on_tag_close()
                    await self.on_tag_complete(self.tag, self.tag_content)

                    # Reset state for next time
                    self.is_open = False
                    self.tag_content = ""

                    # Discard everything up to and including the closing tag
                    self.parse_buffer = self.parse_buffer[close_idx + len(self.as_closing_tag) :]
                    # Loop again to see if there's another <tag> afterwards
