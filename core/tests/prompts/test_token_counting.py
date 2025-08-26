import logging
from typing import Annotated

import pytest

from agent_platform.core.prompts.content.tool_use import PromptToolUseContent
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


def test_count_tokens_approx_with_system_instruction(
    prompt_with_system: Prompt, simple_prompt: Prompt
):
    """System instruction should increase tokens over a simple prompt."""
    assert prompt_with_system.count_tokens_approx() > simple_prompt.count_tokens_approx()


def test_count_tokens_approx_conversation(
    prompt_with_conversation: Prompt, prompt_with_system: Prompt
):
    """Multi-turn conversation should exceed system+single message."""
    assert prompt_with_conversation.count_tokens_approx() > prompt_with_system.count_tokens_approx()


def test_count_tokens_approx_with_tools(prompt_with_tools: Prompt, simple_prompt: Prompt):
    """Tool definitions should add tokens compared to a simple prompt."""
    assert prompt_with_tools.count_tokens_approx() >= simple_prompt.count_tokens_approx()


def test_empty_prompt(
    simple_prompt: Prompt,
    prompt_with_system: Prompt,
    prompt_with_tools: Prompt,
    prompt_with_conversation: Prompt,
    long_prompt: Prompt,
):
    """Empty prompt should have the fewest tokens among all prompts."""
    empty_prompt = Prompt(messages=[])
    empty_count = empty_prompt.count_tokens_approx()

    assert empty_count < simple_prompt.count_tokens_approx()
    assert empty_count < prompt_with_system.count_tokens_approx()
    assert empty_count < prompt_with_tools.count_tokens_approx()
    assert empty_count < prompt_with_conversation.count_tokens_approx()
    assert empty_count < long_prompt.count_tokens_approx()


def test_long_prompt_approx(
    long_prompt: Prompt,
    prompt_with_conversation: Prompt,
    prompt_with_tools: Prompt,
    prompt_with_system: Prompt,
    simple_prompt: Prompt,
):
    """Long prompt should exceed all smaller prompt variants."""
    long_count = long_prompt.count_tokens_approx()
    logger.info(f"Token count for long prompt: {long_count}")

    assert long_count > prompt_with_conversation.count_tokens_approx()
    assert long_count > prompt_with_tools.count_tokens_approx()
    assert long_count > prompt_with_system.count_tokens_approx()
    assert long_count > simple_prompt.count_tokens_approx()
