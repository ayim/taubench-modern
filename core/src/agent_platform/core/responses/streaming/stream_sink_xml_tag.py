import re
from collections.abc import Awaitable, Callable
from typing import Final

from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)

# ---------------------------------------------------------------------------
# Public callback type aliases : mirror the upstream semantics
# ---------------------------------------------------------------------------

OnTagOpen = Callable[[], Awaitable[None]]
OnTagPartial = Callable[[str, str], Awaitable[None]]  # tag, chunk
OnTagClose = Callable[[], Awaitable[None]]
OnTagComplete = Callable[[str, str], Awaitable[None]]  # tag, full_text


async def _noop_open() -> None:
    pass


async def _noop_partial(tag: str, chunk: str) -> None:
    pass


async def _noop_close() -> None:
    pass


async def _noop_complete(tag: str, full: str) -> None:
    pass


# ---------------------------------------------------------------------------
# Helper utilities: kept outside the class for clarity
# ---------------------------------------------------------------------------


def _keep_tail(buf: str, marker: str, extra: int = 0) -> str:
    """Return only the last *len(marker)-1 + extra* bytes of *buf*.

    That is enough to detect a marker that may be split across a chunk boundary
    on the next call.
    """

    tail_len = max(len(marker) - 1 + extra, 0)
    return buf[-tail_len:]


async def _emit_all_but_tail(
    buf: str,
    tail_len: int,
    tag: str,
    emit_partial: Callable[[str], Awaitable[None]],
) -> str:
    """Emit *buf* except for its last *tail_len* bytes via *emit_partial*.

    Returns the remainder to keep in the buffer.
    """

    if len(buf) <= tail_len:
        return buf

    safe_end = len(buf) - tail_len
    chunk, remainder = buf[:safe_end], buf[safe_end:]
    if chunk:
        await emit_partial(chunk)
    return remainder


# ---------------------------------------------------------------------------
# Core implementation (non-nesting, pending-close aware)
# ---------------------------------------------------------------------------


