import asyncio
import os
import re
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar, cast

import structlog

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.combine_delta import combine_generic_deltas
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseMessageContent,
    ResponseReasoningContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.responses.streaming.stream_sink_base import (
    ResponseStreamSinkBase,
)
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)
from agent_platform.core.tools.tool_definition import ToolDefinition

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# Sentinel objects placed on queues to signal “stream finished”
class DeltaEndSentinel:
    pass


class MsgEndSentinel:
    pass


class ResponseStreamPipe:
    """
    Consume a stream of `GenericDelta` objects, reassemble them into a
    `ResponseMessage`, and stream incremental updates to one or more sinks.

    This version is engineered for low tail-latency under concurrent load:
    heavy diffing work is executed in a thread pool; the main request
    coroutine never blocks on CPU, so it can keep reading tokens from the
    LLM-backend as fast as they arrive.
    """

    # 30 Hz flush cadence: limits JSON diff churn
    DEFAULT_FLUSH_INTERVAL: float = 1.0 / 30.0
    # 3 second timeout for per-sink callback latency
    DEFAULT_SINK_TIMEOUT: float = 3.0

    # Thread-pool dedicated to combine_generic_deltas
    _DIFF_POOL: ClassVar[ThreadPoolExecutor] = ThreadPoolExecutor(
        max_workers=os.cpu_count() or 1,  # over-subscription hurts with the GIL
        thread_name_prefix="delta-diff",
    )

    def __init__(
        self,
        stream: AsyncGenerator[GenericDelta, None],
        prompt: Prompt,
        *,
        flush_interval: float | None = None,
        delta_queue_size: int = 4096,
        sink_timeout: float | None = None,
    ) -> None:
        self.stream = stream
        self.source_prompt = prompt
        self.flush_interval: float = (
            flush_interval if flush_interval is not None else self.DEFAULT_FLUSH_INTERVAL
        )

        # Bound for per-sink callback latency
        self._sink_timeout: float = (
            sink_timeout if sink_timeout is not None else self.DEFAULT_SINK_TIMEOUT
        )

        # Fast lookup for tool definitions used by sinks
        self._tool_def_cache: dict[str, ToolDefinition] = {
            tool_def.name: tool_def for tool_def in self.source_prompt.tools
        }

        # ─── Runtime state ────────────────────────────────────────
        self.current_message: ResponseMessage | None = None  # may be incomplete
        self.last_message: ResponseMessage | None = None  # stable; dispatched
        self.stream_closed = False
        self._open_content_indices: set[int] = set()

        # Queues
        self._delta_q: asyncio.Queue[GenericDelta | DeltaEndSentinel] = asyncio.Queue(
            maxsize=delta_queue_size
        )
        self._msg_q: asyncio.Queue[ResponseMessage | MsgEndSentinel] = asyncio.Queue()

        # Sinks
        self._sinks: tuple[ResponseStreamSinkBase, ...] = ()

        # Sinks that have failed and are muted for the rest of the stream
        self._broken_sinks: set[ResponseStreamSinkBase] = set()

        # Task handles (set in pipe_to)
        self._reader_task: asyncio.Task[Any] | None = None
        self._diff_task: asyncio.Task[Any] | None = None
        self._dispatch_task: asyncio.Task[Any] | None = None

    # ──────────────────────────────────────────────────────────────
    # Public helpers
    # ──────────────────────────────────────────────────────────────
    @property
    def reassembled_response(self) -> ResponseMessage | None:
        """Return the latest complete `ResponseMessage`, if any."""
        return self.last_message

    def raw_response_matches(self, regex: re.Pattern[str]) -> bool:
        if not self.last_message:
            return False
        text = "\n".join(
            c.text for c in self.last_message.content if isinstance(c, ResponseTextContent)
        )
        return regex.match(text) is not None

    def raw_response_matches_with_postfix(
        self,
        regex: re.Pattern[str],
        postfix: str,
    ) -> bool:
        if not self.last_message:
            return False
        text = "\n".join(
            c.text for c in self.last_message.content if isinstance(c, ResponseTextContent)
        )
        return regex.match(text + postfix) is not None

    # ──────────────────────────────────────────────────────────────
    # Async context-manager sugar
    # ──────────────────────────────────────────────────────────────
    async def __aenter__(self) -> "ResponseStreamPipe":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────
    async def pipe_to(self, *sinks: ResponseStreamSinkBase) -> None:
        """
        Start streaming to *sinks*.  Returns when the upstream stream ends
        (or an exception occurs).  Re-entrance is not supported.
        """
        if self.stream_closed:
            raise RuntimeError("Stream already closed")

        # Skip explicit No-Op sink instances but keep subclasses that add behavior
        self._sinks = tuple(s for s in sinks if type(s) is not NoOpResponseStreamSink)

        loop = asyncio.get_running_loop()

        # ─── Tasks lifecycle ──────────────────────────────────────
        self._reader_task = loop.create_task(self._reader())
        self._diff_task = loop.create_task(self._diff_worker())
        self._dispatch_task = loop.create_task(self._dispatch_worker())

        tasks = (self._reader_task, self._diff_task, self._dispatch_task)
        try:
            await asyncio.gather(*tasks)
        finally:
            # cancel the rest if one finished with an error
            for t in tasks:
                if not t.done():
                    t.cancel()
            await self.aclose()

    async def aclose(self) -> None:
        """Close the upstream stream and make sure we won't call sinks again."""
        if self.stream_closed:
            return
        self.stream_closed = True

        # Cancel internal tasks
        tasks = tuple(t for t in (self._reader_task, self._diff_task, self._dispatch_task) if t)
        for task in tasks:
            try:
                if not task.done():
                    task.cancel()
            except asyncio.CancelledError:
                pass

        # Wait until every task *exists* (do not re-raise any exceptions)
        await asyncio.gather(*tasks, return_exceptions=True)

        # Ensure upstream stream is closed
        if hasattr(self.stream, "aclose"):
            try:
                await self.stream.aclose()
            except Exception:
                pass

        # Close sinks
        self._sinks = ()

    # ═════════════════════════════════════════════════════════════
    # Internal tasks
    # ═════════════════════════════════════════════════════════════
    async def _reader(self) -> None:
        """Read deltas from `self.stream` and shove them on `_delta_q`."""
        try:
            async for chunk in self.stream:
                await self._delta_q.put(chunk)
        finally:
            # Stream ended or errored, then we push sentinel for downstream workers
            await self._delta_q.put(DeltaEndSentinel())

    async def _diff_worker(self) -> None:
        """Continuously diff/validate pending deltas and emit messages.

        The previous implementation only flushed after *reading* a delta. If
        the LLM paused mid-generation, no further deltas would arrive and the
        consumer would never receive partially completed messages. We now
        employ `asyncio.wait_for` so that a timeout triggers a flush even when
        the queue is idle.
        """
        loop = asyncio.get_running_loop()
        buffer_obj: dict[str, Any] = {}
        batch: list[GenericDelta] = []
        batch_size_limit = 128

        while True:
            # Wait for the next delta, but time-out regularly so we can flush
            # in the absence of new data.
            try:
                delta = await asyncio.wait_for(self._delta_q.get(), timeout=self.flush_interval)
            except TimeoutError:
                delta = None

            # ─── End-of-stream sentinel ─────────────────────────────
            if isinstance(delta, DeltaEndSentinel):
                if batch:
                    buffer_obj, _ = await self._flush_batch(loop, batch, buffer_obj)
                    batch.clear()
                await self._msg_q.put(MsgEndSentinel())
                return

            # ─── Normal delta payload ──────────────────────────────
            if isinstance(delta, GenericDelta):
                batch.append(delta)

            # ─── Flush conditions ──────────────────────────────────
            if batch and (delta is None or len(batch) >= batch_size_limit):
                buffer_obj, flushed = await self._flush_batch(loop, batch, buffer_obj)
                if flushed:
                    batch.clear()

    async def _flush_batch(
        self,
        loop: asyncio.AbstractEventLoop,
        batch: list[GenericDelta],
        current_buf: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """Helper: run diff+validate in executor; push result to msg queue.

        Returns:
            tuple[dict[str, Any], bool]:
                - new_buf: the new buffer state
                - flushed: whether the batch was flushed (i.e. whether the
                  message is complete)
        """
        try:
            new_buf, msg = await loop.run_in_executor(
                self._DIFF_POOL,
                _apply_and_validate,  # local helper defined below
                batch,
                current_buf,
            )
        except Exception:
            # likely need more deltas, just keep current state
            return current_buf, False

        await self._msg_q.put(msg)
        return new_buf, True

    async def _dispatch_worker(self) -> None:
        """
        Consume fully-validated messages from `_msg_q` and send incremental
        updates to sinks.
        """
        while True:
            msg = await self._msg_q.get()
            if isinstance(msg, MsgEndSentinel):
                # Ensure the stable snapshot is set to the last message seen.
                # (It should already be, but this adds a final safeguard in
                #   case the previous update step was skipped due to early
                #   cancellation or unforeseen control-flow.)
                if self.current_message is not None:
                    self.last_message = self.current_message

                # final “end” callbacks
                if self.last_message:
                    await self._dispatch_message_end(self.last_message)
                return

            self.current_message = cast(ResponseMessage, msg)
            if self.last_message is None:
                await self._dispatch_message_begin(self.current_message)
            else:
                await self._dispatch_message_partial(self.last_message, self.current_message)

            # Update the stable snapshot _after_ dispatch so that it always
            # represents the most recently *dispatched* message, not the one
            # currently being diff-processed.
            self.last_message = self.current_message

    # ═════════════════════════════════════════════════════════════
    # Dispatch helpers
    # ═════════════════════════════════════════════════════════════
    def _find_matching_tool_def(self, tool_use: ResponseToolUseContent) -> ToolDefinition | None:
        return self._tool_def_cache.get(tool_use.tool_name)

    # ---------------- message-level ----------------
    async def _dispatch_message_begin(self, msg: ResponseMessage) -> None:
        await self._fan_out("on_message_begin", msg)
        for idx, content in enumerate(msg.content):
            await self._dispatch_content_begin(idx, content)
        if msg.stop_reason:
            await self._fan_out("on_stop_reason", msg.stop_reason)
        if msg.usage:
            await self._fan_out("on_usage", msg.usage)

    async def _dispatch_message_partial(
        self,
        old: ResponseMessage,
        new: ResponseMessage,
    ) -> None:
        # NOTE: We expect our streams to have "grow-only" semantics, and
        # they must _not_ change content kind (e.g. text -> image). This
        # is how LLMs inately behave (at least for now), but something
        # like a diffusion model might not necessarily work the exact same
        # way

        old_len = len(old.content)
        new_len = len(new.content)

        # 1) Diff common prefix (length never changes)
        for idx in range(old_len if new_len >= old_len else new_len):
            if old.content[idx].kind != new.content[idx].kind:
                raise RuntimeError("Content kind changed during streaming")
            await self._dispatch_content_partial(idx, old.content[idx], new.content[idx])

        # 2) Handle append(s)
        if new_len > old_len:
            # finalise old tail only if there was at least one item previously
            if old_len > 0:
                await self._dispatch_content_end(old_len - 1, new.content[old_len - 1])

            # open new items (if any)
            for idx in range(old_len, new_len):
                await self._dispatch_content_begin(idx, new.content[idx])

    async def _dispatch_message_end(self, msg: ResponseMessage) -> None:
        if msg.content:
            await self._dispatch_content_end(len(msg.content) - 1, msg.content[-1])

        # Close any still-open content items
        for idx, c in enumerate(msg.content):
            if idx in self._open_content_indices:
                await self._dispatch_content_end(idx, c)

        if msg.stop_reason:
            await self._fan_out("on_stop_reason", msg.stop_reason)
        if msg.usage:
            await self._fan_out("on_usage", msg.usage)
        await self._fan_out("on_message_end", msg)

    # ---------------- content-level ----------------
    async def _dispatch_content_begin(self, idx: int, content: ResponseMessageContent) -> None:
        await self._fan_out("on_content_begin", idx, content)
        self._open_content_indices.add(idx)
        match content:
            case ResponseTextContent() as c:
                await self._fan_out("on_text_content_begin", idx, c)
            case ResponseImageContent() as c:
                await self._fan_out("on_image_content_begin", idx, c)
            case ResponseAudioContent() as c:
                await self._fan_out("on_audio_content_begin", idx, c)
            case ResponseDocumentContent() as c:
                await self._fan_out("on_document_content_begin", idx, c)
            case ResponseToolUseContent() as c:
                await self._fan_out(
                    "on_tool_use_content_begin", idx, c, self._find_matching_tool_def(c)
                )
            case ResponseReasoningContent() as c:
                await self._fan_out("on_reasoning_content_begin", idx, c)

    async def _dispatch_content_partial(
        self,
        idx: int,
        old_content: ResponseMessageContent,
        new_content: ResponseMessageContent,
    ) -> None:
        match new_content:
            case ResponseTextContent() as new_c:
                await self._fan_out(
                    "on_text_content_partial",
                    idx,
                    cast(ResponseTextContent, old_content),
                    new_c,
                )
            case ResponseImageContent() as new_c:
                await self._fan_out(
                    "on_image_content_partial",
                    idx,
                    cast(ResponseImageContent, old_content),
                    new_c,
                )
            case ResponseAudioContent() as new_c:
                await self._fan_out(
                    "on_audio_content_partial",
                    idx,
                    cast(ResponseAudioContent, old_content),
                    new_c,
                )
            case ResponseDocumentContent() as new_c:
                await self._fan_out(
                    "on_document_content_partial",
                    idx,
                    cast(ResponseDocumentContent, old_content),
                    new_c,
                )
            case ResponseToolUseContent() as new_c:
                await self._fan_out(
                    "on_tool_use_content_partial",
                    idx,
                    cast(ResponseToolUseContent, old_content),
                    new_c,
                    self._find_matching_tool_def(new_c),
                )
            case ResponseReasoningContent() as new_c:
                await self._fan_out(
                    "on_reasoning_content_partial",
                    idx,
                    cast(ResponseReasoningContent, old_content),
                    new_c,
                )

    async def _dispatch_content_end(self, idx: int, final: ResponseMessageContent) -> None:
        await self._fan_out("on_content_end", idx, final)
        self._open_content_indices.discard(idx)
        match final:
            case ResponseTextContent() as c:
                await self._fan_out("on_text_content_end", idx, c)
            case ResponseImageContent() as c:
                await self._fan_out("on_image_content_end", idx, c)
            case ResponseAudioContent() as c:
                await self._fan_out("on_audio_content_end", idx, c)
            case ResponseDocumentContent() as c:
                await self._fan_out("on_document_content_end", idx, c)
            case ResponseToolUseContent() as c:
                await self._fan_out(
                    "on_tool_use_content_end",
                    idx,
                    c,
                    self._find_matching_tool_def(c),
                )
            case ResponseReasoningContent() as c:
                await self._fan_out("on_reasoning_content_end", idx, c)

    # ═════════════════════════════════════════════════════════════
    # Low-level utilities
    # ═════════════════════════════════════════════════════════════
    async def _fan_out(self, method: str, *args: Any) -> None:
        """
        Parallel fan-out with **fault isolation** and **latency bounds**.

        * Any sink raising **or** timing-out is logged exactly once and
          then excluded from further callbacks (muted).
        * Healthy sinks continue unaffected.
        """

        async def _call(sink: ResponseStreamSinkBase):
            if sink in self._broken_sinks or not hasattr(sink, method):
                return
            try:
                await asyncio.wait_for(
                    getattr(sink, method)(*args),  # type: ignore[attr-defined]
                    timeout=self._sink_timeout,
                )
            except Exception as exc:
                logger.warning(
                    "Sink %s failed in %s (muted for rest of stream): %s",
                    type(sink).__name__,
                    method,
                    exc,
                    exc_info=True,
                )
                self._broken_sinks.add(sink)

        if not self._sinks:
            return

        await asyncio.gather(*(_call(s) for s in self._sinks))


# ─────────────────────────────────────────────────────────────────────
# Executor helper kept at module level so it is picklable on Windows
# ─────────────────────────────────────────────────────────────────────
def _apply_and_validate(
    chunk_buf: list[GenericDelta],
    current_buf: dict[str, Any],
) -> tuple[dict[str, Any], ResponseMessage]:
    """
    Pure function executed in the thread-pool:
    merge the deltas and validate the resulting message.
    """
    new_buf = combine_generic_deltas(chunk_buf, current_buf)
    msg = ResponseMessage.model_validate(new_buf)
    return new_buf, msg
