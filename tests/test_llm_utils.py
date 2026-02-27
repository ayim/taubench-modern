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
        mock_response.thinking_blocks = None
        
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
        mock_response.thinking_blocks = None
        mock_response.tool_calls = None

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
        mock_response.thinking_blocks = None
        mock_response.tool_calls = None

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
        mock_response.thinking_blocks = None
        mock_response.tool_calls = None

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


# =============================================================================
# Serialization Round-Trip Tests (JSON save/load)
# =============================================================================

class TestSerializationRoundTrip:
    """Tests proving that raw payload fields survive JSON serialization (saving simulations)."""
    
    def test_assistant_message_with_raw_content_blocks_roundtrip(self):
        """Anthropic raw_content_blocks survives JSON round-trip exactly."""
        raw_blocks = [
            {"type": "thinking", "thinking": "Let me analyze this step by step...", "signature": "abc123xyz"},
            {"type": "redacted_thinking", "data": "base64encodeddatahere"},
            {"type": "text", "text": "The answer is 42."},
            {"type": "tool_use", "id": "toolu_01", "name": "get_user", "input": {"user_id": "123", "include_details": True}},
        ]
        
        original = AssistantMessage(
            role="assistant",
            content="The answer is 42.",
            tool_calls=[ToolCall(
                id="toolu_01",
                name="get_user",
                arguments={"user_id": "123", "include_details": True},
                arguments_raw='{"user_id":"123","include_details":true}',
            )],
            raw_content_blocks=raw_blocks,
            cost=0.005,
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )
        
        # Serialize to JSON (what happens when saving simulations)
        json_str = original.model_dump_json()
        
        # Deserialize from JSON (what happens when loading simulations)
        loaded = AssistantMessage.model_validate_json(json_str)
        
        # Verify exact preservation
        assert loaded.raw_content_blocks == raw_blocks
        assert loaded.content == "The answer is 42."
        assert loaded.cost == 0.005
        
        # Verify thinking block signature is preserved exactly
        thinking_block = loaded.raw_content_blocks[0]
        assert thinking_block["type"] == "thinking"
        assert thinking_block["signature"] == "abc123xyz"
        
        # Verify redacted_thinking is preserved
        redacted_block = loaded.raw_content_blocks[1]
        assert redacted_block["type"] == "redacted_thinking"
        assert redacted_block["data"] == "base64encodeddatahere"
    
    def test_assistant_message_with_raw_output_items_roundtrip(self):
        """OpenAI Responses API raw_output_items survives JSON round-trip exactly."""
        raw_items = [
            {"type": "reasoning", "id": "rs_abc123", "summary": [{"type": "summary_text", "text": "Analyzed the request..."}]},
            {"type": "message", "id": "msg_def456", "role": "assistant",
             "content": [{"type": "output_text", "text": "Here's the answer."}]},
            {"type": "function_call", "id": "fc_ghi789", "call_id": "call_xyz",
             "name": "search", "arguments": '{"query":"test"}', "status": "completed"},
        ]
        
        original = AssistantMessage(
            role="assistant",
            content="Here's the answer.",
            tool_calls=[ToolCall(
                id="call_xyz",
                name="search",
                arguments={"query": "test"},
                arguments_raw='{"query":"test"}',
            )],
            raw_output_items=raw_items,
            usage={"input_tokens": 200, "output_tokens": 100},
        )
        
        # Round-trip through JSON
        json_str = original.model_dump_json()
        loaded = AssistantMessage.model_validate_json(json_str)
        
        # Verify exact preservation
        assert loaded.raw_output_items == raw_items
        assert loaded.content == "Here's the answer."
        
        # Verify reasoning item is preserved
        reasoning_item = loaded.raw_output_items[0]
        assert reasoning_item["type"] == "reasoning"
        assert reasoning_item["id"] == "rs_abc123"
        
        # Verify function_call item is preserved with all fields
        fc_item = loaded.raw_output_items[2]
        assert fc_item["type"] == "function_call"
        assert fc_item["call_id"] == "call_xyz"
        assert fc_item["arguments"] == '{"query":"test"}'
    
    def test_tool_call_with_arguments_raw_roundtrip(self):
        """arguments_raw string survives round-trip and preserves exact formatting."""
        # Original JSON with specific formatting
        original_args_raw = '{"user_id":"123","options":{"verbose":true,"limit":10}}'
        
        original = ToolCall(
            id="call_123",
            name="get_data",
            arguments={"user_id": "123", "options": {"verbose": True, "limit": 10}},
            arguments_raw=original_args_raw,
        )
        
        # Round-trip
        json_str = original.model_dump_json()
        loaded = ToolCall.model_validate_json(json_str)
        
        # Verify arguments_raw is preserved exactly (not re-serialized)
        assert loaded.arguments_raw == original_args_raw
        assert loaded.arguments == {"user_id": "123", "options": {"verbose": True, "limit": 10}}
    
    def test_assistant_message_with_multiple_tool_calls_roundtrip(self):
        """Multiple tool calls with arguments_raw all survive round-trip."""
        tool_calls = [
            ToolCall(id="call_1", name="get_user", arguments={"id": "1"}, arguments_raw='{"id":"1"}'),
            ToolCall(id="call_2", name="get_order", arguments={"id": "99"}, arguments_raw='{"id":"99"}'),
            ToolCall(id="call_3", name="get_product", arguments={"sku": "ABC"}, arguments_raw='{"sku":"ABC"}'),
        ]
        
        original = AssistantMessage(
            role="assistant",
            content=None,
            tool_calls=tool_calls,
        )
        
        # Round-trip
        json_str = original.model_dump_json()
        loaded = AssistantMessage.model_validate_json(json_str)
        
        assert len(loaded.tool_calls) == 3
        for i, tc in enumerate(loaded.tool_calls):
            assert tc.id == tool_calls[i].id
            assert tc.name == tool_calls[i].name
            assert tc.arguments == tool_calls[i].arguments
            assert tc.arguments_raw == tool_calls[i].arguments_raw


