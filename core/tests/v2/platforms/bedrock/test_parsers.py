from typing import Any
from unittest.mock import MagicMock

import pytest

from agent_server_types_v2.kernel import Kernel
from agent_server_types_v2.platforms.bedrock.parsers import BedrockParsers
from agent_server_types_v2.responses.content import (
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_server_types_v2.responses.response import ResponseMessage


class TestBedrockParsers:
    """Tests for the Bedrock parsers."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parsers(self, kernel: Kernel) -> BedrockParsers:
        """Create Bedrock parsers for testing."""
        parsers = BedrockParsers()
        parsers.attach_kernel(kernel)
        return parsers

    def test_parse_text_content(self, parsers: BedrockParsers) -> None:
        """Test parsing text content."""
        # Test with dict
        text_dict = {"type": "text", "text": "Hello, world!"}
        text_content = parsers.parse_text_content(text_dict)
        assert isinstance(text_content, ResponseTextContent)
        assert text_content.text == "Hello, world!"

        # Test with string
        text_str = "Hello, world!"
        text_content = parsers.parse_text_content(text_str)
        assert isinstance(text_content, ResponseTextContent)
        assert text_content.text == "Hello, world!"

        # Test with bytes
        text_bytes = b"Hello, world!"
        text_content = parsers.parse_text_content(text_bytes)
        assert isinstance(text_content, ResponseTextContent)
        assert text_content.text == "Hello, world!"

    def test_parse_tool_use_content(self, parsers: BedrockParsers) -> None:
        """Test parsing tool use content."""
        tool_use_dict = {
            "type": "tool_use",
            "toolUseId": "tool-1234",
            "name": "get_weather",
            "input": '{"location": "New York"}',
        }

        tool_use_content = parsers.parse_tool_use_content(tool_use_dict)

        assert isinstance(tool_use_content, ResponseToolUseContent)
        assert tool_use_content.tool_call_id == "tool-1234"
        assert tool_use_content.tool_name == "get_weather"
        assert tool_use_content.tool_input == {"location": "New York"}
        assert tool_use_content.tool_input_raw == '{"location": "New York"}'

    def test_parse_content_item(self, parsers: BedrockParsers) -> None:
        """Test parsing content items."""
        # Test with text content
        text_item = {"text": "Hello, world!"}
        content_item = parsers.parse_content_item(text_item)
        assert isinstance(content_item, ResponseTextContent)
        assert content_item.text == "Hello, world!"

        # Test with tool use content
        tool_use_dict = {
            "toolUse": {
                "toolUseId": "tool-1234",
                "name": "get_weather",
                "input": '{"location": "New York"}',
            },
        }
        content_item = parsers.parse_content_item(tool_use_dict)
        assert isinstance(content_item, ResponseToolUseContent)
        assert content_item.tool_call_id == "tool-1234"
        assert content_item.tool_name == "get_weather"

        # Test with unsupported content type
        with pytest.raises(
            ValueError,
            match="Unsupported content type in item:",
        ):
            parsers.parse_content_item({"type": "unsupported"})

    def test_parse_response(self, parsers: BedrockParsers) -> None:
        """Test parsing a complete response."""
        response_dict = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "I'll check the weather for you."},
                        {
                            "toolUse": {
                                "toolUseId": "tool-1234",
                                "name": "get_weather",
                                "input": '{"location": "New York"}',
                            },
                        },
                    ],
                },
            },
            "usage": {
                "inputTokens": 10,
                "outputTokens": 20,
                "totalTokens": 30,
            },
            "metrics": {
                "latencyMs": 500,
            },
        }

        response = parsers.parse_response(response_dict)

        assert isinstance(response, ResponseMessage)
        assert response.role == "agent"
        assert len(response.content) == 2
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == "I'll check the weather for you."
        assert isinstance(response.content[1], ResponseToolUseContent)
        assert response.content[1].tool_name == "get_weather"

    @pytest.mark.asyncio
    async def test_parse_stream_event(self, parsers: BedrockParsers) -> None:
        """Test parsing a stream event."""
        # Mock response for the stream event context
        response = {
            "ResponseMetadata": {
                "RequestId": "test-request-id",
                "HTTPStatusCode": 200,
            },
        }

        # Initialize message state
        message: dict[str, Any] = {}
        last_message: dict[str, Any] = {}

        # Test message start
        message_start_event = {
            "messageStart": {"role": "assistant"},
        }
        deltas = []
        async for delta in parsers.parse_stream_event(
            message_start_event,
            response,
            message,
            last_message,
        ):
            deltas.append(delta)

        assert len(deltas) > 0
        assert message.get("role") == "agent"
