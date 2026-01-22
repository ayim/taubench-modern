import json
from unittest.mock import MagicMock

import pytest

from tau2.data_model.message import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from tau2.environment.tool import Tool, as_tool
from tau2.utils.llm_utils import (
    generate,
    is_anthropic_model,
    parse_anthropic_response,
    parse_responses_api,
    to_litellm_messages_anthropic,
    to_responses_api_input,
    use_responses_api,
)


@pytest.fixture
def model() -> str:
    return "gpt-4o-mini"


@pytest.fixture
def messages() -> list[Message]:
    messages = [
        SystemMessage(role="system", content="You are a helpful assistant."),
        UserMessage(role="user", content="What is the capital of the moon?"),
    ]
    return messages


@pytest.fixture
def tool() -> Tool:
    def calculate_square(x: int) -> int:
        """Calculate the square of a number.
            Args:
            x (int): The number to calculate the square of.
        Returns:
            int: The square of the number.
        """
        return x * x

    return as_tool(calculate_square)


@pytest.fixture
def tool_call_messages() -> list[Message]:
    messages = [
        SystemMessage(role="system", content="You are a helpful assistant."),
        UserMessage(
            role="user",
            content="What is the square of 5? Just give me the number, no explanation.",
        ),
    ]
    return messages


def test_generate_no_tool_call(model: str, messages: list[Message]):
    response = generate(model, messages)
    assert isinstance(response, AssistantMessage)
    assert response.content is not None


def test_generate_tool_call(model: str, tool_call_messages: list[Message], tool: Tool):
    response = generate(model, tool_call_messages, tools=[tool])
    assert isinstance(response, AssistantMessage)
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "calculate_square"
    assert response.tool_calls[0].arguments == {"x": 5}
    follow_up_messages = [
        response,
        ToolMessage(role="tool", id=response.tool_calls[0].id, content="25"),
    ]
    response = generate(
        model,
        tool_call_messages + follow_up_messages,
        tools=[tool],
    )
    assert isinstance(response, AssistantMessage)
    assert response.tool_calls is None
    assert response.content == "25"


# =============================================================================
# Provider Detection Tests
# =============================================================================

class TestProviderDetection:
    def test_is_anthropic_model_claude(self):
        assert is_anthropic_model("claude-3-sonnet") is True
        assert is_anthropic_model("claude-3-opus") is True
        assert is_anthropic_model("Claude-3.5-sonnet") is True  # Case insensitive
    
    def test_is_anthropic_model_bedrock(self):
        assert is_anthropic_model("bedrock/anthropic.claude-3") is True
    
    def test_is_anthropic_model_vertex(self):
        assert is_anthropic_model("vertex_ai/claude-3-sonnet") is True
    
    def test_is_anthropic_model_false(self):
        assert is_anthropic_model("gpt-4") is False
        assert is_anthropic_model("o1-preview") is False
    
    def test_use_responses_api_flag(self):
        assert use_responses_api("gpt-4", config_flag=True) is True
        assert use_responses_api("gpt-4", config_flag=False) is False
    
    def test_use_responses_api_o_models(self):
        assert use_responses_api("o1-preview", config_flag=False) is True
        assert use_responses_api("o3-mini", config_flag=False) is True


# =============================================================================
# Anthropic Extended Thinking Tests
# =============================================================================

