"""Tests for the TruncationFinalizer class."""

# Note: This file uses multiple `# type: ignore` annotations because the type system
# has issues with some of the complex nested types. Specifically:
# 1. The Prompt class expects a precise type for messages, but our list contents are
#    compatible subtypes
# 2. PromptToolResultContent is not recognized as a valid content type for
#    PromptAgentMessage by the type checker
# 3. Accessing nested attributes like content[0].content[0].text triggers type errors
# These ignores don't affect runtime behavior, they just silence the type checker.

from unittest.mock import MagicMock

import pytest

from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.finalizers.truncation_finalizer import (
    TruncationFinalizer,
)
from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt


class MockPlatform:
    """Mock platform for testing."""

    def __init__(self):
        self.client = MagicMock()
        self.client.model_map = MagicMock()
        self.client.model_map.model_context_windows = {
            "gpt-3.5-turbo": 4096,
            "gpt-4": 8192,
        }


@pytest.fixture
def mock_kernel():
    """Create a mock kernel for testing."""
    return MagicMock()


@pytest.fixture
def mock_platform():
    """Create a mock platform for testing."""
    return MockPlatform()


@pytest.fixture
def finalizer():
    """Create a TruncationFinalizer for testing."""
    return TruncationFinalizer()


@pytest.mark.asyncio
async def test_truncation_not_needed(finalizer, mock_kernel, mock_platform):
    """Test that no truncation happens when we're below the token budget."""
    # Create a prompt that's small enough to not need truncation
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, world!")]),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Call the finalizer
    result_messages = await finalizer(
        messages, prompt, mock_kernel, platform=mock_platform, model="gpt-3.5-turbo"
    )

    # Verify no truncation occurred
    assert result_messages == messages
    assert result_messages[0].content[0].text == "Hello, world!"


@pytest.mark.asyncio
async def test_truncation_with_large_result(finalizer, mock_kernel, mock_platform):
    """Test truncation with a large tool result."""
    # Create a large tool result
    large_result = "This is a very large tool result. " * 10000  # Lots of tokens

    # Create a prompt with a tool result
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the weather?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_123",
                        tool_name="get_weather",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Set max tokens to force truncation by adjusting the mock platform's context window
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 2000

    # Call the finalizer
    result_messages = await finalizer(
        messages, prompt, mock_kernel, platform=mock_platform, model="gpt-3.5-turbo"
    )

    # Verify truncation occurred
    assert result_messages == messages  # Messages list should be the same object
    assert (
        "[Tool result truncated due to length constraints]"
        in result_messages[1].content[0].content[0].text
    )  # type: ignore
    # Original text should be truncated
    assert len(result_messages[1].content[0].content[0].text) < len(large_result)  # type: ignore


@pytest.mark.asyncio
async def test_truncation_multiple_results(finalizer, mock_kernel, mock_platform):
    """Test truncation with multiple tool results."""
    # Create multiple tool results of different sizes
    small_result = "This is a small tool result."
    medium_result = "This is a medium tool result. " * 200
    large_result = "This is a large tool result. " * 5000

    # Create a prompt with multiple tool results
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the data?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_1",
                        tool_name="small_tool",
                        content=[PromptTextContent(text=small_result)],
                    )
                ]
            ),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_2",
                        tool_name="medium_tool",
                        content=[PromptTextContent(text=medium_result)],
                    )
                ]
            ),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_3",
                        tool_name="large_tool",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Set max tokens to force significant truncation
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 2000

    # Call the finalizer
    result_messages = await finalizer(
        messages, prompt, mock_kernel, platform=mock_platform, model="gpt-3.5-turbo"
    )

    # Verify truncation occurred proportionally
    # The large tool result should have been truncated the most
    assert (
        "[Tool result truncated due to length constraints]"
        in result_messages[3].content[0].content[0].text
    )  # type: ignore

    # The small tool result might not have been truncated due to the token floor
    small_tool_text = result_messages[1].content[0].content[0].text  # type: ignore
    # Either it wasn't truncated or it was but respects the floor
    assert (
        small_tool_text == small_result
        or "[Tool result truncated due to length constraints]" in small_tool_text
    )


@pytest.mark.asyncio
async def test_truncation_no_tool_results(finalizer, mock_kernel, mock_platform):
    """Test that no truncation happens when there are no tool results."""
    # Create a prompt with no tool results
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            PromptAgentMessage([PromptTextContent(text="Hello, how can I help you?")]),
            PromptUserMessage([PromptTextContent(text="What's the weather like?")]),
            PromptAgentMessage([PromptTextContent(text="I don't know, I'm just an AI.")]),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Set max tokens lower than would normally be needed
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 10

    # Call the finalizer
    result_messages = await finalizer(
        messages, prompt, mock_kernel, platform=mock_platform, model="gpt-3.5-turbo"
    )

    # Verify no truncation occurred (because there are no tool results to truncate)
    assert result_messages == messages
    # Check that content is unmodified
    assert result_messages[0].content[0].text == "Hello, world!"
    assert result_messages[1].content[0].text == "Hello, how can I help you?"
    assert result_messages[2].content[0].text == "What's the weather like?"
    assert result_messages[3].content[0].text == "I don't know, I'm just an AI."


