import logging
from typing import Annotated
from unittest.mock import patch

import pytest

from agent_platform.core.prompts.content.tool_use import PromptToolUseContent
from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.prompts.utils import (
    count_role_indicator_tokens,
    count_tokens_approx,
    count_tools_tokens,
    format_tool_use_for_token_counting,
)
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)


@pytest.fixture
def simple_prompt():
    """Create a simple prompt with just a user message."""
    return Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, world!")]),
        ],
    )


@pytest.fixture
def prompt_with_system():
    """Create a prompt with system instruction and user message."""
    return Prompt(
        system_instruction="You are a helpful assistant.",
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, world!")]),
        ],
    )


@pytest.fixture
def prompt_with_conversation():
    """Create a prompt with a multi-turn conversation."""
    return Prompt(
        system_instruction="You are a helpful assistant.",
        messages=[
            PromptUserMessage([PromptTextContent(text="Hello, how are you?")]),
            PromptAgentMessage(
                [
                    PromptTextContent(
                        text="I'm doing well, thank you for asking. "
                        "How can I help you today?"
                    )
                ]
            ),
            PromptUserMessage([PromptTextContent(text="What's the weather like?")]),
        ],
    )


@pytest.fixture
def prompt_with_tools():
    """Create a prompt with a tool definition."""

    async def get_weather(
        location: Annotated[str, "The city or location to get weather for"],
    ):
        """Get the current weather for a location."""
        return f"Weather for {location}"

    weather_tool = ToolDefinition.from_callable(get_weather)

    return Prompt(
        messages=[
            PromptUserMessage(
                [PromptTextContent(text="What's the weather in Seattle?")]
            ),
        ],
        tools=[weather_tool],
    )


@pytest.fixture
def long_prompt():
    """Create a prompt with a long message and a tool with a long description."""
    long_text = "This is a very long message. " * 10_000  # 2.9M chars, ~70,000 tokens

    # Create a tool with a long description
    async def analyze_text(
        text: Annotated[str, "The text to analyze"],
        analysis_type: Annotated[str, "Type of analysis to perform"],
    ):
        """Analyze text using various natural language processing techniques.

        This tool provides comprehensive text analysis capabilities including:
        - Sentiment analysis to determine emotional tone
        - Named entity recognition to identify people, places, and organizations
        - Part-of-speech tagging to understand grammatical structure
        - Topic modeling to identify key themes and concepts
        - Keyword extraction to find important terms and phrases
        - Readability scoring to assess text complexity
        - Language detection and translation support
        - Text summarization for quick understanding
        - Entity linking to connect mentions to knowledge bases
        - Custom analysis pipelines for specific use cases

        The tool supports multiple languages and can handle various text formats.
        Results are returned in a structured format suitable for further processing.
        """
        return f"Analysis results for: {text[:100]}..."

    analysis_tool = ToolDefinition.from_callable(analyze_text)

    return Prompt(
        messages=[
            PromptUserMessage([PromptTextContent(text=long_text)]),
        ],
        tools=[analysis_tool],
    )


@pytest.fixture
def tool_use_content():
    """Create a tool use content example."""
    return PromptToolUseContent(
        tool_call_id="call_123",
        tool_name="get_weather",
        tool_input_raw={"location": "Seattle", "units": "celsius"},
    )


# Tests for utility functions


def test_count_tokens_approx_utility():
    """Test the count_tokens_approx utility function."""
    text = "Hello, world!"

    # Test with tiktoken
    tiktoken_count = count_tokens_approx(text)
    assert tiktoken_count == 4  # Actual value for this text with tiktoken

    # Test with different model
    gpt4_count = count_tokens_approx(text, model="gpt-4")
    assert gpt4_count == 4  # Same for gpt-4 in this case

    # Test fallback to heuristic
    with patch(
        "builtins.__import__",
        side_effect=lambda name, *args: __import__(name, *args)
        if name != "tiktoken"
        else exec("raise ImportError"),
    ):
        heuristic_count = count_tokens_approx(text)
        # Should be close to actual count
        assert 2 <= heuristic_count <= 6


def test_format_tool_use_for_token_counting():
    """Test the format_tool_use_for_token_counting utility function."""
    tool_call_id = "call_123"
    tool_name = "get_weather"
    tool_input = {"location": "Seattle", "units": "celsius"}

    formatted = format_tool_use_for_token_counting(tool_call_id, tool_name, tool_input)

    # Check that the formatted string contains all the key elements
    assert tool_call_id in formatted
    assert tool_name in formatted
    assert "Seattle" in formatted
    assert "celsius" in formatted

    # Check that it's formatted with the expected structure
    expected_structure = (
        f"tool_call_id: {tool_call_id}\ntool_name: {tool_name}\ntool_input:"
    )
    assert expected_structure in formatted


