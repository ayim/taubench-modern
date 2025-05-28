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
    TokenCountingConfig,
    count_role_indicator_tokens,
    count_tokens_approx,
    count_tokens_with_heuristic,
    count_tokens_with_tiktoken,
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
                        text="I'm doing well, thank you for asking. How can I help you today?"
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
            PromptUserMessage([PromptTextContent(text="What's the weather in Seattle?")]),
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


# Tests for individual token counting functions


def test_count_tokens_with_heuristic():
    """Test the count_tokens_with_heuristic function."""
    # Test with simple text
    text = "Hello, world!"
    token_count = count_tokens_with_heuristic(text)

    # Verify heuristic calculation
    char_estimate = len(text) / 4  # 13/4 = 3.25
    word_estimate = len(text.split()) / 0.75  # 2/0.75 = 2.67
    expected = max(int(char_estimate), int(word_estimate))  # max(3, 2) = 3
    assert token_count == expected

    # Test with empty text
    empty_count = count_tokens_with_heuristic("")
    assert empty_count == 0

    # Test with single word
    single_word = count_tokens_with_heuristic("hello")
    char_est = len("hello") / 4  # 5/4 = 1.25
    word_est = 1 / 0.75  # 1.33
    expected = max(int(char_est), int(word_est))  # max(1, 1) = 1
    assert single_word == expected

    # Test with longer text
    long_text = "This is a longer sentence with more words and characters."
    long_count = count_tokens_with_heuristic(long_text)
    char_est = len(long_text) / 4
    word_est = len(long_text.split()) / 0.75
    expected = max(int(char_est), int(word_est))
    assert long_count == expected
    assert long_count > token_count  # Should be more than the simple text


def test_count_tokens_with_tiktoken():
    """Test the count_tokens_with_tiktoken function."""
    text = "Hello, world!"

    # Test with default model (gpt-3.5-turbo)
    token_count = count_tokens_with_tiktoken(text)
    assert token_count == 4  # Known value for this text

    # Test with specific model
    gpt4_count = count_tokens_with_tiktoken(text, model="gpt-4")
    assert gpt4_count == 4  # Same value for gpt-4

    # Test with invalid model (should fallback to gpt-3.5-turbo)
    invalid_count = count_tokens_with_tiktoken(text, model="nonexistent-model")
    assert invalid_count == 4  # Should use fallback

    # Test with empty text
    empty_count = count_tokens_with_tiktoken("")
    assert empty_count == 0

    # Test with longer text
    long_text = "This is a longer sentence with multiple words to test tokenization."
    long_count = count_tokens_with_tiktoken(long_text)
    assert long_count > token_count  # Should be more tokens
    assert long_count > 0


def test_count_tokens_with_tiktoken_fallback():
    """Test that count_tokens_with_tiktoken falls back to heuristic when tiktoken fails."""
    text = "Hello, world!"

    # Directly mock sys.modules to make tiktoken unavailable
    import sys

    tiktoken_module = sys.modules.get("tiktoken")
    try:
        # Remove tiktoken from sys.modules if it exists
        if "tiktoken" in sys.modules:
            del sys.modules["tiktoken"]

        # Mock to raise ImportError when tiktoken is imported
        with patch.dict("sys.modules", {"tiktoken": None}):
            # Should fall back to heuristic
            token_count = count_tokens_with_tiktoken(text)

            # Should match heuristic calculation
            expected_heuristic = count_tokens_with_heuristic(text)
            assert token_count == expected_heuristic
    finally:
        # Restore tiktoken module if it was there
        if tiktoken_module is not None:
            sys.modules["tiktoken"] = tiktoken_module


def test_count_tokens_with_tiktoken_encoding_error():
    """Test tiktoken error handling when encoding fails."""
    text = "Hello, world!"

    # Mock tiktoken to raise an exception during encoding
    with patch("tiktoken.encoding_for_model") as mock_encoding:
        mock_encoding.side_effect = Exception("Encoding error")

        # Should fall back to heuristic
        token_count = count_tokens_with_tiktoken(text)
        expected_heuristic = count_tokens_with_heuristic(text)
        assert token_count == expected_heuristic


# Tests for utility functions


def test_count_tokens_approx_with_config():
    """Test that count_tokens_approx respects the TokenCountingConfig."""
    text = "Hello, world!"

    # Save the original instance
    original_instance = TokenCountingConfig._instances.get(TokenCountingConfig)

    try:
        # Test with tiktoken enabled
        tiktoken_config = TokenCountingConfig(enable_tiktoken=True)
        TokenCountingConfig.set_instance(tiktoken_config)

        tiktoken_count = count_tokens_approx(text)
        expected_tiktoken = count_tokens_with_tiktoken(text)
        assert tiktoken_count == expected_tiktoken

        # Test with tiktoken disabled
        heuristic_config = TokenCountingConfig(enable_tiktoken=False)
        TokenCountingConfig.set_instance(heuristic_config)

        heuristic_count = count_tokens_approx(text)
        expected_heuristic = count_tokens_with_heuristic(text)
        assert heuristic_count == expected_heuristic

    finally:
        # Restore original instance
        if original_instance is not None:
            TokenCountingConfig.set_instance(original_instance)
        else:
            # Remove from instances if there was no original
            TokenCountingConfig._instances.pop(TokenCountingConfig, None)


def test_count_tokens_approx_utility():
    """Test the count_tokens_approx utility function."""
    text = "Hello, world!"

    # Test with current config (heuristic by default)
    current_count = count_tokens_approx(text)
    assert current_count == 3  # Heuristic value for this text

    # Test with different model (should still use heuristic by default)
    gpt4_count = count_tokens_approx(text, model="gpt-4")
    assert gpt4_count == 3  # Still heuristic since config is disabled

    # Test with invalid model name (should still use heuristic)
    invalid_model_count = count_tokens_approx(text, model="nonexistent-model")
    assert invalid_model_count == 3  # Should use heuristic

    # Test with tiktoken enabled via config
    original_instance = TokenCountingConfig._instances.get(TokenCountingConfig)
    try:
        tiktoken_config = TokenCountingConfig(enable_tiktoken=True)
        TokenCountingConfig.set_instance(tiktoken_config)

        tiktoken_count = count_tokens_approx(text)
        assert tiktoken_count == 4  # tiktoken value for this text
    finally:
        # Restore original instance
        if original_instance is not None:
            TokenCountingConfig.set_instance(original_instance)
        else:
            TokenCountingConfig._instances.pop(TokenCountingConfig, None)


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
    expected_structure = f"tool_call_id: {tool_call_id}\ntool_name: {tool_name}\ntool_input:"
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

    # Actual token count for this text with heuristic method (current default)
    assert token_count == 3


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
        ("gpt-3.5-turbo", 4),  # 3 for "Hello, world!" + 1 for role indicator (heuristic)
        ("gpt-4", 4),  # Same count for both models
        ("nonexistent-model", 4),  # Should use heuristic
    ],
)
def test_prompt_count_tokens_approx(simple_prompt: Prompt, model: str, expected_tokens: int):
    """Test token counting using the current configuration (heuristic by default)."""
    token_count = simple_prompt.count_tokens_approx(model=model)
    assert token_count == expected_tokens


def test_count_tokens_approx_with_system_instruction(
    prompt_with_system: Prompt,
):
    """Test token counting with system instruction."""
    token_count = prompt_with_system.count_tokens_approx()
    # With heuristic method: "You are a helpful assistant." (7) + "Hello, world!" (3)
    # + role indicators (2)
    assert token_count >= 12


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
