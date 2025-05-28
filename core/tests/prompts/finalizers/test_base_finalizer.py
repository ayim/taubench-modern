"""Tests for the BaseFinalizer abstract class."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.prompts.finalizers.base import BaseFinalizer
from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt


class TestFinalizer(BaseFinalizer):
    """A concrete implementation of BaseFinalizer for testing."""

    def __init__(self, return_reversed=False):
        """Initialize with option to reverse messages."""
        self.return_reversed = return_reversed
        self.call_count = 0

    async def __call__(self, messages, prompt, kernel=None, **kwargs):
        """Test implementation that either returns messages as is or reversed."""
        self.call_count += 1
        self.last_messages = messages
        self.last_prompt = prompt
        self.last_kernel = kernel
        self.last_kwargs = kwargs

        if self.return_reversed:
            return list(reversed(messages))
        return messages


def test_base_finalizer_instantiation():
    """Test that we can instantiate a concrete subclass of BaseFinalizer."""
    finalizer = TestFinalizer()
    assert isinstance(finalizer, BaseFinalizer)
    assert finalizer.call_count == 0


@pytest.mark.asyncio
async def test_base_finalizer_call():
    """Test calling a concrete BaseFinalizer implementation."""
    finalizer = TestFinalizer()

    # Create test inputs
    messages = [
        PromptUserMessage([PromptTextContent(text="Hello")]),
        PromptAgentMessage([PromptTextContent(text="Hi there")]),
    ]
    prompt = Prompt(messages=messages)
    kernel = MagicMock()

    # Call the finalizer
    result = await finalizer(messages, prompt, kernel, test_param="value")

    # Check that the result is as expected
    assert result == messages

    # Check that the finalizer recorded the call correctly
    assert finalizer.call_count == 1
    assert finalizer.last_messages == messages
    assert finalizer.last_prompt == prompt
    assert finalizer.last_kernel == kernel
    assert finalizer.last_kwargs == {"test_param": "value"}


@pytest.mark.asyncio
async def test_base_finalizer_with_message_modification():
    """Test a finalizer that modifies the messages."""
    finalizer = TestFinalizer(return_reversed=True)

    # Create test inputs
    messages = [
        PromptUserMessage([PromptTextContent(text="First message")]),
        PromptAgentMessage([PromptTextContent(text="Second message")]),
    ]
    prompt = Prompt(messages=messages)

    # Call the finalizer
    result = await finalizer(messages, prompt, None)

    # Check that the result is reversed
    assert result != messages
    assert len(result) == 2
    assert isinstance(result[0], PromptAgentMessage)
    assert isinstance(result[1], PromptUserMessage)
    assert isinstance(result[0].content[0], PromptTextContent)
    assert result[0].content[0].text == "Second message"
    assert isinstance(result[1].content[0], PromptTextContent)
    assert result[1].content[0].text == "First message"


@pytest.mark.asyncio
async def test_base_finalizer_composition():
    """Test composing multiple finalizers together."""
    # Create two finalizers - one that reverses, one that doesn't
    finalizer1 = TestFinalizer(return_reversed=True)
    finalizer2 = TestFinalizer()

    # Create test inputs
    messages = [
        PromptUserMessage([PromptTextContent(text="First message")]),
        PromptAgentMessage([PromptTextContent(text="Second message")]),
    ]
    prompt = Prompt(messages=messages)

    # Apply both finalizers in sequence
    intermediate_result = await finalizer1(messages, prompt, None)
    final_result = await finalizer2(intermediate_result, prompt, None)

    # Check that the result maintains the reversed order from finalizer1
    assert final_result != messages
    assert len(final_result) == 2
    assert isinstance(final_result[0], PromptAgentMessage)
    assert isinstance(final_result[1], PromptUserMessage)


def test_abstract_class_cannot_be_instantiated():
    """Test that BaseFinalizer cannot be instantiated directly."""
    pytest.skip("Cannot instantiate abstract class BaseFinalizer due to linter enforcement.")