class TestAnthropicParsing:
    def test_parse_anthropic_response_simple_string(self):
        """Test parsing when content is a simple string (non-extended-thinking)."""
        mock_response = MagicMock()
        mock_response.content = "Hello, world!"
        mock_response.tool_calls = None
        
        result = parse_anthropic_response(
            response_message=mock_response,
            cost=0.001,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            raw_response_dict={"test": "data"},
        )
        
        assert result.content == "Hello, world!"
        assert result.tool_calls is None
        assert result.raw_content_blocks is None  # Not set for simple strings
    
    def test_parse_anthropic_response_with_thinking_blocks(self):
        """Test parsing with extended thinking content blocks."""
        content_blocks = [
            {"type": "thinking", "thinking": "Let me think about this...", "signature": "abc123"},
            {"type": "text", "text": "The answer is 42."},
        ]
        
        mock_response = MagicMock()
        mock_response.content = content_blocks
        
        result = parse_anthropic_response(
            response_message=mock_response,
            cost=0.002,
            usage={"prompt_tokens": 20, "completion_tokens": 15},
            raw_response_dict={"test": "data"},
        )
        
        assert result.content == "The answer is 42."
        assert result.raw_content_blocks == content_blocks
        assert result.tool_calls is None
    
    def test_parse_anthropic_response_with_tool_use(self):
        """Test parsing with tool_use blocks."""
        content_blocks = [
            {"type": "thinking", "thinking": "I need to call a tool.", "signature": "xyz789"},
            {"type": "text", "text": "Let me look that up."},
            {"type": "tool_use", "id": "tool_1", "name": "get_user", "input": {"user_id": "123"}},
        ]
        
        mock_response = MagicMock()
        mock_response.content = content_blocks
        
        result = parse_anthropic_response(
            response_message=mock_response,
            cost=0.003,
            usage=None,
            raw_response_dict={},
        )
        
        assert result.content == "Let me look that up."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "tool_1"
        assert result.tool_calls[0].name == "get_user"
        assert result.tool_calls[0].arguments == {"user_id": "123"}
        assert result.tool_calls[0].arguments_raw == '{"user_id":"123"}'
        assert result.raw_content_blocks == content_blocks
    
    def test_parse_anthropic_response_with_redacted_thinking(self):
        """Test parsing with redacted_thinking blocks (preserved verbatim)."""
        content_blocks = [
            {"type": "redacted_thinking", "data": "base64encodeddata"},
            {"type": "text", "text": "Based on my analysis..."},
        ]
        
        mock_response = MagicMock()
        mock_response.content = content_blocks
        
        result = parse_anthropic_response(
            response_message=mock_response,
            cost=0.001,
            usage=None,
            raw_response_dict={},
        )
        
        assert result.content == "Based on my analysis..."
        # redacted_thinking should be preserved in raw_content_blocks
        assert result.raw_content_blocks == content_blocks


class TestAnthropicSerialization:
    def test_to_litellm_messages_anthropic_with_raw_blocks(self):
        """Test that raw_content_blocks are replayed verbatim."""
        raw_blocks = [
            {"type": "thinking", "thinking": "My reasoning...", "signature": "sig123"},
            {"type": "text", "text": "The answer."},
        ]
        
        messages = [
            SystemMessage(role="system", content="You are helpful."),
            UserMessage(role="user", content="What is 2+2?"),
            AssistantMessage(
                role="assistant",
                content="The answer.",
                raw_content_blocks=raw_blocks,
            ),
        ]
        
        result = to_litellm_messages_anthropic(messages)
        
        assert len(result) == 3
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1] == {"role": "user", "content": "What is 2+2?"}
        # Assistant message should have raw_content_blocks replayed verbatim
        assert result[2] == {"role": "assistant", "content": raw_blocks}
    
    def test_to_litellm_messages_anthropic_tool_results(self):
        """Test that tool results are batched into user messages."""
        messages = [
            UserMessage(role="user", content="Get user info"),
            AssistantMessage(
                role="assistant",
                content="Looking up user.",
                tool_calls=[ToolCall(id="tool_1", name="get_user", arguments={"user_id": "123"})],
            ),
            ToolMessage(role="tool", id="tool_1", content='{"name": "John"}'),
        ]
        
        result = to_litellm_messages_anthropic(messages)
        
        assert len(result) == 3
        assert result[0] == {"role": "user", "content": "Get user info"}
        # Tool results should be in a user message with tool_result blocks
        assert result[2]["role"] == "user"
        assert result[2]["content"][0]["type"] == "tool_result"
        assert result[2]["content"][0]["tool_use_id"] == "tool_1"


# =============================================================================
# OpenAI Responses API Tests
# =============================================================================

