"""Unit tests for the Groq parsers."""

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.platforms.groq.parsers import GroqParsers
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage


class TestGroqParsers:
    """Tests for the Groq parser logic."""

    @pytest.fixture
    def parsers(self) -> GroqParsers:
        return GroqParsers()

    def test_parse_text_content(self, parsers: GroqParsers) -> None:
        from openai.types.responses import ResponseOutputText

        content = ResponseOutputText(
            type="output_text",
            text="Hello, Groq!",
            annotations=[],
            logprobs=None,
        )
        result = parsers.parse_text_content(content)
        assert isinstance(result, ResponseTextContent)
        assert result.text == "Hello, Groq!"

    def test_parse_tool_use_content(self, parsers: GroqParsers) -> None:
        from openai.types.responses import ResponseFunctionToolCall

        content = ResponseFunctionToolCall(
            id="api-id",
            call_id="call-1",
            type="function_call",
            name="test-tool",
            arguments='{"key": "value"}',
        )
        result = parsers.parse_tool_use_content(content)
        assert isinstance(result, ResponseToolUseContent)
        assert result.tool_call_id == "call-1"
        assert result.tool_name == "test-tool"

    def test_parse_response(self, parsers: GroqParsers) -> None:
        from types import SimpleNamespace

        from openai.types.responses import ResponseOutputMessage, ResponseOutputText

        output_message = ResponseOutputMessage(
            id="msg_1",
            type="message",
            role="assistant",
            status="completed",
            content=[
                ResponseOutputText(
                    type="output_text",
                    text="Hello, Groq!",
                    annotations=[],
                    logprobs=None,
                )
            ],
        )

        response = SimpleNamespace(
            id="resp_1",
            model="openai/gpt-oss-20b",
            output=[output_message],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            ),
        )

        result = parsers.parse_response(response)  # type: ignore[arg-type]
        assert isinstance(result, ResponseMessage)
        assert isinstance(result.content[0], ResponseTextContent)
        assert result.content[0].text == "Hello, Groq!"

    @pytest.mark.asyncio
    async def test_parse_stream_event(self, parsers: GroqParsers) -> None:
        from openai.types.responses import ResponseTextDeltaEvent

        event = ResponseTextDeltaEvent(
            type="response.output_text.delta",
            delta="Hello, ",
            content_index=0,
            item_id="msg_1",
            logprobs=[],
            output_index=0,
            sequence_number=1,
        )

        message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }

        deltas: list[GenericDelta] = []
        async for delta in parsers.parse_stream_event(event, message, last_message):
            deltas.append(delta)

        assert deltas
        assert any(
            item.get("text") == "Hello, "
            for item in message["content"]
            if isinstance(item, dict) and item.get("kind") == "text"
        )
