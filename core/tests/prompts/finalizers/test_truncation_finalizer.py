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

    # Verify truncation occurred
    # The large tool result should have been truncated
    assert (
        "[Tool result truncated due to length constraints]"
        in result_messages[3].content[0].content[0].text
    )  # type: ignore

    # The small tool result should not have been truncated
    assert result_messages[1].content[0].content[0].text == small_result  # type: ignore


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
    """Test that no truncation happens when model is unknown."""
    # Create a prompt
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, world!")]),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Call the finalizer with unknown model
    result_messages = await finalizer(
        messages, prompt, mock_kernel, platform=mock_platform, model="unknown-model"
    )

    # Verify no truncation occurred and we got the original messages back
    assert result_messages == messages


@pytest.mark.asyncio
async def test_truncation_with_custom_max_length(mock_kernel, mock_platform):
    """Test truncation with a custom max_tool_result_length value."""
    # Create a large tool result
    large_result = "This is a very large tool result. " * 500  # Lots of tokens

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
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 500

    # Create a finalizer with a very small max_tool_result_length
    custom_max_length = 100
    custom_finalizer = TruncationFinalizer(max_content_length=custom_max_length)

    # Call the finalizer
    result_messages = await custom_finalizer(
        prompt.messages,
        prompt,
        mock_kernel,
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Verify truncation occurred and respects the custom max length
    truncated_text = result_messages[1].content[0].content[0].text  # type: ignore
    assert "[Tool result truncated due to length constraints]" in truncated_text

    # The truncated part should be close to the custom_max_length
    # Add some margin for the truncation marker
    marker_length = len("[Tool result truncated due to length constraints]") + 4  # ... + space
    assert len(truncated_text) < custom_max_length + marker_length + 50  # Allow some margin


def test_collect_truncatable_content(finalizer, mock_kernel, mock_platform):
    """Test the _collect_truncatable_content method extracts text content properly."""
    # Create multiple content types with sufficient length
    regular_text = "This is regular text content. " * 50  # Make this long enough
    tool_result_text = "This is text content inside a tool result. " * 50  # Make this long enough

    # Set a lower minimum_length_to_truncate to ensure our texts are collected
    object.__setattr__(finalizer, "minimum_length_to_truncate", 10)

    # Create a proper mock for non-text content
    mock_non_text_content = MagicMock()
    mock_non_text_content.count_tokens_approx.return_value = 10

    # Create a prompt with different content types
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text=regular_text)]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_1",
                        tool_name="test_tool",
                        content=[
                            PromptTextContent(text=tool_result_text),
                            # Add a properly mocked non-text content object
                            mock_non_text_content,
                        ],
                    )
                ]
            ),
        ],
    )

    # Get messages to pass to the finalizer
    messages = prompt.messages

    # Call _collect_truncatable_content directly
    truncatable_content = finalizer._collect_truncatable_content(messages)

    # Verify the correct number of items was collected
    assert len(truncatable_content) == 2

    # Find the regular text content item
    text_items = [item for item in truncatable_content if not item.get("tool_name")]
    assert len(text_items) == 1
    assert len(text_items[0]["text_contents"]) == 1
    assert text_items[0]["text_contents"][0].text == regular_text

    # Find the tool result content item
    tool_items = [item for item in truncatable_content if item.get("tool_name") == "test_tool"]
    assert len(tool_items) == 1
    # Verify it found the text content inside the tool result
    assert len(tool_items[0]["text_contents"]) == 1
    assert tool_items[0]["text_contents"][0].text == tool_result_text

    # Verify tool_name is in the dictionary
    assert "tool_name" in tool_items[0]
    assert tool_items[0]["tool_name"] == "test_tool"


def test_truncate_content_method(finalizer):
    """Test the _truncate_content method truncates text from tool results properly."""
    # Create a truncatable content list similar to what
    # _collect_truncatable_content would return
    regular_text_content = PromptTextContent(text="This is regular text. " * 100)
    tool_result_text_content = PromptTextContent(text="This is tool result text. " * 100)

    # Set a very small max_content_length to force truncation
    object.__setattr__(finalizer, "max_content_length", 100)

    truncatable_content = [
        {
            "message_idx": 0,
            "message": MagicMock(),
            "content_idx": 0,
            "content": regular_text_content,
            "tokens": 500,  # Set high token count
            "text_contents": [regular_text_content],
        },
        {
            "message_idx": 1,
            "message": MagicMock(),
            "content_idx": 0,
            "content": MagicMock(),
            "tool_name": "test_tool",
            "tokens": 500,  # Set high token count
            "text_contents": [tool_result_text_content],
        },
    ]

    # Record original lengths
    original_regular_text_len = len(regular_text_content.text)
    original_tool_text_len = len(tool_result_text_content.text)

    # Call _truncate_content with a significant tokens_to_reduce
    tokens_to_reduce = 500
    _ = finalizer._truncate_content(truncatable_content, tokens_to_reduce)

    # Verify both text contents were truncated
    assert len(regular_text_content.text) < original_regular_text_len
    assert len(tool_result_text_content.text) < original_tool_text_len

    # Verify truncation marker was added
    assert "[Tool result truncated due to length constraints]" in regular_text_content.text
    assert "[Tool result truncated due to length constraints]" in tool_result_text_content.text

    # Verify the truncation respects max_content_length
    marker_length = len("[Tool result truncated due to length constraints]") + 4  # ... + space
    assert (
        len(regular_text_content.text) <= finalizer.max_content_length + marker_length + 50
    )  # Allow for marker
    assert (
        len(tool_result_text_content.text) <= finalizer.max_content_length + marker_length + 50
    )  # Allow for marker