class XmlTagResponseStreamSink(NoOpResponseStreamSink):
    """Streaming sink that captures text within one or more instances of a specific
    XML-style tag (e.g., if `tag='MyTag'`, it processes `<MyTag>content</MyTag>`).
    The finalization of a captured tag's content can be optionally guaranteed
    only if its closing tag is immediately followed (ignoring intermediate
    whitespace) by an `expected_next_tag`.

    It is designed for chunked / streaming input where the <tag> / </tag> / <next>
    sequences can be arbitrarily split across chunk boundaries.

    Behaviour summary
    -----------------
    *   The first opening `<TAG>` (e.g., `<MyTag>`) starts capture. Nothing before a
        validly recognized opening tag sequence is emitted.
        *   If `expected_preceding_tag` (e.g., `</PrevTag>`) is configured, capture
            for `<TAG>` only starts if the opening `<TAG>` is found immediately
            after `</PrevTag>` (allowing for intermediate whitespace).
    *   While inside a tag, every byte of content is passed straight through via
        *on_tag_partial*.
    *   A candidate closing tag `</TAG>` is accepted **only if** either:
        - no *expected_next_tag* is configured, **or**
        - it is followed by optional whitespace **and** the exact string
          `<expected_next_tag>` --- *even if that opener itself is split across
          later chunks.*
    *   If `allow_multiple_instances` is `True` (default is `False`), after a
        complete tag instance is processed (including handling any
        `expected_next_tag` conditions), the sink resets to find and process
        subsequent instances of `<TAG>`. Otherwise, it considers its work
        finished after the first complete tag instance.
    *   If the decision on a closing tag cannot yet be made because the next bytes
        (for `expected_next_tag` check) are incomplete, the whole undecided slice
        is cached until more data arrives to prevent duplicate emissions.
    *   When a closing tag is accepted, *on_tag_close* and then *on_tag_complete*
        are fired with the full captured text for that tag instance.
    *   If the stream ends while the sink is still *inside* a tag and **no**
        `expected_next_tag` is set, it flushes whatever content it has
        (tolerating a partial `</TAG>`). If an `expected_next_tag` *is*
        configured, it does NOT auto-flush (assuming another text block might
        complete the sequence). Callers can force a flush by invoking
        `on_text_content_end` on a final block *without* setting
        `expected_next_tag` for that specific sink instance if needed.
    """

    __slots__ = (
        "_allow_multiple_instances",
        "_buffer",
        "_close_len",
        "_close_seq",
        "_content_parts",
        "_expected_next_open_seq",
        "_expected_prev_close_len",
        "_expected_prev_close_seq",
        "_finished",
        "_inside",
        "_on_close",
        "_on_complete",
        "_on_open",
        "_on_partial",
        "_open_len",
        "_open_seq",
        "_pending_close",
        "_pending_open",
        "_tag",
    )

    # ------------------------- construction -----------------------------

    def __init__(  # noqa: PLR0913
        self,
        tag: str,
        *,
        expected_next_tag: str | None = None,
        expected_preceding_tag: str | None = None,
        allow_multiple_instances: bool = False,
        on_tag_open: OnTagOpen = _noop_open,
        on_tag_partial: OnTagPartial = _noop_partial,
        on_tag_close: OnTagClose = _noop_close,
        on_tag_complete: OnTagComplete = _noop_complete,
    ) -> None:
        if "<" in tag or ">" in tag:
            raise ValueError("Provide the *name* of the tag, e.g. 'X', not '<X>'")

        if expected_next_tag and ("<" in expected_next_tag or ">" in expected_next_tag):
            raise ValueError("Provide the *name* of the expected next tag, e.g. 'Y', not '<Y>'")

        self._tag: Final[str] = tag
        self._open_seq: Final[str] = f"<{tag}>"
        self._close_seq: Final[str] = f"</{tag}>"
        self._open_len: Final[int] = len(self._open_seq)
        self._close_len: Final[int] = len(self._close_seq)
        self._allow_multiple_instances: Final[bool] = allow_multiple_instances

        # --- streaming state ---
        self._buffer: str = ""
        self._inside: bool = False
        self._content_parts: list[str] = []
        self._pending_close: str = ""  # undecided slice (before_close+</X>+partial after)
        self._pending_open: str = ""
        self._finished: bool = False

        # --- caller options ---
        self._expected_next_open_seq: Final[str | None] = (
            f"<{expected_next_tag}>" if expected_next_tag else None
        )
        self._expected_prev_close_seq: Final[str | None] = (
            f"</{expected_preceding_tag}>" if expected_preceding_tag else None
        )
        self._expected_prev_close_len: Final[int] = (
            len(self._expected_prev_close_seq) if self._expected_prev_close_seq else 0
        )

        # --- callbacks ---
        self._on_open = on_tag_open
        self._on_partial = on_tag_partial
        self._on_close = on_tag_close
        self._on_complete = on_tag_complete

    @property
    def finished(self) -> bool:
        return self._finished and not self._allow_multiple_instances

    async def force_close(self) -> None:
        self._finished = True
        if self._inside:
            await self._flush_remaining_content()

    # ------------------------------------------------------------------
    # ResponseStreamSink interface (called by the platform)
    # ------------------------------------------------------------------

    async def on_text_content_begin(self, idx: int, content: ResponseTextContent) -> None:
        # If we don't allow multiple instances and we're already finished,
        # then we don't need to process any more data.
        if self.finished:
            return

        self._reset_state()
        await self._process_delta(content.text)

    async def on_text_content_partial(
        self,
        idx: int,
        old_content: ResponseTextContent,
        new_content: ResponseTextContent,
    ) -> None:
        # If we don't allow multiple instances and we're already finished,
        # then we don't need to process any more data.
        if self.finished:
            return

        delta = new_content.text[len(old_content.text) :]
        await self._process_delta(delta)

    async def on_text_content_end(self, idx: int, final_content: ResponseTextContent) -> None:
        # If we don't allow multiple instances and we're already finished,
        # then we don't need to process any more data.
        if self.finished:
            return

        # Auto-flush only when *not* waiting for an expected next tag
        if self._inside and not self._expected_next_open_seq:
            await self._flush_remaining_content()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _reset_state(self) -> None:
        self._buffer = ""
        self._inside = False
        self._content_parts.clear()
        self._pending_close = ""

    async def _process_delta(self, delta: str) -> None:  # noqa: C901 PLR0912 PLR0915
        if self._pending_open:
            delta = self._pending_open + delta
            self._pending_open = ""

        # Pre-pend any undecided slice from a previous pass
        if self._pending_close:
            delta = self._pending_close + delta
            self._pending_close = ""

        self._buffer += delta

        while True:
            if not self._inside:
                open_idx = self._buffer.find(self._open_seq)
                if open_idx == -1:
                    self._buffer = _keep_tail(
                        self._buffer,
                        self._open_seq,
                        self._expected_prev_close_len + 64,
                    )
                    return

                if self._expected_prev_close_seq:
                    # Careful to try every occurrence of <X> in case
                    # there are multiple with only one satisfying the look-behind
                    # criteria
                    found = False
                    while open_idx != -1:
                        # look-behind window: *before* <X>
                        lookbehind = self._buffer[:open_idx]
                        m = re.search(
                            rf"{re.escape(self._expected_prev_close_seq)}\s*$",
                            lookbehind,
                        )
                        if m:
                            found = True
                            break
                        open_idx = self._buffer.find(self._open_seq, open_idx + 1)

                    if not found:
                        # Could be split across chunks --> keep tail & wait
                        self._pending_open = self._buffer[open_idx:]  # from <X> onwards
                        self._buffer = _keep_tail(
                            self._buffer[:open_idx],
                            self._open_seq,
                            self._expected_prev_close_len + 64,
                        )
                        return

                # Discard text before <X>
                self._buffer = self._buffer[open_idx + self._open_len :]
                self._inside = True
                await self._on_open()

            # --- inside: look for </X> ---
            close_idx = self._buffer.find(self._close_seq)
            if close_idx == -1:
                # No close yet -> emit everything except possible partial tail
                self._buffer = await _emit_all_but_tail(
                    self._buffer,
                    tail_len=self._close_len - 1,
                    tag=self._tag,
                    emit_partial=lambda chunk: self._emit_partial_sync(chunk),
                )
                return

            before_close = self._buffer[:close_idx]
            post_close_start = close_idx + self._close_len
            after_close = self._buffer[post_close_start:]

            if self._expected_next_open_seq:
                # Need to decide if this really closes.
                # Peel optional whitespace after </X>
                m_ws = re.match(r"^(\s*)", after_close)
                ws_len = len(m_ws.group(1)) if m_ws else 0
                remain = after_close[ws_len:]

                # 1) not enough bytes to decide: when *remain* is
                # a *prefix* of the expected open seq
                if len(remain) < len(
                    self._expected_next_open_seq
                ) and self._expected_next_open_seq.startswith(remain):
                    # keep undecided slice & wait for more data
                    self._pending_close = before_close + self._close_seq + after_close
                    self._buffer = ""
                    return

                # 2) exact match --> real close
                if remain.startswith(self._expected_next_open_seq):
                    if before_close:
                        await self._emit_partial_sync(before_close)
                    self._buffer = after_close  # skip </X>
                    await self._flush()
                    continue

                # 3) we have enough bytes to be SURE it's *not* <expected_next_tag>
                chunk = before_close + self._close_seq
                await self._emit_partial_sync(chunk)
                self._buffer = after_close
                continue

            # No expected_next_tag: close immediately.
            if before_close:
                await self._emit_partial_sync(before_close)
            self._buffer = after_close
            await self._flush()
            continue

    # ----------------------- helpers ------------------------------

    async def _emit_partial_sync(self, chunk: str) -> None:
        self._content_parts.append(chunk)
        await self._on_partial(self._tag, chunk)

    async def _flush(self) -> None:
        self._finished = True
        await self._on_close()
        full_text = "".join(self._content_parts)
        await self._on_complete(self._tag, full_text)
        self._content_parts.clear()
        self._inside = False

    async def _flush_remaining_content(self) -> None:
        """Emit whatever remains (tolerant of a partial close_tag)."""
        prefix = self._close_seq[:-1]  # e.g. '</X'
        idx = self._buffer.find(prefix)
        if idx != -1:
            if idx:
                await self._emit_partial_sync(self._buffer[:idx])
        elif self._buffer:
            await self._emit_partial_sync(self._buffer)
        await self._flush()