class TestResponsesApiParsing:
    def test_parse_responses_api_simple_message(self):
        """Test parsing a simple message from Responses API."""
        mock_response = MagicMock()
        mock_response.output = [
            {"type": "message", "id": "msg_1", "role": "assistant", 
             "content": [{"type": "output_text", "text": "Hello!"}]}
        ]
        mock_response.usage = None
        
        result = parse_responses_api(mock_response, cost=0.001)
        
        assert result.content == "Hello!"
        assert result.tool_calls is None
        assert result.raw_output_items == mock_response.output
    
    def test_parse_responses_api_with_reasoning(self):
        """Test parsing with reasoning items (preserved verbatim)."""
        output_items = [
            {"type": "reasoning", "id": "rs_1", "content": [{"type": "text", "text": "thinking..."}]},
            {"type": "message", "id": "msg_1", "role": "assistant",
             "content": [{"type": "output_text", "text": "The answer is 42."}]},
        ]
        
        mock_response = MagicMock()
        mock_response.output = output_items
        mock_response.usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        
        result = parse_responses_api(mock_response, cost=0.002)
        
        assert result.content == "The answer is 42."
        # reasoning items should be preserved in raw_output_items
        assert result.raw_output_items == output_items
        assert result.usage == {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
    
    def test_parse_responses_api_with_function_calls(self):
        """Test parsing with function_call items."""
        output_items = [
            {"type": "message", "id": "msg_1", "role": "assistant",
             "content": [{"type": "output_text", "text": "Let me look that up."}]},
            {"type": "function_call", "id": "fc_1", "call_id": "call_123",
             "name": "get_user", "arguments": '{"user_id":"123"}', "status": "completed"},
        ]
        
        mock_response = MagicMock()
        mock_response.output = output_items
        mock_response.usage = None
        
        result = parse_responses_api(mock_response, cost=0.003)
        
        assert result.content == "Let me look that up."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "call_123"  # Uses call_id
        assert result.tool_calls[0].name == "get_user"
        assert result.tool_calls[0].arguments == {"user_id": "123"}
        assert result.tool_calls[0].arguments_raw == '{"user_id":"123"}'
    
    def test_parse_responses_api_multiple_function_calls(self):
        """Test parsing with multiple parallel function calls."""
        output_items = [
            {"type": "function_call", "id": "fc_1", "call_id": "call_1",
             "name": "get_user", "arguments": '{"user_id":"1"}'},
            {"type": "function_call", "id": "fc_2", "call_id": "call_2",
             "name": "get_order", "arguments": '{"order_id":"99"}'},
        ]
        
        mock_response = MagicMock()
        mock_response.output = output_items
        mock_response.usage = None
        
        result = parse_responses_api(mock_response, cost=0.004)
        
        assert result.content is None
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].id == "call_1"
        assert result.tool_calls[1].id == "call_2"


class TestResponsesApiSerialization:
    def test_to_responses_api_input_basic(self):
        """Test basic message conversion to Responses API input."""
        messages = [
            SystemMessage(role="system", content="You are helpful."),
            UserMessage(role="user", content="Hello"),
        ]
        
        result = to_responses_api_input(messages)
        
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1] == {"role": "user", "content": "Hello"}
    
    def test_to_responses_api_input_with_raw_output_items(self):
        """Test that raw_output_items are replayed verbatim."""
        raw_items = [
            {"type": "reasoning", "id": "rs_1", "content": [{"type": "text", "text": "thinking..."}]},
            {"type": "message", "id": "msg_1", "role": "assistant",
             "content": [{"type": "output_text", "text": "The answer."}]},
        ]
        
        messages = [
            UserMessage(role="user", content="What is 2+2?"),
            AssistantMessage(role="assistant", content="The answer.", raw_output_items=raw_items),
        ]
        
        result = to_responses_api_input(messages)
        
        assert len(result) == 3  # user message + 2 output items replayed
        assert result[0] == {"role": "user", "content": "What is 2+2?"}
        # raw_output_items should be extended into the result
        assert result[1] == raw_items[0]
        assert result[2] == raw_items[1]
    
    def test_to_responses_api_input_tool_results(self):
        """Test tool result conversion to function_call_output."""
        messages = [
            UserMessage(role="user", content="Get user"),
            ToolMessage(role="tool", id="call_123", content='{"name": "John"}'),
        ]
        
        result = to_responses_api_input(messages)
        
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Get user"}
        assert result[1] == {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": '{"name": "John"}',
        }
