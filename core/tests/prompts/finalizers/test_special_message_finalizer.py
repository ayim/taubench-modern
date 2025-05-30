"""Tests for the SpecialMessageFinalizer class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_platform.core.prompts.finalizers.special_message_finalizer import (
    SpecialMessageFinalizer,
)
from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.prompts.special.conversation_history import (
    ConversationHistorySpecialMessage,
)


@pytest.fixture
def finalizer():
    """Create a SpecialMessageFinalizer for testing."""
    return SpecialMessageFinalizer()


@pytest.fixture
def mock_kernel():
    """Create a mock kernel for testing."""
    return MagicMock()


@pytest.mark.asyncio
async def test_special_message_finalizer_with_no_special_messages(finalizer, mock_kernel):
    """Test that regular messages pass through unchanged."""
    # Create regular messages
    messages = [
        PromptUserMessage([PromptTextContent(text="Hello")]),
        PromptAgentMessage([PromptTextContent(text="Hi there")]),
    ]
    prompt = Prompt(messages=messages)

    # Call the finalizer
    result = await finalizer(messages, prompt, mock_kernel)

    # Should return the same messages unchanged
    assert result == messages
    assert len(result) == 2
    assert isinstance(result[0], PromptUserMessage)
    assert isinstance(result[1], PromptAgentMessage)
    assert result[0].content[0].text == "Hello"
    assert result[1].content[0].text == "Hi there"


@pytest.mark.asyncio
async def test_special_message_finalizer_with_special_messages(finalizer, mock_kernel):
    """Test that special messages are properly hydrated."""
    # Create messages with a special message
    hydrated_messages = [
        PromptUserMessage([PromptTextContent(text="Previous conversation")]),
        PromptAgentMessage([PromptTextContent(text="Previous response")]),
    ]

    # Create a special message
    special_message = ConversationHistorySpecialMessage(role="$conversation-history")

    messages = [
        PromptUserMessage([PromptTextContent(text="Hello")]),
        special_message,
        PromptUserMessage([PromptTextContent(text="Current message")]),
    ]
    prompt = Prompt(messages=messages)  # type: ignore

    # Mock the hydrate method using patch on the class
    with patch.object(
        ConversationHistorySpecialMessage, "hydrate", new=AsyncMock(return_value=hydrated_messages)
    ):
        # Call the finalizer
        result = await finalizer(messages, prompt, mock_kernel)

        # Should have hydrated the special message
        assert len(result) == 4  # Original 2 + 2 hydrated
        assert isinstance(result[0], PromptUserMessage)
        assert result[0].content[0].text == "Hello"
        assert isinstance(result[1], PromptUserMessage)
        assert result[1].content[0].text == "Previous conversation"
        assert isinstance(result[2], PromptAgentMessage)
        assert result[2].content[0].text == "Previous response"
        assert isinstance(result[3], PromptUserMessage)
        assert result[3].content[0].text == "Current message"

        # Verify hydrate was called
        ConversationHistorySpecialMessage.hydrate.assert_called_once_with(mock_kernel)  # type: ignore


@pytest.mark.asyncio
async def test_special_message_finalizer_no_kernel():
    """Test that special messages are removed when no kernel is provided."""
    finalizer = SpecialMessageFinalizer()

    # Create messages with a special message
    special_message = ConversationHistorySpecialMessage(role="$conversation-history")
    messages = [
        PromptUserMessage([PromptTextContent(text="Hello")]),
        special_message,
        PromptUserMessage([PromptTextContent(text="Current message")]),
    ]
    prompt = Prompt(messages=messages)  # type: ignore

    # Call the finalizer without kernel
    result = await finalizer(messages, prompt, None)

    # Should filter out special messages
    assert len(result) == 2
    assert isinstance(result[0], PromptUserMessage)
    assert result[0].content[0].text == "Hello"  # type: ignore
    assert isinstance(result[1], PromptUserMessage)
    assert result[1].content[0].text == "Current message"  # type: ignore


@pytest.mark.asyncio
async def test_special_message_finalizer_multiple_special_messages(finalizer, mock_kernel):
    """Test handling multiple special messages."""
    # Create hydrated messages for each special message
    history_hydrated = [
        PromptUserMessage([PromptTextContent(text="History message")]),
    ]
    memories_hydrated = [
        PromptAgentMessage([PromptTextContent(text="Memory information")]),
    ]

    # Create special messages
    history_special = ConversationHistorySpecialMessage(role="$conversation-history")

    # Create a mock memories special message
    from agent_platform.core.prompts.special.base import SpecialPromptMessage

    memories_special = MagicMock(spec=SpecialPromptMessage)
    memories_special.hydrate = AsyncMock(return_value=memories_hydrated)

    messages = [
        PromptUserMessage([PromptTextContent(text="Start")]),
        history_special,
        memories_special,
        PromptUserMessage([PromptTextContent(text="End")]),
    ]
    prompt = Prompt(messages=messages)  # type: ignore

    # Mock the hydrate method for the conversation history class
    with patch.object(
        ConversationHistorySpecialMessage, "hydrate", new=AsyncMock(return_value=history_hydrated)
    ):
        # Call the finalizer
        result = await finalizer(messages, prompt, mock_kernel)

        # Should have hydrated both special messages
        assert len(result) == 4  # Start + history + memories + End
        assert isinstance(result[0], PromptUserMessage)
        assert result[0].content[0].text == "Start"
        assert isinstance(result[1], PromptUserMessage)
        assert result[1].content[0].text == "History message"
        assert isinstance(result[2], PromptAgentMessage)
        assert result[2].content[0].text == "Memory information"
        assert isinstance(result[3], PromptUserMessage)
        assert result[3].content[0].text == "End"

        # Verify both hydrate methods were called
        ConversationHistorySpecialMessage.hydrate.assert_called_once_with(mock_kernel)  # type: ignore
        memories_special.hydrate.assert_called_once_with(mock_kernel)  # type: ignore


@pytest.mark.asyncio
async def test_special_message_finalizer_empty_hydration(finalizer, mock_kernel):
    """Test handling when special message hydration returns empty list."""
    # Create special message
    special_message = ConversationHistorySpecialMessage(role="$conversation-history")

    messages = [
        PromptUserMessage([PromptTextContent(text="Hello")]),
        special_message,
        PromptUserMessage([PromptTextContent(text="End")]),
    ]
    prompt = Prompt(messages=messages)  # type: ignore

    # Mock hydrate to return empty list using class patch
    with patch.object(ConversationHistorySpecialMessage, "hydrate", new=AsyncMock(return_value=[])):
        # Call the finalizer
        result = await finalizer(messages, prompt, mock_kernel)

        # Should have only the regular messages
        assert len(result) == 2
        assert isinstance(result[0], PromptUserMessage)
        assert result[0].content[0].text == "Hello"
        assert isinstance(result[1], PromptUserMessage)
        assert result[1].content[0].text == "End"

        # Verify hydrate was called
        ConversationHistorySpecialMessage.hydrate.assert_called_once_with(mock_kernel)  # type: ignore
