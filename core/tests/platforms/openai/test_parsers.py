"""Unit tests for the OpenAI platform parsers."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.platforms.openai.parsers import OpenAIParsers
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
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
            "text": "Hello, world!",
        }
        result = parsers.parse_text_content(content)

        assert isinstance(result, ResponseTextContent)
        assert result.text == "Hello, world!"

    def test_parse_image_content_not_implemented(self, parsers: OpenAIParsers) -> None:
        """Test parsing image content."""
        # This is expected to fail until image content is supported
        content = {
            "type": "image_url",
            "image_url": {
                "url": "base64_encoded_image",
            },
        }
        with pytest.raises(
            NotImplementedError,
            match="Image content not supported yet",
        ):
            parsers.parse_image_content(content)

    def test_parse_tool_use_content(self, parsers: OpenAIParsers) -> None:
        """Test parsing tool use content."""
        content = {
            "id": "test-tool-call-id",
            "function": {
                "name": "test-tool",
                "arguments": '{"key": "value"}',
            },
        }
        result = parsers.parse_tool_use_content(content)

        assert isinstance(result, ResponseToolUseContent)
        assert result.tool_call_id == "test-tool-call-id"
        assert result.tool_name == "test-tool"
        assert result.tool_input_raw == '{"key": "value"}'

    def test_parse_document_content_not_implemented(
        self,
        parsers: OpenAIParsers,
    ) -> None:
        """Test parsing document content."""
        # This is expected to fail until document content is supported
        content = {
            "type": "file",
            "file": {
                "name": "test.pdf",
                "url": "https://example.com/test.pdf",
            },
        }
        with pytest.raises(
            NotImplementedError,
            match="Document content not supported yet",
        ):
            parsers.parse_document_content(content)

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
        with pytest.raises(ValueError, match="Unsupported content type in item:"):
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
        assert len(result.content) == 1
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
        assert len(result.content) == 1
        assert isinstance(result.content[0], ResponseToolUseContent)
        assert result.content[0].tool_call_id == "test-tool-call-id"
        assert result.content[0].tool_name == "test-tool"
        assert result.content[0].tool_input_raw == '{"key": "value"}'
        assert result.role == "agent"
        assert result.raw_response == response

    @pytest.mark.asyncio
    async def test_parse_stream_event(self, parsers: OpenAIParsers) -> None:
        """Test parsing a stream event."""

        # Create a mock object with correct structure for parse_stream_event
        class Delta:
            content = "Hello, world!"

        class Choice:
            delta = Delta()

        event = MagicMock()
        event.choices = [Choice()]

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

        deltas = []
        async for delta in parsers.parse_stream_event(
            event=event,
            message=message,
            last_message=last_message,
        ):
            deltas.append(delta)

        # Check that deltas were produced and the text was added to the message
        assert len(deltas) > 0
        assert all(isinstance(d, GenericDelta) for d in deltas)
        assert any(
            item.get("text") == "Hello, world!"
            for item in message["content"]
            if isinstance(item, dict) and "text" in item
        )

    @pytest.mark.asyncio
    async def test_parse_stream_event_with_tool_call(
        self,
        parsers: OpenAIParsers,
    ) -> None:
        """Test parsing a stream event with tool call."""

        # Create mock function object
        class Function:
            name = "test-tool"
            arguments = '{"key": "value"}'

        # Create mock tool call object
        class ToolCall:
            id = "test-tool-call-id"
            function = Function()

        # Create mock delta object
        class Delta:
            content = None

            @property
            def tool_calls(self):
                return [ToolCall()]

        # Create mock choice object
        class Choice:
            delta = Delta()

        # Create mock event object
        event = MagicMock()
        event.choices = [Choice()]

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

        deltas = []
        async for delta in parsers.parse_stream_event(
            event=event,
            message=message,
            last_message=last_message,
        ):
            deltas.append(delta)

        assert len(deltas) > 0
        assert any(
            isinstance(item, dict) and item.get("kind") == "tool_use"
            for item in message["content"]
        )