# =============================================================================
# Message Conversion Replay Tests
# =============================================================================

class TestMessageConversionReplay:
    """Tests proving that raw fields are used when converting messages back to provider format."""
    
    def test_anthropic_raw_blocks_replayed_exactly_not_reconstructed(self):
        """Raw content blocks are replayed verbatim, not reconstructed from derived fields."""
        # Raw blocks with specific structure that would be lost if reconstructed
        raw_blocks = [
            {"type": "thinking", "thinking": "Step 1: Consider the problem\nStep 2: Analyze options", "signature": "sig_abc123"},
            {"type": "redacted_thinking", "data": "cmVkYWN0ZWRfZGF0YQ=="},
            {"type": "text", "text": "First part of answer."},
            {"type": "text", "text": "Second part of answer."},  # Multiple text blocks!
            {"type": "tool_use", "id": "toolu_01", "name": "search", "input": {"q": "test", "limit": 5}},
        ]
        
        # The derived content would lose the separation between text blocks
        msg = AssistantMessage(
            role="assistant",
            content="First part of answer.\nSecond part of answer.",  # Concatenated
            tool_calls=[ToolCall(id="toolu_01", name="search", arguments={"q": "test", "limit": 5})],
            raw_content_blocks=raw_blocks,
        )
        
        result = to_litellm_messages_anthropic([msg])
        
        # The key assertion: raw_blocks are replayed exactly, not reconstructed
        assert result[0]["content"] == raw_blocks
        # Note: We check equality, not identity, as Pydantic may make copies
        
        # Verify all original blocks are present with exact values
        assert len(result[0]["content"]) == 5
        assert result[0]["content"][0]["type"] == "thinking"
        assert result[0]["content"][0]["signature"] == "sig_abc123"
        assert result[0]["content"][1]["type"] == "redacted_thinking"
        # Two separate text blocks, not merged
        assert result[0]["content"][2]["type"] == "text"
        assert result[0]["content"][3]["type"] == "text"
    
    def test_responses_api_raw_items_replayed_exactly(self):
        """Raw output items are replayed verbatim, preserving reasoning items."""
        raw_items = [
            {"type": "reasoning", "id": "rs_001", "summary": [{"type": "summary_text", "text": "Thinking deeply..."}]},
            {"type": "message", "id": "msg_002", "role": "assistant", 
             "content": [{"type": "output_text", "text": "The result is 42."}]},
        ]
        
        msg = AssistantMessage(
            role="assistant",
            content="The result is 42.",
            raw_output_items=raw_items,
        )
        
        result = to_responses_api_input([msg])
        
        # Raw items should be extended into result (2 items)
        assert len(result) == 2
        assert result[0] == raw_items[0]  # Reasoning item
        assert result[1] == raw_items[1]  # Message item
        
        # Verify reasoning is present (would be lost without raw replay)
        assert result[0]["type"] == "reasoning"
        assert result[0]["id"] == "rs_001"
    
    def test_anthropic_fallback_without_raw_blocks(self):
        """Without raw_content_blocks, falls back to reconstructing from content."""
        msg = AssistantMessage(
            role="assistant",
            content="Simple answer without raw blocks.",
            tool_calls=None,
            raw_content_blocks=None,  # No raw blocks
        )
        
        result = to_litellm_messages_anthropic([msg])
        
        # Falls back to simple content string
        assert result[0]["content"] == "Simple answer without raw blocks."
    
    def test_responses_api_fallback_without_raw_items(self):
        """Without raw_output_items, falls back to simple assistant message."""
        msg = AssistantMessage(
            role="assistant",
            content="Simple answer.",
            raw_output_items=None,  # No raw items
        )
        
        result = to_responses_api_input([msg])
        
        # Falls back to role-based message
        assert result[0] == {"role": "assistant", "content": "Simple answer."}
    
    def test_serialization_then_conversion_preserves_raw(self):
        """Full flow: create message -> serialize -> deserialize -> convert to provider format."""
        raw_blocks = [
            {"type": "thinking", "thinking": "Analysis...", "signature": "sig999"},
            {"type": "text", "text": "Final answer."},
        ]
        
        # Step 1: Create original message
        original = AssistantMessage(
            role="assistant",
            content="Final answer.",
            raw_content_blocks=raw_blocks,
        )
        
        # Step 2: Serialize (save simulation)
        json_str = original.model_dump_json()
        
        # Step 3: Deserialize (load simulation)
        loaded = AssistantMessage.model_validate_json(json_str)
        
        # Step 4: Convert to provider format (replay conversation)
        result = to_litellm_messages_anthropic([loaded])
        
        # Verify raw blocks survived the entire journey
        assert result[0]["content"] == raw_blocks
        assert result[0]["content"][0]["signature"] == "sig999"


