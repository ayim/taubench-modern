"""Integration tests for finalizers with the Prompt class."""

import pytest

from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.finalizers.special_message_finalizer import (
    SpecialMessageFinalizer,
)
from agent_platform.core.prompts.finalizers.truncation_finalizer import (
    TruncationFinalizer,
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


class MockPlatform:
    """Mock platform for testing."""

    def __init__(self):
        # Create MockModelMap with model_context_windows defined
        MockModelMap = type(  # noqa: N806
            "MockModelMap",
            (),
            {
                "model_context_windows": {
                    "gpt-3.5-turbo": 4096,
                    "gpt-4": 8192,
                }
            },
        )

        # Create MockClient with model_map defined
        self.client = type("MockClient", (), {"model_map": MockModelMap()})()


@pytest.fixture
def mock_kernel():
    """Create a mock kernel for testing."""
    # Create a large tool result that would be in the conversation history
    large_tool_result = (
        "This is a very large tool result with lots of data. " * 800
    )  # Lots of tokens

    # Define hydrated messages that would result from the special message
    # Include actual tool results that can be truncated
    hydrated_messages = [
        PromptUserMessage([PromptTextContent(text="What's the weather?")]),
        PromptAgentMessage(content=[PromptTextContent(text="Let me check the weather for you.")]),
        PromptUserMessage([PromptTextContent(text="Can you give me more details?")]),
        PromptAgentMessage(
            content=[
                PromptTextContent(text="Here's the detailed weather information:"),
                PromptToolResultContent(  # type: ignore
                    tool_call_id="call_weather_1",
                    tool_name="weather_tool",
                    content=[PromptTextContent(text=large_tool_result)],
                ),
            ]
        ),
    ]

    # Create a mock kernel that will return the hydrated messages
    mock_kernel = type(
        "MockKernel",
        (),
        {
            "thread": type("MockThread", (), {"get_last_n_message_turns": lambda n: []}),
            "converters": type(
                "MockConverters",
                (),
                {"thread_messages_to_prompt_messages": lambda messages: hydrated_messages},
            ),
        },
    )()

    # The original hydrate method
    original_hydrate = ConversationHistorySpecialMessage.hydrate

    # Create a mock hydrate that returns our prepared hydrated messages
    async def mock_hydrate(self, kernel):
        # This must return the hydrated messages list
        return hydrated_messages

    # Patch the hydrate method for testing
    ConversationHistorySpecialMessage.hydrate = mock_hydrate

    yield mock_kernel

    # Restore the original method after the test
    ConversationHistorySpecialMessage.hydrate = original_hydrate


@pytest.fixture
def mock_platform():
    """Create a mock platform for testing."""
    return MockPlatform()


@pytest.mark.asyncio
async def test_prompt_finalize_with_default_finalizers(mock_kernel, mock_platform):
    """Test that Prompt.finalize_messages works with default finalizers when none are provided."""
    # Create a prompt with special message for conversation history
    prompt = Prompt(
        messages=[
            # Start with a user message as required
            PromptUserMessage([PromptTextContent(text="Hello")]),
            # Then add special messages for conversation history
            ConversationHistorySpecialMessage(role="$conversation-history"),
            # Add a user message after the history
            PromptUserMessage([PromptTextContent(text="Tell me more about the weather")]),
        ],
    )

    # Set max tokens to force truncation
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 2000

    # Finalize the prompt WITHOUT providing explicit finalizers (should use defaults)
    finalized_prompt = await prompt.finalize_messages(
        kernel=mock_kernel,
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Verify the prompt was finalized
    assert finalized_prompt._finalized

    # Verify the default finalizers worked
    assert len(finalized_prompt.messages) == 6  # Same as explicit test
    assert isinstance(finalized_prompt.messages[4], PromptAgentMessage)

    # Check that truncation occurred on the tool result
    agent_message = finalized_prompt.messages[4]
    tool_result = agent_message.content[1]  # type: ignore
    assert isinstance(tool_result, PromptToolResultContent)
    tool_result_text = tool_result.content[0].text  # type: ignore
    assert "[Tool result truncated due to length constraints]" in tool_result_text


@pytest.mark.asyncio
async def test_prompt_finalize_already_finalized(mock_kernel, mock_platform):
    """Test that calling finalize_messages on an already finalized prompt returns the
    same instance."""
    # Create a simple prompt
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, world!")]),
        ]
    )

    # Finalize it once
    finalized_once = await prompt.finalize_messages(
        kernel=mock_kernel,
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Verify it's finalized
    assert finalized_once._finalized

    # Finalize it again
    finalized_twice = await finalized_once.finalize_messages(
        kernel=mock_kernel,
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Should return the same instance
    assert finalized_twice is finalized_once
    assert finalized_twice._finalized


@pytest.mark.asyncio
async def test_prompt_finalize_with_finalizer_kwargs(mock_kernel, mock_platform):
    """Test that finalizer-specific kwargs are properly passed to individual finalizers."""
    # Create a prompt with tool result
    large_result = "This is a large tool result. " * 1000
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the data?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_1",
                        tool_name="test_tool",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Set small context window to force truncation
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 1000

    # Create finalizers
    special_finalizer = SpecialMessageFinalizer()
    truncation_finalizer = TruncationFinalizer()

    # Finalize with specific kwargs for the truncation finalizer
    finalized_prompt = await prompt.finalize_messages(
        kernel=mock_kernel,
        prompt_finalizers=[special_finalizer, truncation_finalizer],
        finalizer_kwargs={
            truncation_finalizer: {
                "token_budget_percentage": 0.3,  # Very aggressive
                "truncation_token_floor": 50,  # Very low floor
            }
        },
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Verify truncation occurred with the custom parameters
    tool_result_text = finalized_prompt.messages[1].content[0].content[0].text  # type: ignore
    assert "[Tool result truncated due to length constraints]" in tool_result_text
    # Should be heavily truncated due to aggressive settings
    assert len(tool_result_text) < len(large_result) * 0.5


@pytest.mark.asyncio
async def test_prompt_finalize_with_empty_finalizers_list(mock_kernel):
    """Test that providing an empty finalizers list works."""
    # Create a prompt with special message
    prompt = Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello")]),
            ConversationHistorySpecialMessage(role="$conversation-history"),
        ],
    )

    # Finalize with empty finalizers list
    finalized_prompt = await prompt.finalize_messages(
        kernel=mock_kernel,
        prompt_finalizers=[],  # Explicitly empty
    )

    # Should be finalized but special messages should remain (not hydrated)
    assert finalized_prompt._finalized
    # Note: The special message would remain because no SpecialMessageFinalizer was applied
    # But the prompt.finalize_messages method casts to regular messages, so this would
    # likely cause issues in practice


@pytest.mark.asyncio
async def test_prompt_finalize_kwargs_precedence(mock_kernel, mock_platform):
    """Test that global kwargs take precedence over finalizer-specific kwargs."""
    # Create a prompt with tool result
    large_result = "This is a large tool result. " * 1000
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the data?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_1",
                        tool_name="test_tool",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Set small context window to force truncation
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 1000

    # Create finalizers
    special_finalizer = SpecialMessageFinalizer()
    truncation_finalizer = TruncationFinalizer()

    # Both finalizer_kwargs and global kwargs specify platform, global should win
    finalized_prompt = await prompt.finalize_messages(
        kernel=mock_kernel,
        prompt_finalizers=[special_finalizer, truncation_finalizer],
        finalizer_kwargs={
            truncation_finalizer: {
                "platform": None,  # This should be overridden
            }
        },
        platform=mock_platform,  # Global kwargs should take precedence
        model="gpt-3.5-turbo",
    )

    # Verify truncation occurred (proving global platform was used)
    tool_result_text = finalized_prompt.messages[1].content[0].content[0].text  # type: ignore
    assert "[Tool result truncated due to length constraints]" in tool_result_text


@pytest.mark.asyncio
async def test_prompt_finalize_with_truncation(mock_kernel, mock_platform):
    """Test that Prompt.finalize_messages works with TruncationFinalizer."""
    # Create a prompt with special message for conversation history
    prompt = Prompt(
        messages=[
            # Start with a user message as required
            PromptUserMessage([PromptTextContent(text="Hello")]),
            # Then add special messages for conversation history
            ConversationHistorySpecialMessage(role="$conversation-history"),
            # Add a user message after the history
            PromptUserMessage([PromptTextContent(text="Tell me more about the weather")]),
        ],
    )

    # Set max tokens to force truncation
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 2000

    # Create the finalizers in the correct order
    special_finalizer = SpecialMessageFinalizer()
    truncation_finalizer = TruncationFinalizer(
        token_budget_percentage=0.5,
        truncation_token_floor=100,  # Lower floor for more aggressive truncation
    )

    # Finalize the prompt with both finalizers in the right order
    finalized_prompt = await prompt.finalize_messages(
        kernel=mock_kernel,
        prompt_finalizers=[special_finalizer, truncation_finalizer],
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Verify the prompt was finalized
    assert finalized_prompt._finalized

    # After hydration, our message sequence should be:
    # 0: Original user message ("Hello")
    # 1: First hydrated message - User ("What's the weather?")
    # 2: Second hydrated message - Agent ("Let me check the weather for you.")
    # 3: Third hydrated message - User ("Can you give me more details?")
    # 4: Fourth hydrated message - Agent (with text and tool result to be truncated)
    # 5: Final user message ("Tell me more about the weather")

    # Verify the message structure
    assert len(finalized_prompt.messages) == 6
    assert isinstance(finalized_prompt.messages[0], PromptUserMessage)
    assert isinstance(finalized_prompt.messages[1], PromptUserMessage)
    assert isinstance(finalized_prompt.messages[2], PromptAgentMessage)
    assert isinstance(finalized_prompt.messages[3], PromptUserMessage)
    assert isinstance(finalized_prompt.messages[4], PromptAgentMessage)
    assert isinstance(finalized_prompt.messages[5], PromptUserMessage)

    # Check that the fourth message (agent response) has both text and tool result content
    agent_message = finalized_prompt.messages[4]
    assert len(agent_message.content) == 2

    # First content should be regular text
    assert isinstance(agent_message.content[0], PromptTextContent)
    assert agent_message.content[0].text == "Here's the detailed weather information:"

    # Second content should be the tool result that was truncated
    assert isinstance(agent_message.content[1], PromptToolResultContent)
    tool_result = agent_message.content[1]
    assert tool_result.tool_name == "weather_tool"
    assert tool_result.tool_call_id == "call_weather_1"

    # The tool result should have been truncated
    assert isinstance(tool_result.content, list)
    assert len(tool_result.content) == 1
    assert isinstance(tool_result.content[0], PromptTextContent)
    tool_result_text = tool_result.content[0].text

    # Verify that the tool result was actually truncated
    assert "[Tool result truncated due to length constraints]" in tool_result_text

    # The truncated text should be much shorter than the original
    original_large_result = "This is a very large tool result with lots of data. " * 800
    assert len(tool_result_text) < len(original_large_result)


@pytest.mark.asyncio
async def test_prompt_finalize_with_custom_truncation_params(mock_kernel, mock_platform):
    """Test TruncationFinalizer with custom parameters."""
    # Create tool results of different sizes
    small_result = "This is a small tool result."
    large_result = "This is a large tool result. " * 500

    # Create a prompt with tool results
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
                        tool_call_id="call_3",
                        tool_name="large_tool",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Set max tokens to force significant truncation (even smaller than before)
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 500

    # Create the finalizer with very aggressive settings
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.3,  # Even more aggressive truncation
        truncation_token_floor=50,  # Very low token floor
    )

    # Finalize the prompt
    finalized_prompt = await prompt.finalize_messages(
        kernel=mock_kernel,
        prompt_finalizers=[finalizer],
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Verify the prompt was finalized
    assert finalized_prompt._finalized

    # Check the large tool result is properly set up
    assert isinstance(finalized_prompt.messages[2], PromptAgentMessage)
    assert isinstance(finalized_prompt.messages[2].content[0], PromptToolResultContent)  # type: ignore
    assert isinstance(finalized_prompt.messages[2].content[0].content[0], PromptTextContent)  # type: ignore

    # The large tool result should have been heavily truncated
    tool_result_text = finalized_prompt.messages[2].content[0].content[0].text  # type: ignore
    assert tool_result_text is not None
    assert "[Tool result truncated due to length constraints]" in tool_result_text

    # With our extremely aggressive settings, truncation should be very significant
    assert len(tool_result_text) < len(large_result)


@pytest.mark.asyncio
async def test_truncation_with_multiple_content_items(mock_kernel, mock_platform):
    """Test truncation with tool results containing multiple text content items."""
    # Create tool result with multiple text items
    text1 = "This is the first text content item. " * 100
    text2 = "This is the second text content item. " * 200
    text3 = "This is the third text content item. " * 300

    # Create a prompt with a tool result containing multiple text content items
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="Process this data")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_1",
                        tool_name="complex_tool",
                        content=[
                            PromptTextContent(text=text1),
                            PromptTextContent(text=text2),
                            PromptTextContent(text=text3),
                        ],
                    )
                ]
            ),
        ],
    )

    # Set max tokens to force significant truncation
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 1000

    # Create finalizer with aggressive settings
    finalizer = TruncationFinalizer(
        token_budget_percentage=0.5,
        truncation_token_floor=100,  # Lower token floor for more truncation
    )

    # Finalize the prompt
    finalized_prompt = await prompt.finalize_messages(
        kernel=mock_kernel,
        prompt_finalizers=[finalizer],
        platform=mock_platform,
        model="gpt-3.5-turbo",
    )

    # Verify the prompt was finalized
    assert finalized_prompt._finalized

    # Check all text content items in the tool result
    tool_result = finalized_prompt.messages[1].content[0]  # type: ignore
    assert isinstance(tool_result, PromptToolResultContent)

    # All three text content items should have been truncated proportionally
    truncated_count = 0
    for i, content_item in enumerate(tool_result.content):
        if isinstance(content_item, PromptTextContent):
            original_text = [text1, text2, text3][i]

            # Check if this item was truncated
            if "[Tool result truncated due to length constraints]" in content_item.text:
                truncated_count += 1
                # Verify original text was much longer
                assert len(content_item.text) < len(original_text)

    # At least some of the content should have been truncated given our aggressive settings
    assert truncated_count > 0
