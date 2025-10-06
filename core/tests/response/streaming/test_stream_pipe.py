import asyncio
from typing import Any

import pytest

from agent_platform.core.delta.base import GenericDelta
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.responses.streaming.stream_pipe import (
    ResponseStreamPipe,
)
from agent_platform.core.responses.streaming.stream_sink_base import (
    ResponseStreamSinkBase,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


class CollectingStreamSink(ResponseStreamSinkBase):
    """A simple sink that records every callback invocation for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, tuple[Any, ...]]] = []

    # --- helper ---------------------------------------------------------
    async def _record(self, name: str, *args: Any) -> None:
        self.events.append((name, args))

    # --- ResponseStreamSinkBase interface ------------------------------
    async def on_message_begin(self, message: ResponseMessage) -> None:
        await self._record("on_message_begin", message)

    async def on_stop_reason(self, stop_reason: str | None) -> None:
        await self._record("on_stop_reason", stop_reason)

    async def on_usage(self, usage) -> None:
        await self._record("on_usage", usage)

    async def on_message_end(self, message: ResponseMessage) -> None:
        await self._record("on_message_end", message)

    async def on_content_begin(self, idx: int, content) -> None:
        await self._record("on_content_begin", idx, content)

    async def on_content_end(self, idx: int, final_content) -> None:
        await self._record("on_content_end", idx, final_content)

    async def on_text_content_begin(self, idx: int, content) -> None:
        await self._record("on_text_content_begin", idx, content)

    async def on_text_content_partial(self, idx: int, old_content, new_content) -> None:
        await self._record("on_text_content_partial", idx, old_content, new_content)

    async def on_text_content_end(self, idx: int, final_content) -> None:
        await self._record("on_text_content_end", idx, final_content)

    async def on_image_content_begin(self, idx: int, content) -> None:
        await self._record("on_image_content_begin", idx, content)

    async def on_image_content_partial(self, idx: int, old_content, new_content) -> None:
        await self._record("on_image_content_partial", idx, old_content, new_content)

    async def on_image_content_end(self, idx: int, final_content) -> None:
        await self._record("on_image_content_end", idx, final_content)

    async def on_audio_content_begin(self, idx: int, content) -> None:
        await self._record("on_audio_content_begin", idx, content)

    async def on_audio_content_partial(self, idx: int, old_content, new_content) -> None:
        await self._record("on_audio_content_partial", idx, old_content, new_content)

    async def on_audio_content_end(self, idx: int, final_content) -> None:
        await self._record("on_audio_content_end", idx, final_content)

    async def on_document_content_begin(self, idx: int, content) -> None:
        await self._record("on_document_content_begin", idx, content)

    async def on_document_content_partial(self, idx: int, old_content, new_content) -> None:
        await self._record("on_document_content_partial", idx, old_content, new_content)

    async def on_document_content_end(self, idx: int, final_content) -> None:
        await self._record("on_document_content_end", idx, final_content)

    async def on_tool_use_content_begin(self, idx: int, content, tool_def) -> None:
        await self._record("on_tool_use_content_begin", idx, content, tool_def)

    async def on_tool_use_content_partial(
        self,
        idx: int,
        old_content,
        new_content,
        tool_def,
    ) -> None:
        await self._record(
            "on_tool_use_content_partial",
            idx,
            old_content,
            new_content,
            tool_def,
        )

    async def on_tool_use_content_end(self, idx: int, final_content, tool_def) -> None:
        await self._record("on_tool_use_content_end", idx, final_content, tool_def)

    async def on_reasoning_content_begin(self, idx: int, content) -> None:
        await self._record("on_reasoning_content_begin", idx, content)

    async def on_reasoning_content_partial(self, idx: int, old_content, new_content) -> None:
        await self._record("on_reasoning_content_partial", idx, old_content, new_content)

    async def on_reasoning_content_end(self, idx: int, final_content) -> None:
        await self._record("on_reasoning_content_end", idx, final_content)


class ExplodingSink(CollectingStreamSink):
    """Sink that raises an exception on its first callback to test fault isolation."""

    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0

    async def on_message_begin(self, message: ResponseMessage) -> None:  # type: ignore[override]
        self.call_count += 1
        raise RuntimeError("kaboom")


class SlowSink(CollectingStreamSink):
    """Sink that sleeps longer than allowed timeout on its first callback."""

    def __init__(self, sleep_s: float) -> None:
        super().__init__()
        self.sleep_s = sleep_s
        self.call_count = 0

    async def on_message_begin(self, message: ResponseMessage) -> None:  # type: ignore[override]
        self.call_count += 1
        await asyncio.sleep(self.sleep_s)


@pytest.mark.asyncio
async def test_stream_pipe_happy_path() -> None:
    """Validate that a single delta yields the expected callbacks and final message."""

    # Construct a minimal, valid ResponseMessage we expect to stream
    text_content = ResponseTextContent(text="Hello, world!")
    expected_msg = ResponseMessage(content=[text_content], role="agent")

    # Encode the message as a single "replace root document" delta
    delta = GenericDelta(op="replace", path="", value=expected_msg.model_dump())

    async def delta_stream():
        yield delta
        # End of stream, just return (generator exhausts)

    # Prompt can be bare-bones for this unit test
    prompt = Prompt(system_instruction="Test system instruction")

    sink = CollectingStreamSink()

    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=0.01)

    # Exercise the pipe end-to-end
    await pipe.pipe_to(sink)

    # Basic integrity checks ------------------------------------------------
    assert pipe.reassembled_response == expected_msg

    event_names = [name for name, _ in sink.events]

    # We should at least see these critical events in order
    assert event_names[0] == "on_message_begin"
    assert "on_message_end" in event_names

    # The sink should have received callbacks for the text content
    assert "on_text_content_begin" in event_names
    assert "on_text_content_end" in event_names


@pytest.mark.asyncio
async def test_stream_pipe_flush_on_batch_size() -> None:
    """Flush should occur when 128-delta batch size limit is reached."""

    batch_size_limit = 128  # internal constant from ResponseStreamPipe._diff_worker

    # Build deltas producing incrementally longer text
    def make_message(text: str) -> dict[str, Any]:
        msg = ResponseMessage(content=[ResponseTextContent(text=text)], role="agent")
        return msg.model_dump()

    deltas: list[GenericDelta] = []

    # First delta replaces whole document with single char, subsequent replace text
    for i in range(batch_size_limit + 1):  # 129 deltas => 2 batches
        text = "x" * (i + 1)
        if i == 0:
            deltas.append(GenericDelta(op="replace", path="", value=make_message(text)))
        else:
            deltas.append(
                GenericDelta(op="replace", path="/content/0/text", value=text),
            )

    async def delta_stream():
        for d in deltas:
            yield d
        # generator ends

    prompt = Prompt(system_instruction="batch test")
    sink = CollectingStreamSink()

    # Large flush_interval so timeout does NOT trigger; only batch-size triggers flush
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=1.0)

    await pipe.pipe_to(sink)

    # Expect exactly one text partial (transition between batches)
    partial_count = sum(1 for name, _ in sink.events if name == "on_text_content_partial")
    assert partial_count == 1, f"expected 1 partial update, got {partial_count}"


@pytest.mark.asyncio
async def test_stream_pipe_flush_on_timeout() -> None:
    """Flush should occur automatically after `flush_interval` when no new deltas arrive."""

    flush_interval = 0.05  # 50 ms; keep test fast

    async def delta_stream():
        # First delta sets initial message
        first_msg = ResponseMessage(
            content=[ResponseTextContent(text="Hello")],
            role="agent",
        )
        yield GenericDelta(op="replace", path="", value=first_msg.model_dump())

        # Pause longer than flush_interval to trigger timeout-driven flush in _diff_worker
        await asyncio.sleep(flush_interval * 1.5)

        # Second delta extends the text
        yield GenericDelta(op="replace", path="/content/0/text", value="Hello world")
        # end

    prompt = Prompt(system_instruction="timeout test")
    sink = CollectingStreamSink()
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=flush_interval)

    await pipe.pipe_to(sink)

    # We should have received a message begin early, and then at least one partial afterwards
    event_names = [name for name, _ in sink.events]
    assert "on_message_begin" in event_names
    assert "on_text_content_partial" in event_names


@pytest.mark.asyncio
async def test_stream_pipe_flush_during_continuous_ingress() -> None:
    """Verify we still flush regularly when deltas keep arriving faster than the timeout."""

    flush_interval = 0.05

    async def delta_stream():
        base_text = "Hello"
        initial_msg = ResponseMessage(
            content=[ResponseTextContent(text=base_text)],
            role="agent",
        )
        yield GenericDelta(op="replace", path="", value=initial_msg.model_dump())

        for i in range(1, 6):
            await asyncio.sleep(flush_interval * 0.6)
            yield GenericDelta(
                op="replace",
                path="/content/0/text",
                value=f"{base_text} {i}",
            )

    prompt = Prompt(system_instruction="continuous ingress test")
    sink = CollectingStreamSink()
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=flush_interval)

    await pipe.pipe_to(sink)

    partial_count = sum(1 for name, _ in sink.events if name == "on_text_content_partial")
    assert partial_count >= 2, f"expected multiple partial flushes, got {partial_count}"


@pytest.mark.asyncio
async def test_stream_pipe_final_flush_on_end() -> None:
    """Any residual batch must flush when the stream ends (sentinel received)."""

    async def delta_stream():
        # Build a couple of quick deltas (<128) so timeout not hit, rely on sentinel flush
        yield GenericDelta(
            op="replace",
            path="",
            value=ResponseMessage(
                content=[ResponseTextContent(text="foo")],
                role="agent",
            ).model_dump(),
        )
        yield GenericDelta(op="replace", path="/content/0/text", value="foobar")
        # End of generator

    prompt = Prompt(system_instruction="end flush test")
    sink = CollectingStreamSink()
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=1.0)  # long

    await pipe.pipe_to(sink)

    # Sink must see exactly one message_end and final text value "foobar"
    end_events = [args for name, args in sink.events if name == "on_message_end"]
    assert len(end_events) == 1
    final_msg = end_events[0][0]
    assert isinstance(final_msg, ResponseMessage)
    first_content = final_msg.content[0]
    assert isinstance(first_content, ResponseTextContent)
    assert first_content.text == "foobar"


# ---------------------------------------------------------------
# 3. Content diff / partial events
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_growth_partial_then_end() -> None:
    """Growing text should produce partial callbacks then a final end callback."""

    flush_interval = 0.02

    async def delta_stream():
        # Initial single-character message
        msg = ResponseMessage(content=[ResponseTextContent(text="H")], role="agent")
        yield GenericDelta(op="replace", path="", value=msg.model_dump())

        # Sleep with extra margin to avoid Windows timer jitter coalescing batches
        await asyncio.sleep(flush_interval * 2.5)

        # Grow: "He"
        yield GenericDelta(op="replace", path="/content/0/text", value="He")

        # Sleep with extra margin to avoid Windows timer jitter coalescing batches
        await asyncio.sleep(flush_interval * 2.5)

        # Grow: "Hello"
        yield GenericDelta(op="replace", path="/content/0/text", value="Hello")
        # Done, generator ends

    prompt = Prompt(system_instruction="text diff test")
    sink = CollectingStreamSink()
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=flush_interval)

    await pipe.pipe_to(sink)

    # Events inspection
    event_names = [name for name, _ in sink.events]

    # One begin, two partials, one end
    assert event_names.count("on_text_content_begin") == 1
    assert event_names.count("on_text_content_partial") == 2
    assert event_names.count("on_text_content_end") == 1


@pytest.mark.asyncio
async def test_new_content_item_triggers_begin_events() -> None:
    """Adding a second content item should close first and begin second."""

    from agent_platform.core.responses.content import ResponseImageContent

    flush_interval = 0.02

    async def delta_stream():
        text_content = ResponseTextContent(text="Hello")
        first_msg = ResponseMessage(content=[text_content], role="agent")
        yield GenericDelta(op="replace", path="", value=first_msg.model_dump())

        # Extra margin to avoid timer jitter on Windows
        await asyncio.sleep(flush_interval * 2.5)

        # New message with an added image content at idx=1
        image_content = ResponseImageContent(
            mime_type="image/png",
            value="https://example.com/img.png",
            sub_type="url",
        )
        second_msg = ResponseMessage(content=[text_content, image_content], role="agent")
        yield GenericDelta(op="replace", path="", value=second_msg.model_dump())
        # generator ends

    prompt = Prompt(system_instruction="multi content diff test")
    sink = CollectingStreamSink()
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=flush_interval)

    await pipe.pipe_to(sink)

    # Find order of key events
    names = [name for name, _ in sink.events]

    first_img_begin = names.index("on_image_content_begin")

    # Ensure *some* content_end happened before the image_begin
    assert any(
        idx < first_img_begin for idx, name in enumerate(names) if name == "on_content_end"
    ), "Expected a content_end event before image content begin"

    assert names.count("on_image_content_begin") == 1


@pytest.mark.asyncio
async def test_sink_exception_is_muted() -> None:
    """If a sink raises, it should be muted while others continue receiving updates."""

    text1 = ResponseTextContent(text="hi")
    text2 = ResponseTextContent(text="hello")

    deltas = [
        GenericDelta(
            op="replace",
            path="",
            value=ResponseMessage(content=[text1], role="agent").model_dump(),
        ),
        GenericDelta(op="replace", path="/content/0/text", value=text2.text),
    ]

    async def delta_stream():
        for d in deltas:
            yield d

    prompt = Prompt(system_instruction="fault isolation test")

    exploding = ExplodingSink()
    healthy = CollectingStreamSink()

    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=0.01)

    await pipe.pipe_to(exploding, healthy)

    # Exploding sink should have been invoked exactly once
    assert exploding.call_count == 1

    # Healthy sink should have received both begin and end
    event_names = [name for name, _ in healthy.events]
    assert "on_message_begin" in event_names
    assert "on_message_end" in event_names


@pytest.mark.asyncio
async def test_sink_timeout_is_muted() -> None:
    """Sink exceeding timeout should be muted; other sinks unaffected."""

    sink_timeout = 0.05
    slow_sleep = sink_timeout * 2

    deltas = [
        GenericDelta(
            op="replace",
            path="",
            value=ResponseMessage(
                content=[ResponseTextContent(text="foo")],
                role="agent",
            ).model_dump(),
        ),
        GenericDelta(op="replace", path="/content/0/text", value="foobar"),
    ]

    async def delta_stream():
        for d in deltas:
            yield d

    prompt = Prompt(system_instruction="timeout isolation test")

    slow_sink = SlowSink(sleep_s=slow_sleep)
    healthy_sink = CollectingStreamSink()

    pipe = ResponseStreamPipe(
        stream=delta_stream(),
        prompt=prompt,
        flush_interval=0.01,
        sink_timeout=sink_timeout,
    )

    await pipe.pipe_to(slow_sink, healthy_sink)

    # Slow sink should have been called once (before timeout) and then muted.
    assert slow_sink.call_count == 1

    event_names = [name for name, _ in healthy_sink.events]
    assert "on_message_begin" in event_names
    assert "on_message_end" in event_names


# ---------------------------------------------------------------
# 4. Tool-use content resolution helpers
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_use_callbacks_include_tool_def() -> None:
    """Sink callbacks for tool_use should receive the matching ToolDefinition object."""

    from agent_platform.core.responses.content import ResponseToolUseContent

    # Define a simple tool
    tool_def = ToolDefinition(
        name="weather",
        description="Get weather",
        input_schema={"type": "object", "properties": {"location": {"type": "string"}}},
    )

    prompt = Prompt(system_instruction="tool test", tools=[tool_def])

    tool_content = ResponseToolUseContent(
        tool_call_id="call-1",
        tool_name="weather",
        tool_input_raw='{"location": "Paris"}',
    )

    response_msg = ResponseMessage(content=[tool_content], role="agent")

    # Remove internal-only _tool_input field so model_validate will accept it
    msg_dict = response_msg.model_dump()
    for item in msg_dict["content"]:
        item.pop("_tool_input", None)

    delta = GenericDelta(op="replace", path="", value=msg_dict)

    async def delta_stream():
        yield delta

    sink = CollectingStreamSink()
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=0.01)

    await pipe.pipe_to(sink)

    # Find the tool_use begin event arguments
    for name, args in sink.events:
        if name == "on_tool_use_content_begin":
            _idx, content_arg, tool_def_arg = args  # type: ignore[assignment]
            assert isinstance(content_arg, ResponseToolUseContent)
            assert tool_def_arg is tool_def  # should be same instance
            break
    else:  # pragma: no cover
        pytest.fail("on_tool_use_content_begin not seen")


# ---------------------------------------------------------------
# 5. Pipe helper APIs (regex & reassembled_response)
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipe_regex_helpers() -> None:
    """Validate raw_response_matches and postfix variant."""

    text_content = ResponseTextContent(text="The quick brown fox")
    final_msg = ResponseMessage(content=[text_content], role="agent")
    delta = GenericDelta(op="replace", path="", value=final_msg.model_dump())

    async def delta_stream():
        yield delta

    prompt = Prompt(system_instruction="regex test")
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=0.01)
    await pipe.pipe_to()  # no sinks needed

    # reassembled_response present
    assert pipe.reassembled_response == final_msg

    import re

    assert pipe.raw_response_matches(re.compile(r".*quick brown.*"))
    assert not pipe.raw_response_matches(re.compile(r".*lazy dog.*"))

    # postfix helper
    assert pipe.raw_response_matches_with_postfix(re.compile(r".*brown fox jumps.*"), " jumps")


# ---------------------------------------------------------------
# 6. Robustness / cleanup scenarios
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipe_aclose_idempotent() -> None:
    """Calling aclose twice should not raise and should leave pipe closed."""

    delta = GenericDelta(
        op="replace",
        path="",
        value=ResponseMessage(
            content=[ResponseTextContent(text="bye")],
            role="agent",
        ).model_dump(),
    )

    async def delta_stream():
        yield delta

    prompt = Prompt(system_instruction="close test")
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=0.01)
    await pipe.pipe_to()  # run to completion

    # First explicit close (should be no-op but allowed)
    await pipe.aclose()
    # Second explicit close must also be harmless
    await pipe.aclose()

    assert pipe.stream_closed


@pytest.mark.asyncio
async def test_kind_change_raises_and_cleans_up() -> None:
    """Changing content kind at same index should raise RuntimeError and cancel tasks."""

    from agent_platform.core.responses.content import ResponseImageContent

    text_msg = ResponseMessage(
        content=[ResponseTextContent(text="hi")],
        role="agent",
    )
    image_msg = ResponseMessage(
        content=[
            ResponseImageContent(
                mime_type="image/jpeg",
                value="https://example.com/cat.jpg",
                sub_type="url",
            )
        ],
        role="agent",
    )

    flush = 0.02

    delta1 = GenericDelta(op="replace", path="", value=text_msg.model_dump())
    delta2 = GenericDelta(op="replace", path="", value=image_msg.model_dump())

    async def delta_stream():
        yield delta1
        await asyncio.sleep(flush * 1.5)
        yield delta2  # triggers kind change

    prompt = Prompt(system_instruction="kind error test")
    pipe = ResponseStreamPipe(stream=delta_stream(), prompt=prompt, flush_interval=flush)

    with pytest.raises(RuntimeError, match="Content kind changed"):
        await pipe.pipe_to(CollectingStreamSink())

    # Pipe should be marked closed and internal tasks done
    assert pipe.stream_closed
    for task in (pipe._reader_task, pipe._diff_task, pipe._dispatch_task):
        assert task is None or task.done()


@pytest.mark.asyncio
async def test_tail_end_is_final_for_index_zero() -> None:
    """
    When a new content item is appended, the previous tail (idx 0) must get
    `..._end` exactly once and **never** receive a subsequent `..._partial`.
    """
    from agent_platform.core.responses.content import ResponseImageContent

    async def delta_stream():
        # 1️⃣ initial single-text message
        text = ResponseTextContent(text="Hello")
        yield GenericDelta(
            op="replace",
            path="",
            value=ResponseMessage(content=[text], role="agent").model_dump(),
        )

        # give the pipe enough time to flush
        await asyncio.sleep(0.02)

        # 2️⃣ append an image, text stays unchanged
        img = ResponseImageContent(
            mime_type="image/png",
            value="https://example.com/img.png",
            sub_type="url",
        )
        yield GenericDelta(
            op="replace",
            path="",
            value=ResponseMessage(content=[text, img], role="agent").model_dump(),
        )

    sink = CollectingStreamSink()
    pipe = ResponseStreamPipe(
        stream=delta_stream(),
        prompt=Prompt(system_instruction="dup-event test"),
        flush_interval=0.01,
    )

    await pipe.pipe_to(sink)

    # ── verification ──────────────────────────────────────────────
    # Find the first `end` for idx 0
    end_pos = next(
        i
        for i, (name, args) in enumerate(sink.events)
        if name == "on_text_content_end" and args[0] == 0  # idx == 0
    )

    # Ensure NO later `partial` for idx 0 exists
    duplicate = any(
        name == "on_text_content_partial" and args[0] == 0 and i > end_pos
        for i, (name, args) in enumerate(sink.events)
    )

    assert not duplicate, "saw partial callback after end for idx 0"


@pytest.mark.asyncio
async def test_first_incomplete_delta_is_not_lost() -> None:
    """
    The first delta only adds the `role` field --> not yet a valid `ResponseMessage`.
    It *must* be kept until the second delta (which adds `content`) arrives.
    """

    flush_interval = 0.02

    # 1️⃣ delta adds /role  (invalid on its own)
    delta_role = GenericDelta(op="replace", path="", value={"role": "agent"})

    # 2️⃣ delta adds /content  (together they form a valid message)
    text_content = ResponseTextContent(text="hi")
    delta_content = GenericDelta(
        op="add",
        path="/content",
        value=[text_content.model_dump()],
    )

    async def delta_stream():
        yield delta_role
        # We'd try to flush now, but the message is not complete yet
        await asyncio.sleep(flush_interval * 1.5)
        # After this, the message is complete and we should see a flush
        yield delta_content

    pipe = ResponseStreamPipe(
        stream=delta_stream(),
        prompt=Prompt(system_instruction="loss-test"),
        flush_interval=flush_interval,
    )

    sink = CollectingStreamSink()
    await pipe.pipe_to(sink)

    # ── ASSERTIONS ───────────────────────────────────────────────
    # With the bug present, *no* callbacks fire → list is empty
    assert "on_message_begin" in [name for name, _ in sink.events]
    assert "on_message_end" in [name for name, _ in sink.events]
