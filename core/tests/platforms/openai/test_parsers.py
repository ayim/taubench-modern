"""Unit tests for the OpenAI platform parsers."""

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
        content = "Hello, world!"
        result = parsers.parse_text_content(content)

        assert isinstance(result, ResponseTextContent)
        assert result.text == "Hello, world!"

    def test_parse_tool_use_content(self, parsers: OpenAIParsers) -> None:
        """Test parsing tool use content."""
        from openai.types.chat.chat_completion_message_tool_call import (
            ChatCompletionMessageToolCall,
            Function,
        )

        content = ChatCompletionMessageToolCall(
            id="test-tool-call-id",
            type="function",
            function=Function(
                name="test-tool",
                arguments='{"key": "value"}',
            ),
        )
        result = parsers.parse_tool_use_content(content)

        assert isinstance(result, ResponseToolUseContent)
        assert result.tool_call_id == "test-tool-call-id"
        assert result.tool_name == "test-tool"
        assert result.tool_input_raw == '{"key": "value"}'

    def test_parse_tool_use_odd_empty_content(self, parsers: OpenAIParsers) -> None:
        """Test parsing of {"":""} as tool use content. This is an odd case I saw
        testing against the actual API. We probably should elide empty keys."""
        from openai.types.chat.chat_completion_message_tool_call import (
            ChatCompletionMessageToolCall,
            Function,
        )

        content = ChatCompletionMessageToolCall(
            id="test-tool-call-id",
            type="function",
            function=Function(
                name="test-tool",
                arguments='{"":""}',
            ),
        )
        result = parsers.parse_tool_use_content(content)

        assert isinstance(result, ResponseToolUseContent)
        assert result.tool_call_id == "test-tool-call-id"
        assert result.tool_name == "test-tool"

        # Also completely empty args we probably should handle as empty obj
        content_2 = ChatCompletionMessageToolCall(
            id="test-tool-call-id",
            type="function",
            function=Function(
                name="test-tool",
                arguments="",
            ),
        )
        result_2 = parsers.parse_tool_use_content(content_2)

        assert isinstance(result_2, ResponseToolUseContent)
        assert result_2.tool_call_id == "test-tool-call-id"
        assert result_2.tool_name == "test-tool"
        assert result_2.tool_input_raw == "{}"

    def test_parse_tool_use_odd_nested_content(self, parsers: OpenAIParsers) -> None:
        """Test parsing of {"function_name": {"args..."}} as tool use content.
        This is an odd case I saw testing against the actual API. We probably
        should elide the function_name in the tool input."""
        from unittest.mock import patch

        from openai.types.chat.chat_completion_message_tool_call import (
            ChatCompletionMessageToolCall,
            Function,
        )

        content = ChatCompletionMessageToolCall(
            id="test-tool-call-id",
            type="function",
            function=Function(
                name="test-tool",
                arguments='{"test-tool": {"key": "value", "key1": 123}}',
            ),
        )
        # Capture logs to check if the warning is produced
        with patch(
            "agent_platform.core.platforms.openai.parsers.logger.warning",
        ) as mock_warning:
            result = parsers.parse_tool_use_content(content)

        assert mock_warning.call_count == 2
        assert "Tool name found in tool input" in mock_warning.call_args_list[0].args[0]
        assert "Un-nesting tool input" in mock_warning.call_args_list[1].args[0]

        assert isinstance(result, ResponseToolUseContent)
        assert result.tool_call_id == "test-tool-call-id"
        assert result.tool_name == "test-tool"
        assert result.tool_input_raw == '{"key": "value", "key1": 123}'

    def test_parse_response(self, parsers: OpenAIParsers) -> None:
        """Test parsing a response."""
        from openai.types.chat import (
            ChatCompletion,
            ChatCompletionMessage,
        )
        from openai.types.chat.chat_completion import Choice
        from openai.types.completion_usage import CompletionUsage

        response = ChatCompletion(
            id="test-completion-id",
            object="chat.completion",
            created=1717171717,
            model="test-model",
            choices=[
                Choice(
                    message=ChatCompletionMessage(
                        role="assistant",
                        content="Hello, world!",
                    ),
                    finish_reason="stop",
                    index=0,
                ),
            ],
            usage=CompletionUsage(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
            ),
        )
        result = parsers.parse_response(response)

        assert isinstance(result, ResponseMessage)
        assert len(result.content) == 1
        assert isinstance(result.content[0], ResponseTextContent)
        assert result.content[0].text == "Hello, world!"
        assert result.role == "agent"
        assert result.raw_response == response

    def test_parse_response_with_tool_call(self, parsers: OpenAIParsers) -> None:
        """Test parsing a response with tool call."""
        from openai.types.chat import (
            ChatCompletion,
            ChatCompletionMessage,
            ChatCompletionMessageToolCall,
        )
        from openai.types.chat.chat_completion import Choice
        from openai.types.chat.chat_completion_message_tool_call import Function
        from openai.types.completion_usage import CompletionUsage

        response = ChatCompletion(
            id="test-completion-id",
            object="chat.completion",
            created=1717171717,
            model="test-model",
            choices=[
                Choice(
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="test-tool-call-id",
                                type="function",
                                function=Function(
                                    name="test-tool",
                                    arguments='{"key": "value"}',
                                ),
                            ),
                        ],
                    ),
                    finish_reason="stop",
                    index=0,
                ),
            ],
            usage=CompletionUsage(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
            ),
        )
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
        from openai.types.chat.chat_completion_chunk import (
            ChatCompletionChunk,
            Choice,
            ChoiceDelta,
        )

        event = ChatCompletionChunk(
            id="test-chunk-id",
            object="chat.completion.chunk",
            created=1717171717,
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    delta=ChoiceDelta(content="Hello, world!"),
                    finish_reason="stop",
                ),
            ],
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
        from openai.types.chat.chat_completion_chunk import (
            ChatCompletionChunk,
            Choice,
            ChoiceDelta,
            ChoiceDeltaToolCall,
            ChoiceDeltaToolCallFunction,
        )

        # Create mock event object
        event = ChatCompletionChunk(
            id="test-chunk-id",
            object="chat.completion.chunk",
            created=1717171717,
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    delta=ChoiceDelta(
                        content="Hello, world!",
                        tool_calls=[
                            ChoiceDeltaToolCall(
                                index=0,
                                id="test-tool-call-id",
                                type="function",
                                function=ChoiceDeltaToolCallFunction(
                                    name="test-tool",
                                    arguments='{"key": "value"}',
                                ),
                            ),
                        ],
                    ),
                    finish_reason="stop",
                ),
            ],
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

        deltas = []
        async for delta in parsers.parse_stream_event(
            event=event,
            message=message,
            last_message=last_message,
        ):
            deltas.append(delta)

        assert len(deltas) > 0
        assert any(
            isinstance(item, dict) and item.get("kind") == "tool_use" for item in message["content"]
        )
