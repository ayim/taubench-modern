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
    large_result = "This is a very large tool result. " * 1000  # Lots of tokens

    # Define hydrated messages that would result from the special message
    hydrated_messages = [
        PromptUserMessage([PromptTextContent(text="What's the weather?")]),
        PromptAgentMessage(
            content=[PromptTextContent(text="Here's the weather information:")]
        ),
        PromptUserMessage([PromptTextContent(text="Can you give me more details?")]),
        PromptAgentMessage(
            content=[
                PromptTextContent(
                    text="The weather is sunny with a high of 75°F. " + large_result
                )
            ]
        ),
    ]

    # Create a mock kernel that will return the hydrated messages
    mock_kernel = type(
        "MockKernel",
        (),
        {
            "thread": type(
                "MockThread", (), {"get_last_n_message_turns": lambda n: []}
            ),
            "converters": type(
                "MockConverters",
                (),
                {
                    "thread_messages_to_prompt_messages": lambda messages: hydrated_messages  # noqa: E501
                },
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
            PromptUserMessage(
                [PromptTextContent(text="Tell me more about the weather")]
            ),
        ],
    )

    # Set max tokens to force truncation
    mock_platform.client.model_map.model_context_windows["gpt-3.5-turbo"] = 2000

    # Create the finalizers in the correct order
    special_finalizer = SpecialMessageFinalizer()
    truncation_finalizer = TruncationFinalizer(
        token_budget_percentage=0.5, max_content_length=200
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
    # 2: Second hydrated message - Agent
    # 3: Third hydrated message - User
    # 4: Fourth hydrated message - Agent (with large text to be truncated)
    # 5: Final user message ("Tell me more about the weather")

    # Verify the first few messages are of the expected types
    assert isinstance(finalized_prompt.messages[0], PromptUserMessage)
    assert isinstance(finalized_prompt.messages[1], PromptUserMessage)
    assert isinstance(finalized_prompt.messages[2], PromptAgentMessage)
    assert isinstance(finalized_prompt.messages[3], PromptUserMessage)
    assert isinstance(finalized_prompt.messages[4], PromptAgentMessage)
    assert isinstance(finalized_prompt.messages[5], PromptUserMessage)

    # Check that the fourth message (agent response) has truncated text
    assert isinstance(finalized_prompt.messages[4].content[0], PromptTextContent)

    # Get the text of the 4th message (agent response with the large tool result)
    large_text = finalized_prompt.messages[4].content[0].text
    assert large_text is not None

    # The truncation marker should be present in the text
    assert "[Tool result truncated due to length constraints]" in large_text

    # Verify the original large text was truncated significantly
    large_result = "This is a very large tool result. " * 1000
    assert len(large_text) < len(large_result)
    # With our aggressive settings, truncation should be significant
    assert len(large_text) < 500  # Allow some extra chars for truncation marker


@pytest.mark.asyncio
async def test_prompt_finalize_with_custom_truncation_params(
    mock_kernel, mock_platform
):
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
        max_content_length=50,  # Very short max length
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
    assert isinstance(finalized_prompt.messages[2].content[0], PromptToolResultContent)
    assert isinstance(
        finalized_prompt.messages[2].content[0].content[0], PromptTextContent
    )

    # The large tool result should have been heavily truncated
    tool_result_text = finalized_prompt.messages[2].content[0].content[0].text
    assert tool_result_text is not None
    assert "[Tool result truncated due to length constraints]" in tool_result_text

    # With our extremely aggressive settings, truncation should be very significant
    assert len(tool_result_text) < 200


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
        max_content_length=100,  # Very short max length
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

    # All three text content items should have been truncated
    for i, content_item in enumerate(tool_result.content):
        if isinstance(content_item, PromptTextContent):
            # Verify truncation marker is present
            assert (
                "[Tool result truncated due to length constraints]" in content_item.text
            )

            # Verify length is within limits (allowing for marker)
            marker_length = len("[Tool result truncated due to length constraints]") + 4
            assert (
                len(content_item.text)
                <= finalizer.max_content_length + marker_length + 50
            )

            # Verify original text was much longer
            original_text = [text1, text2, text3][i]
            assert len(content_item.text) < len(original_text)