# =============================================================================
# Multi-Turn Conversation Tests
# =============================================================================

class TestMultiTurnRawPreservation:
    """Tests proving raw fields are preserved across realistic multi-turn conversations."""
    
    def test_anthropic_multi_turn_tool_calling_full_roundtrip(self):
        """
        Full conversation flow with Anthropic extended thinking:
        user -> assistant(thinking+tool_use) -> tool_result -> assistant(thinking+text)
        
        Serialize entire conversation, deserialize, convert to LiteLLM format.
        All thinking blocks and signatures must be preserved.
        """
        # Turn 1: User asks a question
        user_msg = UserMessage(role="user", content="What's the weather in NYC?")
        
        # Turn 2: Assistant with thinking and tool call
        assistant_raw_blocks_1 = [
            {"type": "thinking", "thinking": "User wants weather info. I should use the weather API.", "signature": "sig_turn1"},
            {"type": "text", "text": "Let me check the weather for you."},
            {"type": "tool_use", "id": "toolu_weather", "name": "get_weather", "input": {"city": "NYC"}},
        ]
        assistant_msg_1 = AssistantMessage(
            role="assistant",
            content="Let me check the weather for you.",
            tool_calls=[ToolCall(id="toolu_weather", name="get_weather", arguments={"city": "NYC"}, arguments_raw='{"city":"NYC"}')],
            raw_content_blocks=assistant_raw_blocks_1,
        )
        
        # Turn 3: Tool result
        tool_msg = ToolMessage(role="tool", id="toolu_weather", content='{"temp": 72, "condition": "sunny"}')
        
        # Turn 4: Assistant with thinking and final answer
        assistant_raw_blocks_2 = [
            {"type": "thinking", "thinking": "Got the weather data. Temperature is 72F and sunny.", "signature": "sig_turn2"},
            {"type": "text", "text": "The weather in NYC is 72°F and sunny!"},
        ]
        assistant_msg_2 = AssistantMessage(
            role="assistant",
            content="The weather in NYC is 72°F and sunny!",
            raw_content_blocks=assistant_raw_blocks_2,
        )
        
        # Full conversation
        conversation = [user_msg, assistant_msg_1, tool_msg, assistant_msg_2]
        
        # Serialize entire conversation (simulating save)
        serialized = [msg.model_dump_json() for msg in conversation]
        
        # Deserialize (simulating load)
        loaded_conversation = []
        for i, json_str in enumerate(serialized):
            if i == 0:
                loaded_conversation.append(UserMessage.model_validate_json(json_str))
            elif i == 2:
                loaded_conversation.append(ToolMessage.model_validate_json(json_str))
            else:
                loaded_conversation.append(AssistantMessage.model_validate_json(json_str))
        
        # Convert to LiteLLM format (simulating API call)
        result = to_litellm_messages_anthropic(loaded_conversation)
        
        # Verify all messages present
        assert len(result) == 4
        
        # Verify first assistant message has raw blocks with signature
        assert result[1]["content"] == assistant_raw_blocks_1
        assert result[1]["content"][0]["signature"] == "sig_turn1"
        
        # Verify tool result is properly formatted
        assert result[2]["role"] == "user"
        assert result[2]["content"][0]["type"] == "tool_result"
        assert result[2]["content"][0]["tool_use_id"] == "toolu_weather"
        
        # Verify second assistant message has raw blocks with signature
        assert result[3]["content"] == assistant_raw_blocks_2
        assert result[3]["content"][0]["signature"] == "sig_turn2"
    
    def test_responses_api_multi_turn_with_reasoning_full_roundtrip(self):
        """
        Full conversation flow with OpenAI Responses API:
        user -> assistant(reasoning+message+function_call) -> function_call_output -> assistant(reasoning+message)
        
        Serialize, deserialize, convert to Responses API input.
        Reasoning items must be preserved for behavioral consistency.
        """
        # Turn 1: User asks
        user_msg = UserMessage(role="user", content="Search for 'Python tutorials'")
        
        # Turn 2: Assistant with reasoning and function call
        assistant_raw_items_1 = [
            {"type": "reasoning", "id": "rs_001", "summary": [{"type": "summary_text", "text": "Need to search for tutorials"}]},
            {"type": "message", "id": "msg_001", "role": "assistant",
             "content": [{"type": "output_text", "text": "I'll search for that."}]},
            {"type": "function_call", "id": "fc_001", "call_id": "call_search",
             "name": "web_search", "arguments": '{"query":"Python tutorials"}', "status": "completed"},
        ]
        assistant_msg_1 = AssistantMessage(
            role="assistant",
            content="I'll search for that.",
            tool_calls=[ToolCall(id="call_search", name="web_search", arguments={"query": "Python tutorials"}, arguments_raw='{"query":"Python tutorials"}')],
            raw_output_items=assistant_raw_items_1,
        )
        
        # Turn 3: Tool result
        tool_msg = ToolMessage(role="tool", id="call_search", content='{"results": ["tutorial1.com", "tutorial2.com"]}')
        
        # Turn 4: Assistant with reasoning and final message
        assistant_raw_items_2 = [
            {"type": "reasoning", "id": "rs_002", "summary": [{"type": "summary_text", "text": "Found good results"}]},
            {"type": "message", "id": "msg_002", "role": "assistant",
             "content": [{"type": "output_text", "text": "Here are the top Python tutorials!"}]},
        ]
        assistant_msg_2 = AssistantMessage(
            role="assistant",
            content="Here are the top Python tutorials!",
            raw_output_items=assistant_raw_items_2,
        )
        
        # Full conversation
        conversation = [user_msg, assistant_msg_1, tool_msg, assistant_msg_2]
        
        # Serialize
        serialized = [msg.model_dump_json() for msg in conversation]
        
        # Deserialize
        loaded_conversation = []
        for i, json_str in enumerate(serialized):
            if i == 0:
                loaded_conversation.append(UserMessage.model_validate_json(json_str))
            elif i == 2:
                loaded_conversation.append(ToolMessage.model_validate_json(json_str))
            else:
                loaded_conversation.append(AssistantMessage.model_validate_json(json_str))
        
        # Convert to Responses API input
        result = to_responses_api_input(loaded_conversation)
        
        # user_msg + 3 items from assistant_1 + function_call_output + 2 items from assistant_2
        assert len(result) == 7
        
        # User message
        assert result[0] == {"role": "user", "content": "Search for 'Python tutorials'"}
        
        # First assistant's raw items replayed
        assert result[1]["type"] == "reasoning"
        assert result[1]["id"] == "rs_001"
        assert result[2]["type"] == "message"
        assert result[3]["type"] == "function_call"
        assert result[3]["call_id"] == "call_search"
        
        # Tool result as function_call_output
        assert result[4] == {
            "type": "function_call_output",
            "call_id": "call_search",
            "output": '{"results": ["tutorial1.com", "tutorial2.com"]}',
        }
        
        # Second assistant's raw items replayed
        assert result[5]["type"] == "reasoning"
        assert result[5]["id"] == "rs_002"
        assert result[6]["type"] == "message"
    
    def test_anthropic_parallel_tool_calls_roundtrip(self):
        """Test conversation with parallel tool calls (multiple tool_use in one turn)."""
        # Assistant calls multiple tools at once
        raw_blocks = [
            {"type": "thinking", "thinking": "I need to get both user and order info.", "signature": "sig_parallel"},
            {"type": "tool_use", "id": "toolu_user", "name": "get_user", "input": {"id": "123"}},
            {"type": "tool_use", "id": "toolu_order", "name": "get_order", "input": {"id": "456"}},
        ]
        
        assistant_msg = AssistantMessage(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(id="toolu_user", name="get_user", arguments={"id": "123"}, arguments_raw='{"id":"123"}'),
                ToolCall(id="toolu_order", name="get_order", arguments={"id": "456"}, arguments_raw='{"id":"456"}'),
            ],
            raw_content_blocks=raw_blocks,
        )
        
        # Multiple tool results
        tool_msg_1 = ToolMessage(role="tool", id="toolu_user", content='{"name": "Alice"}')
        tool_msg_2 = ToolMessage(role="tool", id="toolu_order", content='{"total": 99.99}')
        
        conversation = [
            UserMessage(role="user", content="Get user 123 and order 456"),
            assistant_msg,
            tool_msg_1,
            tool_msg_2,
        ]
        
        # Serialize and deserialize
        serialized = [msg.model_dump_json() for msg in conversation]
        loaded = [
            UserMessage.model_validate_json(serialized[0]),
            AssistantMessage.model_validate_json(serialized[1]),
            ToolMessage.model_validate_json(serialized[2]),
            ToolMessage.model_validate_json(serialized[3]),
        ]
        
        # Convert to provider format
        result = to_litellm_messages_anthropic(loaded)
        
        # Verify parallel tool_use blocks preserved
        assert len(result[1]["content"]) == 3  # thinking + 2 tool_use
        assert result[1]["content"][0]["type"] == "thinking"
        assert result[1]["content"][0]["signature"] == "sig_parallel"
        assert result[1]["content"][1]["type"] == "tool_use"
        assert result[1]["content"][2]["type"] == "tool_use"
        
        # Verify both tool results in same user message
        assert result[2]["role"] == "user"
        assert len(result[2]["content"]) == 2  # Two tool_result blocks
        assert result[2]["content"][0]["tool_use_id"] == "toolu_user"
        assert result[2]["content"][1]["tool_use_id"] == "toolu_order"


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestSerializationEdgeCases:
    """Tests for edge cases and backwards compatibility."""
    
    def test_legacy_message_without_raw_fields_roundtrip(self):
        """Messages created before raw field support still work correctly."""
        # Legacy message - no raw fields
        legacy_msg = AssistantMessage(
            role="assistant",
            content="This is a legacy message without raw fields.",
            tool_calls=None,
            # raw_content_blocks and raw_output_items are None by default
        )
        
        # Round-trip
        json_str = legacy_msg.model_dump_json()
        loaded = AssistantMessage.model_validate_json(json_str)
        
        assert loaded.content == "This is a legacy message without raw fields."
        assert loaded.raw_content_blocks is None
        assert loaded.raw_output_items is None
        
        # Should work with Anthropic conversion (fallback path)
        result = to_litellm_messages_anthropic([loaded])
        assert result[0]["content"] == "This is a legacy message without raw fields."
        
        # Should work with Responses API conversion (fallback path)
        result = to_responses_api_input([loaded])
        assert result[0] == {"role": "assistant", "content": "This is a legacy message without raw fields."}
    
    def test_mixed_messages_with_and_without_raw_fields(self):
        """Conversation mixing raw-enabled and legacy messages."""
        # Some messages have raw fields, some don't
        conversation = [
            UserMessage(role="user", content="Hello"),
            AssistantMessage(
                role="assistant",
                content="Response 1",
                raw_content_blocks=[{"type": "text", "text": "Response 1"}],  # Has raw
            ),
            UserMessage(role="user", content="Follow up"),
            AssistantMessage(
                role="assistant",
                content="Response 2",
                raw_content_blocks=None,  # No raw (legacy)
            ),
            UserMessage(role="user", content="Another question"),
            AssistantMessage(
                role="assistant",
                content="Response 3",
                raw_content_blocks=[
                    {"type": "thinking", "thinking": "...", "signature": "sig"},
                    {"type": "text", "text": "Response 3"},
                ],  # Has raw with thinking
            ),
        ]
        
        # Convert to Anthropic format
        result = to_litellm_messages_anthropic(conversation)
        
        # First assistant: uses raw_content_blocks
        assert result[1]["content"] == [{"type": "text", "text": "Response 1"}]
        
        # Second assistant: falls back to simple content
        assert result[3]["content"] == "Response 2"
        
        # Third assistant: uses raw_content_blocks with thinking
        assert result[5]["content"][0]["type"] == "thinking"
        assert result[5]["content"][0]["signature"] == "sig"
    
    def test_nested_json_in_tool_arguments_roundtrip(self):
        """Complex nested JSON in tool arguments is preserved exactly."""
        # Complex nested structure
        complex_args = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"title": "test"}},
                        {"range": {"date": {"gte": "2024-01-01", "lte": "2024-12-31"}}},
                    ],
                    "filter": [
                        {"term": {"status": "active"}},
                    ],
                }
            },
            "options": {
                "size": 10,
                "from": 0,
                "sort": [{"date": "desc"}, {"_score": "desc"}],
            },
        }
        
        # Specific JSON formatting we want to preserve
        args_raw = json.dumps(complex_args, separators=(',', ':'))
        
        tool_call = ToolCall(
            id="call_complex",
            name="search",
            arguments=complex_args,
            arguments_raw=args_raw,
        )
        
        msg = AssistantMessage(
            role="assistant",
            content=None,
            tool_calls=[tool_call],
        )
        
        # Round-trip
        json_str = msg.model_dump_json()
        loaded = AssistantMessage.model_validate_json(json_str)
        
        # Verify complex structure preserved
        assert loaded.tool_calls[0].arguments == complex_args
        assert loaded.tool_calls[0].arguments_raw == args_raw
        
        # Nested structure accessible
        assert loaded.tool_calls[0].arguments["query"]["bool"]["must"][0]["match"]["title"] == "test"
    
    def test_empty_content_with_raw_blocks(self):
        """Message with empty/None content but valid raw_content_blocks."""
        raw_blocks = [
            {"type": "thinking", "thinking": "Processing silently...", "signature": "sig_silent"},
            {"type": "tool_use", "id": "toolu_1", "name": "action", "input": {}},
        ]
        
        msg = AssistantMessage(
            role="assistant",
            content=None,  # No text content
            tool_calls=[ToolCall(id="toolu_1", name="action", arguments={})],
            raw_content_blocks=raw_blocks,
        )
        
        # Round-trip
        json_str = msg.model_dump_json()
        loaded = AssistantMessage.model_validate_json(json_str)
        
        assert loaded.content is None
        assert loaded.raw_content_blocks == raw_blocks
        
        # Convert to provider format
        result = to_litellm_messages_anthropic([loaded])
        assert result[0]["content"] == raw_blocks
    
    def test_unicode_and_special_characters_in_raw_blocks(self):
        """Unicode and special characters are preserved in raw blocks."""
        thinking_text = "考虑中文字符 🤔 and émojis™"
        response_text = "Response with «special» quotes and ñ"
        
        raw_blocks = [
            {"type": "thinking", "thinking": thinking_text, "signature": "sig_unicode"},
            {"type": "text", "text": response_text},
        ]
        
        msg = AssistantMessage(
            role="assistant",
            content=response_text,
            raw_content_blocks=raw_blocks,
        )
        
        # Round-trip
        json_str = msg.model_dump_json()
        loaded = AssistantMessage.model_validate_json(json_str)
        
        # Unicode preserved exactly
        assert loaded.raw_content_blocks[0]["thinking"] == thinking_text
        assert loaded.raw_content_blocks[1]["text"] == response_text
    
    def test_tool_call_without_arguments_raw_fallback(self):
        """ToolCall without arguments_raw still works (backwards compatible)."""
        tool_call = ToolCall(
            id="call_123",
            name="simple_action",
            arguments={"key": "value"},
            arguments_raw=None,  # Not provided
        )
        
        msg = AssistantMessage(
            role="assistant",
            content=None,
            tool_calls=[tool_call],
        )
        
        # Round-trip
        json_str = msg.model_dump_json()
        loaded = AssistantMessage.model_validate_json(json_str)
        
        assert loaded.tool_calls[0].arguments == {"key": "value"}
        assert loaded.tool_calls[0].arguments_raw is None
    
    def test_both_raw_content_blocks_and_raw_output_items_present(self):
        """Edge case: message has both raw fields (should never happen, but handle gracefully)."""
        msg = AssistantMessage(
            role="assistant",
            content="Test",
            raw_content_blocks=[{"type": "text", "text": "Test"}],
            raw_output_items=[{"type": "message", "content": [{"type": "output_text", "text": "Test"}]}],
        )
        
        # Round-trip still works
        json_str = msg.model_dump_json()
        loaded = AssistantMessage.model_validate_json(json_str)
        
        assert loaded.raw_content_blocks is not None
        assert loaded.raw_output_items is not None
        
        # Anthropic conversion uses raw_content_blocks
        result_anthropic = to_litellm_messages_anthropic([loaded])
        assert result_anthropic[0]["content"] == [{"type": "text", "text": "Test"}]
        
        # Responses API uses raw_output_items
        result_responses = to_responses_api_input([loaded])
        assert result_responses[0]["type"] == "message"
