import logging
from typing import Annotated
from unittest.mock import patch

import pytest

from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt
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


@pytest.mark.parametrize(
    ("model", "expected_tokens"),
    [
        ("gpt-3.5-turbo", 6),  # "Hello, world!" is actually 6 tokens with tiktoken
        ("gpt-4", 6),  # Same count for both models
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
    # "system: You are a helpful assistant.\nuser: Hello, world!\n" -> 14 tokens
    assert token_count == 14


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
        # "Hello, world!" has 13 chars (≈3 tokens) and 2 words (≈3 tokens)
        # The max would be 3
        assert 2 <= token_count <= 4


def test_heuristic_directly(simple_prompt: Prompt):
    """Test the heuristic method directly."""
    token_count = simple_prompt._count_tokens_heuristic()

    # "Hello, world!" has 13 chars (≈3 tokens) and 2 words (≈3 tokens)
    assert 2 <= token_count <= 4


def test_empty_prompt():
    """Test token counting with an empty prompt."""
    empty_prompt = Prompt(messages=[])

    token_count = empty_prompt.count_tokens_approx()
    assert token_count == 0

    # Also test the heuristic
    token_count = empty_prompt._count_tokens_heuristic()
    assert token_count == 0


def test_long_prompt_heuristic_vs_tiktoken(long_prompt: Prompt):
    """Test that the heuristic method gives reasonable results compared to
    tiktoken for long prompts. In order to see the difference output, use
    pytest -v -log-cli-level=INFO."""
    # Get token count using tiktoken
    tiktoken_count = long_prompt.count_tokens_approx()

    # Get token count using heuristic
    heuristic_count = long_prompt._count_tokens_heuristic()

    count_diff = abs(tiktoken_count - heuristic_count)
    # Log the comparison for analysis
    logger.info("Token count comparison for long prompt:")
    logger.info(f"tiktoken count: {tiktoken_count}")
    logger.info(f"heuristic count: {heuristic_count}")
    logger.info(f"difference: {count_diff}")
    logger.info(f"relative difference: {count_diff / tiktoken_count:.2%}")

    # The heuristic should be within 20% of the tiktoken count
    # This is a reasonable margin given the approximation nature of the heuristic
    assert abs(tiktoken_count - heuristic_count) / tiktoken_count <= 0.2

    # Both methods should agree that this is a long prompt
    assert tiktoken_count >= 100
    assert heuristic_count >= 100
