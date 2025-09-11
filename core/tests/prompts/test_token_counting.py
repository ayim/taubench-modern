import json
import logging
from typing import Annotated

import pytest

from agent_platform.core.prompts import (
    Prompt,
    PromptAgentMessage,
    PromptImageContent,
    PromptReasoningContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)


def tokens_for(text: str) -> int:
    """
    Use the same tokenizer path that PromptTextContent uses so we don't
    hard-code numbers. This remains a *lower bound* in our assertions.
    """
    return PromptTextContent.count_tokens_in_text(text)


class FakeTool:
    """
    Minimal stand-in that exposes the attributes Prompt.count_tokens_approx() reads.
    """

    def __init__(self, name: str, description: str, input_schema: dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema


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


def test_system_instruction_increases_tokens():
    """
    Adding a system instruction should increase the token count by at least
    the tokens of that instruction.
    """
    base_prompt = Prompt(
        messages=[
            PromptUserMessage(content=[PromptTextContent(text="hello")]),
            PromptAgentMessage(content=[PromptTextContent(text="hi")]),
        ]
    )
    base_count = base_prompt.count_tokens_approx()

    sys_text = "You are a careful assistant."
    with_system = Prompt(
        system_instruction=sys_text,
        messages=[
            PromptUserMessage(content=[PromptTextContent(text="hello")]),
            PromptAgentMessage(content=[PromptTextContent(text="hi")]),
        ],
    )
    with_system_count = with_system.count_tokens_approx()

    assert with_system_count > base_count
    assert (with_system_count - base_count) >= tokens_for(sys_text)


def test_reasoning_skipped_before_latest_user():
    """
    Reasoning content in messages *before* the most recent user message is skipped.
    Reasoning content *after* the most recent user message counts.

    We assert:
      - adding "old" reasoning before the latest user does not increase tokens
      - adding "new" reasoning after the latest user increases tokens by at least its tokens
    """
    # Baseline without any reasoning
    m0_user = PromptUserMessage(content=[PromptTextContent(text="hi")])
    m1_agent_no_reason = PromptAgentMessage(content=[PromptTextContent(text="old_reply")])
    m2_user = PromptUserMessage(content=[PromptTextContent(text="new")])
    m3_agent_no_reason = PromptAgentMessage(content=[PromptTextContent(text="new_reply")])

    base_prompt = Prompt(messages=[m0_user, m1_agent_no_reason, m2_user, m3_agent_no_reason])
    base_count = base_prompt.count_tokens_approx()

    # Add "old" reasoning before the latest user: should NOT change token count
    m1_agent_with_old_reason = PromptAgentMessage(
        content=[
            PromptReasoningContent(reasoning="old_think"),
            PromptTextContent(text="old_reply"),
        ]
    )
    prompt_with_old_reason = Prompt(
        messages=[m0_user, m1_agent_with_old_reason, m2_user, m3_agent_no_reason]
    )
    count_with_old_reason = prompt_with_old_reason.count_tokens_approx()

    assert count_with_old_reason == base_count, "Old (pre-latest-user) reasoning should be skipped"

    # Add "new" reasoning after the latest user: SHOULD increase by at least its tokens
    new_reason = "new_think"
    m3_agent_with_new_reason = PromptAgentMessage(
        content=[
            PromptReasoningContent(reasoning=new_reason),
            PromptTextContent(text="new_reply"),
        ]
    )
    prompt_with_new_reason = Prompt(
        messages=[m0_user, m1_agent_no_reason, m2_user, m3_agent_with_new_reason]
    )
    count_with_new_reason = prompt_with_new_reason.count_tokens_approx()

    assert count_with_new_reason > base_count
    assert (count_with_new_reason - base_count) >= tokens_for(new_reason)


def test_tools_increase_token_count_by_at_least_rendered_tool_text():
    """
    Adding tools should increase the token count. We assert the increase is at
    least the tokens of the rendered tool metadata string (leaving any fixed
    per-tool fudge factors unconstrained).
    """
    prompt_no_tools = Prompt(
        messages=[PromptUserMessage(content=[PromptTextContent(text="hello")])]
    )
    count_no_tools = prompt_no_tools.count_tokens_approx()

    tool = FakeTool(
        name="search",
        description="Find things on the web",
        input_schema={
            "type": "object",
            "properties": {"q": {"type": "string"}, "site": {"type": "string"}},
            "required": ["q"],
        },
    )
    prompt_with_tool = Prompt(
        messages=[PromptUserMessage(content=[PromptTextContent(text="hello")])],
        tools=[tool],  # type: ignore
    )
    count_with_tool = prompt_with_tool.count_tokens_approx()

    tool_str = (
        f"Tool: {tool.name}\n"
        f"Description: {tool.description}\n"
        f"Parameters: {json.dumps(tool.input_schema, indent=2)}"
    )

    assert count_with_tool > count_no_tools
    assert (count_with_tool - count_no_tools) >= tokens_for(tool_str)


def test_image_content_contributes_its_own_token_cost():
    """
    Adding an image content item should increase the prompt tokens by at least
    the image content's own count_tokens_approx().
    """
    base = Prompt(messages=[PromptUserMessage(content=[PromptTextContent(text="hello")])])
    base_count = base.count_tokens_approx()

    img = PromptImageContent(
        mime_type="image/jpeg",
        value="http://example.com/sample.jpg",
        sub_type="url",
    )
    with_img = Prompt(messages=[PromptUserMessage(content=[PromptTextContent(text="hello"), img])])
    with_img_count = with_img.count_tokens_approx()

    # Lower bound: at least the image's own token estimate
    assert with_img_count > base_count
    assert (with_img_count - base_count) >= img.count_tokens_approx()


def test_tool_result_content_contributes_its_own_token_cost():
    """
    PromptToolResultContent token cost is defined by its own count method.
    The overall prompt should grow by at least that amount when we add it.
    """
    base = Prompt(messages=[PromptUserMessage(content=[PromptTextContent(text="hello")])])
    base_count = base.count_tokens_approx()

    tool_result = PromptToolResultContent(
        tool_name="fetch_data",
        tool_call_id="call_1",
        content=[PromptTextContent(text="abc 123")],
        is_error=False,
    )
    with_result = Prompt(
        messages=[PromptUserMessage(content=[PromptTextContent(text="hello"), tool_result])]
    )
    with_result_count = with_result.count_tokens_approx()

    assert with_result_count > base_count
    assert (with_result_count - base_count) >= tool_result.count_tokens_approx()


def test_multiple_text_contents_add_up_at_least_sum_of_their_tokens():
    """
    Multiple text contents in a single message should increase the prompt by at least
    the sum of their tokens (message-level overhead left unconstrained).
    """
    base = Prompt(messages=[PromptUserMessage(content=[])])
    base_count = base.count_tokens_approx()

    t1 = PromptTextContent(text="alpha")
    t2 = PromptTextContent(text="beta!")
    t3 = PromptTextContent(text="gamma++")

    with_three = Prompt(messages=[PromptUserMessage(content=[t1, t2, t3])])
    with_three_count = with_three.count_tokens_approx()

    expected_min_delta = (
        t1.count_tokens_approx() + t2.count_tokens_approx() + t3.count_tokens_approx()
    )

    assert with_three_count > base_count
    assert (with_three_count - base_count) >= expected_min_delta
