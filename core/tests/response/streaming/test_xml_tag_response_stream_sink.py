from dataclasses import dataclass

import pytest

from agent_platform.core.responses.streaming.stream_sink_xml_tag import (
    XmlTagResponseStreamSink,
)

# ---------------------------------------------------------------------------
# Lightweight stub for the platform's ResponseTextContent
# ---------------------------------------------------------------------------


@dataclass
class ResponseTextContent:
    text: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class Recorder:
    """Collects callbacks emitted by *XmlTagResponseStreamSink* for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str | None]] = []
        self._buf: list[str] = []  # accumulates full text for *complete*

    # Callbacks ----------------------------------------------------------

    async def open(self) -> None:
        self.events.append(("open", None))

    async def partial(self, tag: str, chunk: str) -> None:
        self.events.append(("partial", chunk))
        self._buf.append(chunk)

    async def close(self) -> None:
        self.events.append(("close", None))

    async def complete(self, tag: str, full: str) -> None:
        # Caller's *full* may be empty when backlog-flush auto-closes.
        self.events.append(("complete", full))

    # Assertion helpers --------------------------------------------------

    def names(self) -> list[str]:
        return [n for n, _ in self.events]

    def full_text(self) -> str:
        return "".join(c or "" for n, c in self.events if n == "partial")

    def all_texts(self) -> list[str]:
        texts = []
        current = ""
        for n, c in self.events:
            if n == "partial":
                current += c or ""
            elif n == "complete":
                texts.append(current)
                current = ""
        return texts


async def _drive(sink: XmlTagResponseStreamSink, chunks: list[str]) -> Recorder:
    recorder = Recorder()
    sink._on_open = recorder.open  # monkey-patch our recorder
    sink._on_partial = recorder.partial
    sink._on_close = recorder.close
    sink._on_complete = recorder.complete

    if not chunks:
        return recorder

    # Feed first chunk via *begin*
    first = ResponseTextContent(chunks[0])
    await sink.on_text_content_begin(0, first)  # type: ignore (for testing)
    prior = first

    # Subsequent chunks --> *partial*
    for chunk in chunks[1:]:
        new = ResponseTextContent(prior.text + chunk)
        await sink.on_text_content_partial(0, prior, new)  # type: ignore (for testing)
        prior = new

    await sink.on_text_content_end(0, prior)  # type: ignore (for testing)
    return recorder


# ---------------------------------------------------------------------------
# PARAMETRIZED CASES: no expected_next_tag
# ---------------------------------------------------------------------------

BASIC_CASES: list[tuple[list[str], str, str]] = [
    # chunks, expected_text, id
    (["<X>hello</X>"], "hello", "single"),
    (["<X>he", "llo</X>"], "hello", "split-open-close"),
    (["junk<X>hi</X>junk"], "hi", "ignored-prefix-suffix"),
    (["<X>a<X>b</X>c</X>"], "a<X>b", "nested-same-tag-literal"),
    (["<X><X><X>deep</X></X></X>"], "<X><X>deep", "deep-nesting-literal"),
    (["<X></X>"], "", "empty"),
    (["<X><X> <X><X>deep</X> </X></X>\n</X>"], "<X> <X><X>deep", "very-deep"),
    (["<X>outer<X>inner</X>more</X>"], "outer<X>inner", "mixed-content"),
    (["prefix<X>content</X>"], "content", "tag-at-end"),
    (["<X>content</X>suffix"], "content", "tag-at-beginning"),
    (["<X>h", "e", "l", "l", "o</", "X", ">"], "hello", "close-split-every-char"),
    (["junk" * 1000 + "<X>ok</X>"], "ok", "huge-prefix"),
    (["<X>💩", "🍕</X>"], "💩🍕", "utf8-boundary"),
    (["<X>1<Z/>2</X>"], "1<Z/>2", "self-closing-foreign-tag"),
    (["<X>abc</"], "abc</", "dangling-partial-close-at-end"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chunks", "expected_text"),
    [(case[0], case[1]) for case in BASIC_CASES],
    ids=[case[2] for case in BASIC_CASES],
)
async def test_basic_cases(
    chunks: list[str],
    expected_text: str,
) -> None:
    sink = XmlTagResponseStreamSink("X")
    rec = await _drive(sink, chunks)
    names = rec.names()
    assert names[0] == "open"
    for name in names[1:-2]:
        assert name == "partial"
    assert names[-2:] == ["close", "complete"]
    assert rec.full_text() == expected_text


# ---------------------------------------------------------------------------
# PARAMETRIZED CASES: expected_next_tag = "Y"
# ---------------------------------------------------------------------------

NEXTTAG_CASES: list[tuple[list[str], str, str]] = [
    (["<X>hello</X> <Y>"], "hello", "single-with-next"),
    (["<X>he", "llo</X>", "\n\t", " ", "<Y", ">"], "hello", "close-split-before-next"),
    (["junk<X>hi</X> <Y>junk"], "hi", "ignored-prefix-with-next"),
    (["<X>a<X>b</X>c</X><Y>"], "a<X>b</X>c", "nested-tag-literal-then-next"),
    (["<X><X><X>deep</X></X></X> \t<Y>\ntest"], "<X><X>deep</X></X>", "deep-nesting-with-next"),
    (["<X></X><Y>"], "", "empty-with-next"),
    (
        ["<X><X> <X><X>deep</X> </X></X>\n</X>  <Y>"],
        "<X> <X><X>deep</X> </X></X>\n",
        "very-deep-with-next",
    ),
    (["<X>outer<X>inner</X>more</X><Y>"], "outer<X>inner</X>more", "mixed-content-with-next"),
    (["prefix<X>content</X><Y>"], "content", "tag-at-end-with-next"),
    (["<X>content</X> <Y> suffix"], "content", "tag-at-beginning-with-next"),
    (["<X>hi</X>", " ", "<", "Y>"], "hi", "multi-chunk-next-opener"),
    (["<X>bye</X>\t\t<Y>"], "bye", "tabs-before-next"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chunks", "expected_text"),
    [(case[0], case[1]) for case in NEXTTAG_CASES],
    ids=[case[2] for case in NEXTTAG_CASES],
)
async def test_cases_with_expected_next_tag(
    chunks: list[str],
    expected_text: str,
) -> None:
    sink = XmlTagResponseStreamSink("X", expected_next_tag="Y")
    rec = await _drive(sink, chunks)
    names = rec.names()
    assert names[0] == "open"
    assert names[-2:] == ["close", "complete"]
    for name in names[1:-2]:
        assert name == "partial"
    assert rec.full_text() == expected_text


# ---------------------------------------------------------------------------
# PARAMETRIZED CASES: expected_preceding_tag = "P"
# ---------------------------------------------------------------------------

PREVTAG_CASES: list[tuple[list[str], str | None, str]] = [
    # chunks, expected_text, id
    (["</P><X>ok</X>"], "ok", "tight-close-open"),
    (["</P>  <X>hi</X>"], "hi", "ws-between-close-open"),
    (["</", "P>", "<X>split</X>"], "split", "preceding-close-split-two"),
    (["</", "P", ">", " ", "<", "X>", "yay</X>"], "yay", "preceding-close-split-many"),
    (["stuff</P><X>a</X>"], "a", "long-prefix-before-close"),
    (["</P>\n\t<X>nl</X>"], "nl", "newline-tab-between"),
    (["</P>", "  <X>late</X>"], "late", "open-split-from-close"),
    # ---------- negative cases (expected_text = None --> should NOT finalise)
    (["</p><X>case</X>"], None, "case-mismatch"),
    (["</Pa><X>nope</X>"], None, "prefix-trap"),
    (["</P><Y/> <X>later</X>"], None, "foreign-element-between"),
    (["oops<X>never</X>"], None, "missing-preceding-close"),
    (["</P></X>"], None, "preceding-close-but-wrong-open"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chunks", "expected_text"),
    [(case[0], case[1]) for case in PREVTAG_CASES],
    ids=[case[2] for case in PREVTAG_CASES],
)
async def test_cases_with_expected_preceding_tag(
    chunks: list[str],
    expected_text: str | None,
) -> None:
    sink = XmlTagResponseStreamSink("X", expected_preceding_tag="P")
    rec = await _drive(sink, chunks)
    if expected_text is None:  # negative rows
        assert "complete" not in rec.names()
        return
    assert rec.names()[0] == "open"
    assert rec.names()[-2:] == ["close", "complete"]
    assert rec.full_text() == expected_text


# ---------------------------------------------------------------------------
# REAL WORLD TOUBLESOME CASES
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_world_troublesome_cases_1() -> None:
    chunks = [
        "<thinking>\nThe user wants to know about my output format. According to the ",
        "instructions, I must include my thoughts on how best to respond to the user's ",
        "message in a <thinking>...</thinking> tag, provide my response in a <response>",
        "...</response> tag, and indicate the processing status in a <step>(processing|",
        "done)</step> tag. Additionally, any tool usage must be preceded by these tags.\n",
        "</thinking>\n<response>\nMy output format includes three main components: \n1. A",
        " <thinking> tag where I express my thoughts on how to respond to your message.\n",
        "2. A <response> tag where I provide the actual response to your query.\n3. A <ste",
        "p> tag indicating whether I am still processing the request or have finished with ",
        'either "processing" or "done".\nI use these tags to maintain clarity and ',
        "transparency in my process and response.\n</response>\n<step>done</step>",
    ]
    sink = XmlTagResponseStreamSink("thinking", expected_next_tag="response")
    rec = await _drive(sink, chunks)
    assert rec.full_text() == (
        "\nThe user wants to know about my output format. According to the "
        "instructions, I must include my thoughts on how best to respond to the "
        "user's message in a <thinking>...</thinking> tag, provide my response in a "
        "<response>...</response> tag, and indicate the processing status in a "
        "<step>(processing|done)</step> tag. Additionally, any tool usage must be "
        "preceded by these tags.\n"
    )

    sink = XmlTagResponseStreamSink(
        "response",
        expected_next_tag="step",
        expected_preceding_tag="thinking",
    )
    rec = await _drive(sink, chunks)
    assert rec.full_text() == (
        "\nMy output format includes three main components: \n1. A"
        " <thinking> tag where I express my thoughts on how to respond to your message.\n"
        "2. A <response> tag where I provide the actual response to your query.\n3. A <ste"
        "p> tag indicating whether I am still processing the request or have finished with "
        'either "processing" or "done".\nI use these tags to maintain clarity and '
        "transparency in my process and response.\n"
    )


@pytest.mark.asyncio
async def test_real_world_troublesome_cases_2() -> None:
    chunks = [
        "'<thinking>\nThe user wants to know about my output format. According to ",
        "the instructions, I must include my thoughts on how best to respond to the ",
        "user's message in a <thinking>...</thinking> tag, provide my response in a ",
        "<response>...</response> tag, and indicate the processing status in a <step>",
        "(processing|done)</step> tag. Additionally, any tool usage must be preceded ",
        "by these tags.\n</thinking>\n<response>\nMy output format includes three main ",
        "components: \n1. A <thinking> tag where I express my thoughts on how to ",
        "respond to your message.\n2. A <response> tag where I provide the actual ",
        "response to your query.\n3. A <step> tag indicating whether I am still ",
        'processing the request or have finished with either "processing" or "',
        'done".\nI use these tags to maintain clarity and transparency in my process',
        " and response.\n</response>\n<step>done</step>'",
    ]

    for chunk_size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
        finer_chunks = [chunk[i : i + chunk_size] for chunk in chunks for i in range(0, len(chunk), chunk_size)]
        sink = XmlTagResponseStreamSink("thinking", expected_next_tag="response")
        rec = await _drive(sink, finer_chunks)
        assert rec.full_text() == (
            "\nThe user wants to know about my output format. According to the "
            "instructions, I must include my thoughts on how best to respond to the "
            "user's message in a <thinking>...</thinking> tag, provide my response in a "
            "<response>...</response> tag, and indicate the processing status in a "
            "<step>(processing|done)</step> tag. Additionally, any tool usage must be "
            "preceded by these tags.\n"
        )

        sink = XmlTagResponseStreamSink(
            "response",
            expected_next_tag="step",
            expected_preceding_tag="thinking",
        )
        rec = await _drive(sink, finer_chunks)
        assert rec.full_text() == (
            "\nMy output format includes three main components: \n1. A"
            " <thinking> tag where I express my thoughts on how to respond to your message.\n"
            "2. A <response> tag where I provide the actual response to your query.\n3. A <ste"
            "p> tag indicating whether I am still processing the request or have finished with "
            'either "processing" or "done".\nI use these tags to maintain clarity and '
            "transparency in my process and response.\n"
        )

        sink = XmlTagResponseStreamSink("step", expected_preceding_tag="response")
        rec = await _drive(sink, finer_chunks)
        assert rec.full_text() == "done"


@pytest.mark.asyncio
async def test_real_world_troublesome_cases_3() -> None:
    chunks = [
        "\n<thinking>\nThe user is asking about my output format. I need to explain "
        "the required tags: `<thinking>`, `<response>`, and `<step>`. I should "
        "also acknowledge the configuration issues mentioned in the prompt, but "
        "clarify that they don't impact my ability to describe my output format."
        "</thinking>\n<response>\nMy output format includes the following tags:\n"
        "1.  `<thinking>...</thinking>`: This tag contains my internal thoughts "
        "and reasoning process. This part is not shown to you.\n2.  `<response>"
        "...</response>`: This tag contains the actual response that is visible "
        "to you.\n3.  `<step>(processing|done)</step>`: This tag indicates whether "
        "I am still working on your request (`processing`) or if I have finished "
        "(`done`).\n</response>\n<step>done</step>",
    ]

    for chunk_size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
        finer_chunks = [chunk[i : i + chunk_size] for chunk in chunks for i in range(0, len(chunk), chunk_size)]
        sink = XmlTagResponseStreamSink("thinking", expected_next_tag="response")
        rec = await _drive(sink, finer_chunks)
        assert rec.full_text() == (
            "\nThe user is asking about my output format. I need to explain "
            "the required tags: `<thinking>`, `<response>`, and `<step>`. I should "
            "also acknowledge the configuration issues mentioned in the prompt, but "
            "clarify that they don't impact my ability to describe my output format."
        )

        sink = XmlTagResponseStreamSink(
            "response",
            expected_next_tag="step",
            expected_preceding_tag="thinking",
        )
        rec = await _drive(sink, finer_chunks)
        assert rec.full_text() == (
            "\nMy output format includes the following tags:\n"
            "1.  `<thinking>...</thinking>`: This tag contains my internal thoughts "
            "and reasoning process. This part is not shown to you.\n2.  `<response>"
            "...</response>`: This tag contains the actual response that is visible "
            "to you.\n3.  `<step>(processing|done)</step>`: This tag indicates whether "
            "I am still working on your request (`processing`) or if I have finished "
            "(`done`).\n"
        )

        sink = XmlTagResponseStreamSink("step", expected_preceding_tag="response")
        rec = await _drive(sink, finer_chunks)
        assert rec.full_text() == "done"


# ---------------------------------------------------------------------------
# NEGATIVE: should *not* flush because <Y> never appears
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_flush_if_expected_next_never_arrives() -> None:
    chunks = ["<X>lost</X>  <Z>"]  # something other than <Y>
    sink = XmlTagResponseStreamSink("X", expected_next_tag="Y")
    rec = await _drive(sink, chunks)
    assert "complete" not in rec.names()  # still waiting for <Y>


# ---------------------------------------------------------------------------
# Split-boundary edge-cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_and_close_split_across_boundaries() -> None:
    # <X> split across 3 chunks; </X> split across 2.
    chunks = ["<", "X>foo</", "X>"]
    sink = XmlTagResponseStreamSink("X")
    rec = await _drive(sink, chunks)
    assert rec.full_text() == "foo"
    names = [n for n, _ in rec.events]
    assert names.count("open") == names.count("close") == 1


# ---------------------------------------------------------------------------
# Multiple complete tags in sequence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_complete_tags_in_sequence() -> None:
    """Test that multiple complete tags are processed independently."""
    chunks = ["<X>first</X>junk<X>second</X>"]
    sink = XmlTagResponseStreamSink("X")
    rec = await _drive(sink, chunks)
    # Should only capture the first complete tag
    assert rec.all_texts() == ["first", "second"]
    names = [n for n, _ in rec.events]
    # Should see exactly two complete cycles
    assert names.count("open") == 2
    assert names.count("close") == 2
    assert names.count("complete") == 2


@pytest.mark.asyncio
async def test_multiple_complete_tags_in_sequence_with_nested_tags() -> None:
    """Test that multiple complete tags are processed independently."""
    chunks = ["<X>first</X>junk<X>se\ncond</X>  \n<X>third"]
    sink = XmlTagResponseStreamSink("X", allow_multiple_instances=True)
    rec = await _drive(sink, chunks)
    # Should only capture the first complete tag
    assert rec.all_texts() == ["first", "se\ncond", "third"]
    names = [n for n, _ in rec.events]
    # Should see exactly two complete cycles
    assert names.count("open") == 3
    assert names.count("close") == 3
    assert names.count("complete") == 3


# ---------------------------------------------------------------------------
# Edge cases for when stream ends
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unclosed_tag_at_end() -> None:
    """Test that unclosed tags are flushed when stream ends."""
    chunks = ["<X>content never closed"]
    sink = XmlTagResponseStreamSink("X")
    rec = await _drive(sink, chunks)
    assert rec.full_text() == "content never closed"
    names = [n for n, _ in rec.events]
    assert names[0] == "open"
    for i in range(1, len(names) - 2):
        assert names[i] == "partial"
    assert names[-2] == "close"
    assert names[-1] == "complete"


@pytest.mark.asyncio
async def test_partial_close_tag_at_end() -> None:
    """Test tolerance for partial close tags at stream end."""
    chunks = ["<X>content</X"]  # Missing final ">"
    sink = XmlTagResponseStreamSink("X")
    rec = await _drive(sink, chunks)
    assert rec.full_text() == "content"
    names = [n for n, _ in rec.events]
    assert names[0] == "open"
    for i in range(1, len(names) - 2):
        assert names[i] == "partial"
    assert names[-2] == "close"
    assert names[-1] == "complete"


@pytest.mark.asyncio
async def test_very_partial_close_tag_at_end() -> None:
    """Test tolerance for very partial close tags at stream end."""
    chunks = ["<X>content</"]  # Only has "</"
    sink = XmlTagResponseStreamSink("X")
    rec = await _drive(sink, chunks)
    assert rec.full_text() == "content</"
    names = [n for n, _ in rec.events]
    assert names[0] == "open"
    for i in range(1, len(names) - 2):
        assert names[i] == "partial"
    assert names[-2] == "close"
    assert names[-1] == "complete"


@pytest.mark.asyncio
async def test_multiple_tags_with_final_unclosed() -> None:
    """Test multiple complete tags followed by an unclosed one."""
    chunks = ["<X>first</X><X>second</X><X>third"]
    sink = XmlTagResponseStreamSink("X", allow_multiple_instances=True)
    rec = await _drive(sink, chunks)
    assert rec.all_texts() == ["first", "second", "third"]
    names = [n for n, _ in rec.events]
    assert names.count("open") == 3
    assert names.count("close") == 3
    assert names.count("complete") == 3


@pytest.mark.asyncio
async def test_malformed_nested_with_unclosed_end() -> None:
    """Test nested tags where the stream ends unexpectedly."""
    chunks = ["<X>outer<X>inner"]  # Outer tag never closed
    sink = XmlTagResponseStreamSink("X")
    rec = await _drive(sink, chunks)
    assert rec.full_text() == "outer<X>inner"
    names = [n for n, _ in rec.events]
    assert names.count("complete") == 1


# ---------------------------------------------------------------------------
# ADVANCED SCENARIOS AND INTERACTIONS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allow_multiple_false_with_next_tag_stops_after_first_sequence() -> None:
    """
    Tests that with allow_multiple_instances=False (default) and expected_next_tag,
    the sink stops after the first complete <X>...</X><Y> sequence.
    """
    chunks = ["<X>one</X><Y>", " <X>two</X><Y>"]
    # allow_multiple_instances is False by default
    sink = XmlTagResponseStreamSink("X", expected_next_tag="Y")
    rec = await _drive(sink, chunks)

    assert rec.all_texts() == ["one"]
    assert rec.names().count("open") == 1
    assert rec.names().count("close") == 1
    assert rec.names().count("complete") == 1


@pytest.mark.asyncio
async def test_allow_multiple_true_with_next_tag_continues_for_multiple_sequences() -> None:
    """
    Tests that with allow_multiple_instances=True and expected_next_tag,
    the sink processes all <X>...</X><Y> sequences.
    """
    chunks = ["<X>one</X><Y>", " <X>two</X><Y>", " <X>three</X>", "<Y>"]
    sink = XmlTagResponseStreamSink("X", expected_next_tag="Y", allow_multiple_instances=True)
    rec = await _drive(sink, chunks)

    assert rec.all_texts() == ["one", "two", "three"]
    assert rec.names().count("open") == 3
    assert rec.names().count("close") == 3
    assert rec.names().count("complete") == 3


@pytest.mark.asyncio
async def test_allow_multiple_true_with_preceding_tag_requires_preceding_for_each() -> None:
    """
    Tests that with allow_multiple_instances=True and expected_preceding_tag,
    each instance of <X> requires its own <P> to be processed.
    """
    chunks = ["</P><X>one</X>", "ignored<X>orphan</X>", "</P><X>two</X>"]
    sink = XmlTagResponseStreamSink("X", expected_preceding_tag="P", allow_multiple_instances=True)
    rec = await _drive(sink, chunks)

    assert rec.all_texts() == ["one", "two"]
    assert rec.names().count("open") == 2
    assert rec.names().count("close") == 2
    assert rec.names().count("complete") == 2