@pytest.mark.asyncio
async def test_truncation_with_missing_platform(finalizer, mock_kernel):
    """Test that no truncation happens when platform is missing."""
    # Create a prompt
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, world!")]),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Call the finalizer without platform
    result_messages = await finalizer(messages, prompt, mock_kernel, model="gpt-3.5-turbo")

    # Verify no truncation occurred and we got the original messages back
    assert result_messages == messages


@pytest.mark.asyncio
async def test_truncation_with_missing_kernel(finalizer, mock_platform):
    """Test that no truncation happens when kernel is missing."""
    # Create a prompt
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, world!")]),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Call the finalizer without kernel
    result_messages = await finalizer(
        messages, prompt, None, platform=mock_platform, model="gpt-3.5-turbo"
    )

    # Verify no truncation occurred and we got the original messages back
    assert result_messages == messages


@pytest.mark.asyncio
async def test_truncation_with_unknown_model(finalizer, mock_kernel, mock_platform):
    """Test that truncation works correctly for unknown models using default context window."""
    # Create a very large tool result that will exceed even the 128k default context window
    large_result = "This is a very large tool result. " * 50000  # Much larger content

    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the weather?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_123",
                        tool_name="get_weather",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Call the finalizer with unknown model (should use default 128,000 context window)
    result_messages = await finalizer(
        messages, prompt, mock_kernel, platform=mock_platform, model="unknown-model"
    )

    # With such a large tool result, even the 128k context window should require truncation
    assert result_messages == messages  # Same message objects

    # Verify that truncation occurred on the tool result
    truncated_text = result_messages[1].content[0].content[0].text  # type: ignore
    assert "[Tool result truncated due to length constraints]" in truncated_text
    assert len(truncated_text) < len(large_result)


@pytest.mark.asyncio
async def test_truncation_with_custom_parameters(mock_kernel, mock_platform):
    """Test truncation with custom token_budget_percentage and truncation_token_floor."""
    # Create a large tool result
    large_result = "This is a very large tool result. " * 1000

    # Create a prompt with a tool result
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the weather?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_123",
                        tool_name="get_weather",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Set max tokens to force truncation with a very small context window
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 1000

    # Create a finalizer with custom parameters
    custom_finalizer = TruncationFinalizer(
        token_budget_percentage=0.5,  # Use only 50% of context window
        truncation_token_floor=100,  # Lower token floor for more aggressive truncation
    )

    # Call the finalizer
    result_messages = await custom_finalizer(
        prompt.messages,
        prompt,
        mock_kernel,
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Verify truncation occurred and respects the custom parameters
    truncated_text = result_messages[1].content[0].content[0].text  # type: ignore
    assert "[Tool result truncated due to length constraints]" in truncated_text
    assert len(truncated_text) < len(large_result)


def test_collect_truncatable_content(finalizer):
    """Test the _collect_truncatable_content method extracts tool results properly."""
    # Create content with tool results
    tool_result_text = "This is text content inside a tool result. " * 50

    # Create a prompt with different content types
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="Regular user message")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_1",
                        tool_name="test_tool",
                        content=[PromptTextContent(text=tool_result_text)],
                    )
                ]
            ),
            PromptAgentMessage([PromptTextContent(text="Regular agent response")]),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Call _collect_truncatable_content directly
    truncatable_content = finalizer._collect_truncatable_content(messages)

    # Verify only the tool result was collected
    assert len(truncatable_content) == 1

    # Verify the structure matches TruncationItem
    item = truncatable_content[0]
    assert "tool_name" in item
    assert "tokens" in item
    assert "text_contents" in item

    # Verify the content
    assert item["tool_name"] == "test_tool"
    assert item["tokens"] > 0
    assert len(item["text_contents"]) == 1
    assert item["text_contents"][0].text == tool_result_text


def test_truncate_content_method(finalizer):
    """Test the _truncate_content method truncates tool results proportionally."""
    # Create tool result text content
    tool_result_text_content = PromptTextContent(text="This is tool result text. " * 100)

    # Create a truncatable content list similar to what
    # _collect_truncatable_content would return
    # Use more tokens than the default floor (1000) to allow truncation
    truncatable_content = [
        {
            "tool_name": "test_tool",
            "tokens": 1500,  # More than the default floor of 1000
            "text_contents": [tool_result_text_content],
        }
    ]

    # Record original length
    original_text_len = len(tool_result_text_content.text)

    # Call _truncate_content with a significant tokens_to_reduce
    tokens_to_reduce = 300
    remaining_tokens = finalizer._truncate_content(truncatable_content, tokens_to_reduce)

    # Verify text content was truncated
    assert len(tool_result_text_content.text) < original_text_len

    # Verify truncation marker was added
    assert "[Tool result truncated due to length constraints]" in tool_result_text_content.text

    # Verify the method returned remaining tokens (should be 0 or close to 0)
    assert remaining_tokens >= 0

    # Verify the token count was updated in the item
    assert truncatable_content[0]["tokens"] < 1500