def test_count_role_indicator_tokens():
    """Test the count_role_indicator_tokens utility function."""
    # Test each role
    system_tokens = count_role_indicator_tokens("system")
    user_tokens = count_role_indicator_tokens("user")
    assistant_tokens = count_role_indicator_tokens("assistant")

    # Each role indicator should return a positive token count
    assert system_tokens > 0
    assert user_tokens > 0
    assert assistant_tokens > 0

    # Test with different model
    gpt4_system_tokens = count_role_indicator_tokens("system", model="gpt-4")
    assert gpt4_system_tokens > 0


def test_count_tools_tokens():
    """Test the count_tools_tokens utility function."""
    # Test with a list of tool dictionaries
    tool_dicts = [
        {
            "name": "get_weather",
            "description": "Get weather information",
            "parameters": {"location": {"type": "string", "description": "Location"}},
        }
    ]

    dict_tokens = count_tools_tokens(tool_dicts)
    assert dict_tokens > 0

    # Test with a list of ToolDefinition objects
    async def get_weather(
        location: Annotated[str, "The city or location to get weather for"],
    ):
        """Get the current weather for a location."""
        return f"Weather for {location}"

    tool_objects = [ToolDefinition.from_callable(get_weather)]

    object_tokens = count_tools_tokens(tool_objects)
    assert object_tokens > 0

    # Test with an empty list
    empty_tokens = count_tools_tokens([])
    assert empty_tokens == 0


# Tests for content type token counting methods


def test_text_content_token_counting():
    """Test token counting for text content."""
    content = PromptTextContent(text="Hello, world!")
    token_count = content.count_tokens_approx()

    # Actual token count for this text
    assert token_count == 4


def test_tool_use_content_token_counting(tool_use_content):
    """Test token counting for tool use content."""
    token_count = tool_use_content.count_tokens_approx()

    # Should be a positive token count
    assert token_count > 0

    # Verify it uses format_tool_use_for_token_counting and count_tokens_approx
    expected_format = format_tool_use_for_token_counting(
        tool_use_content.tool_call_id,
        tool_use_content.tool_name,
        tool_use_content.tool_input,
    )
    expected_count = count_tokens_approx(expected_format)

    assert token_count == expected_count


# Tests for prompt token counting


@pytest.mark.parametrize(
    ("model", "expected_tokens"),
    [
        ("gpt-3.5-turbo", 7),  # 4 for "Hello, world!" + 3 for "user: "
        ("gpt-4", 7),  # Same count for both models
    ],
)
def test_count_tokens_approx_with_tiktoken(
    simple_prompt: Prompt, model: str, expected_tokens: int
):
    """Test token counting using tiktoken."""
    token_count = simple_prompt.count_tokens_approx(model=model)
    assert token_count == expected_tokens


def test_count_tokens_approx_with_system_instruction(
    prompt_with_system: Prompt,
):
    """Test token counting with system instruction."""
    token_count = prompt_with_system.count_tokens_approx()
    # "system: You are a helpful assistant." + "user: Hello, world!"
    assert token_count >= 14


def test_count_tokens_approx_conversation(prompt_with_conversation: Prompt):
    """Test token counting with a multi-turn conversation."""
    token_count = prompt_with_conversation.count_tokens_approx()
    # The full conversation should have more tokens
    assert token_count > 20


def test_count_tokens_approx_with_tools(prompt_with_tools: Prompt):
    """Test token counting with tools."""
    token_count = prompt_with_tools.count_tokens_approx()
    # Tool definitions add to token count
    assert token_count > 10


def test_count_tokens_no_tiktoken(simple_prompt: Prompt):
    """Test token counting fallback when tiktoken is not available."""
    # Mock ImportError when importing tiktoken
    with patch(
        "builtins.__import__",
        side_effect=lambda name, *args: __import__(name, *args)
        if name != "tiktoken"
        else exec("raise ImportError"),
    ):
        # This should use the heuristic method
        token_count = simple_prompt.count_tokens_approx()

        # Check that the token count is reasonable
        # "user: Hello, world!" has ~15 chars and 3 words
        assert token_count > 0


def test_empty_prompt():
    """Test token counting with an empty prompt."""
    empty_prompt = Prompt(messages=[])

    token_count = empty_prompt.count_tokens_approx()
    assert token_count == 0


def test_long_prompt_approx(long_prompt: Prompt):
    """Test that token counting works with long prompts."""
    # Get token count
    token_count = long_prompt.count_tokens_approx()

    # Log the count for analysis
    logger.info(f"Token count for long prompt: {token_count}")

    # Should be a large number
    assert token_count > 1000
