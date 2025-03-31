"""Unit tests for the OpenAI platform parsers."""

from collections.abc import AsyncGenerator
from typing import cast

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.platforms.openai.parsers import OpenAIParsers
from agent_platform.core.responses.content import (
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage


class TestOpenAIParsers:
    """Tests for the OpenAI parsers."""

    @pytest.fixture
    def parsers(self) -> OpenAIParsers:
        """Create a parser instance for testing."""
        return OpenAIParsers()

    def test_parse_text_content(self, parsers: OpenAIParsers) -> None:
        """Test parsing text content."""
        content = {
            "type": "text",
            "text": "Hello, world!",
        }
        result = parsers.parse_text_content(content)

        assert isinstance(result, ResponseTextContent)
        assert result.text == "Hello, world!"

    def test_parse_image_content(self, parsers: OpenAIParsers) -> None:
        """Test parsing image content."""
        content = {
            "type": "image_url",
            "image_url": {
                "url": "base64_encoded_image",
            },
        }
        result = parsers.parse_image_content(content)

        assert result.mime_type == "image/jpeg"
        assert result.value == "base64_encoded_image"
        assert result.sub_type == "url"

    def test_parse_tool_use_content(self, parsers: OpenAIParsers) -> None:
        """Test parsing tool use content."""
        content = {
            "type": "function",
            "function": {
                "name": "test-tool",
                "arguments": '{"key": "value"}',
            },
            "id": "test-tool-call-id",
        }
        result = cast(ResponseToolUseContent, parsers.parse_tool_use_content(content))

        assert result.tool_call_id == "test-tool-call-id"
        assert result.tool_name == "test-tool"
        assert result.tool_input_raw == '{"key": "value"}'

    def test_parse_document_content(self, parsers: OpenAIParsers) -> None:
        """Test parsing document content."""
        content = {
            "type": "file",
            "file": {
                "name": "test.pdf",
                "url": "https://example.com/test.pdf",
            },
        }
        result = parsers.parse_document_content(content)

        assert result.mime_type == "application/pdf"
        assert result.value == "https://example.com/test.pdf"
        assert result.name == "test.pdf"
        assert result.sub_type == "url"

    def test_parse_content_item(self, parsers: OpenAIParsers) -> None:
        """Test parsing a content item."""
        content = {
            "type": "text",
            "text": "Hello, world!",
        }
        result = parsers.parse_content_item(content)

        assert isinstance(result, ResponseTextContent)
        assert result.text == "Hello, world!"

    def test_parse_content_item_invalid_type(self, parsers: OpenAIParsers) -> None:
        """Test parsing a content item with invalid type."""
        content = {
            "type": "invalid",
            "text": "Hello, world!",
        }
        with pytest.raises(ValueError, match="Unknown content type: invalid"):
            parsers.parse_content_item(content)

    def test_parse_response(self, parsers: OpenAIParsers) -> None:
        """Test parsing a response."""
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello, world!",
                    },
                },
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }
        result = parsers.parse_response(response)

        assert isinstance(result, ResponseMessage)
        assert isinstance(result.content[0], ResponseTextContent)
        assert result.content[0].text == "Hello, world!"
        assert result.role == "agent"
        assert result.raw_response == response

    def test_parse_response_with_tool_call(self, parsers: OpenAIParsers) -> None:
        """Test parsing a response with tool call."""
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "test-tool-call-id",
                                "type": "function",
                                "function": {
                                    "name": "test-tool",
                                    "arguments": '{"key": "value"}',
                                },
                            },
                        ],
                    },
                },
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }
        result = parsers.parse_response(response)

        assert isinstance(result, ResponseMessage)
        tool_content = cast(ResponseToolUseContent, result.content[0])
        assert tool_content.tool_call_id == "test-tool-call-id"
        assert tool_content.tool_name == "test-tool"
        assert tool_content.tool_input_raw == '{"key": "value"}'
        assert result.role == "agent"
        assert result.raw_response == response

    @pytest.mark.asyncio
    async def test_parse_stream_event(self, parsers: OpenAIParsers) -> None:
        """Test parsing a stream event."""
        event = {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "Hello, world!",
                    },
                },
            ],
        }
        response = {}
        message = ResponseMessage(
            content=[ResponseTextContent(text="Hello")],
            raw_response={},
            role="agent",
        )
        last_message = ResponseMessage(
            content=[ResponseTextContent(text="Hello")],
            raw_response={},
            role="agent",
        )
        result = parsers.parse_stream_event(
            event=event,
            response=response,
            message=message,
            last_message=last_message,
        )

        assert isinstance(result, AsyncGenerator)
        async for delta in result:
            assert isinstance(delta, GenericDelta)
            assert delta.op == "concat_string"
            assert delta.path == "/content/0/text"
            assert delta.value == "Hello, world!"

    @pytest.mark.asyncio
    async def test_parse_stream_event_with_tool_call(
        self,
        parsers: OpenAIParsers,
    ) -> None:
        """Test parsing a stream event with tool call."""
        event = {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "test-tool-call-id",
                                "type": "function",
                                "function": {
                                    "name": "test-tool",
                                    "arguments": '{"key": "value"}',
                                },
                            },
                        ],
                    },
                },
            ],
        }
        response = {}
        message = ResponseMessage(
            content=[ResponseTextContent(text="Hello")],
            raw_response={},
            role="agent",
        )
        last_message = ResponseMessage(
            content=[ResponseTextContent(text="Hello")],
            raw_response={},
            role="agent",
        )
        result = parsers.parse_stream_event(
            event=event,
            response=response,
            message=message,
            last_message=last_message,
        )

        assert isinstance(result, AsyncGenerator)
        async for delta in result:
            assert isinstance(delta, GenericDelta)
            assert delta.op == "add"
            assert delta.path == "/content/1"
            assert isinstance(delta.value, dict)
            assert delta.value["tool_call_id"] == "test-tool-call-id"
            assert delta.value["tool_name"] == "test-tool"
            assert delta.value["tool_input_raw"] == '{"key": "value"}'
