from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.cortex.converters import CortexConverters
from agent_platform.core.platforms.cortex.prompts import CortexPrompt
from agent_platform.core.platforms.cortex.types import (
    CortexPromptContent,
    CortexPromptToolResults,
    CortexPromptToolUse,
)
from agent_platform.core.prompts import (
    Prompt,
    PromptAgentMessage,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.tools import ToolDefinition


class TestCortexConverters:
    """Tests for the Cortex converters."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def converters(self, kernel: Kernel) -> CortexConverters:
        """Create Cortex converters for testing."""
        converters = CortexConverters()
        converters.attach_kernel(kernel)
        return converters

    @pytest.mark.asyncio
    async def test_convert_text_content(self, converters: CortexConverters) -> None:
        """Test converting text content."""
        text_content = PromptTextContent(text="Hello, world!")

        result = await converters.convert_text_content(text_content)

        assert result == CortexPromptContent(type="text", text="Hello, world!")

    @pytest.mark.asyncio
    async def test_convert_image_content(self, converters: CortexConverters) -> None:
        """Test converting image content."""
        # Skip this test for now as Cortex doesn't support images today (4/1/2025)
        pass

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(
        self,
        converters: CortexConverters,
    ) -> None:
        """Test converting tool use content."""
        tool_use_content = PromptToolUseContent(
            tool_call_id="tool-1234",
            tool_name="get_weather",
            tool_input_raw='{"location": "New York"}',
        )

        result = await converters.convert_tool_use_content(tool_use_content)

        assert result == CortexPromptContent(
            type="tool_use",
            tool_use=CortexPromptToolUse(
                tool_use_id="tool-1234",
                name="get_weather",
                input={"location": "New York"},
            ),
        )

    @pytest.mark.asyncio
    async def test_convert_tool_result_content(
        self,
        converters: CortexConverters,
    ) -> None:
        """Test converting tool result content."""
        tool_result_content = PromptToolResultContent(
            tool_call_id="tool-1234",
            tool_name="get_weather",
            content=[PromptTextContent(text='{"temp": 72, "condition": "sunny"}')],
        )

        result = await converters.convert_tool_result_content(tool_result_content)

        assert result == CortexPromptContent(
            type="tool_results",
            tool_results=CortexPromptToolResults(
                tool_use_id="tool-1234",
                name="get_weather",
                content=[
                    CortexPromptContent(
                        type="text",
                        text='{"temp": 72, "condition": "sunny"}',
                    ),
                ],
            ),
        )

    @pytest.mark.asyncio
    async def test_convert_prompt(
        self,
        converters: CortexConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt."""
        # Create a simple prompt
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage(
                    content=[PromptTextContent(text="Hello, world!")],
                ),
            ],
        )

        # Convert the prompt
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt)

        # Check that the result is a CortexPrompt
        assert isinstance(result, CortexPrompt)

        # Check that the prompt has the expected structure
        assert result.messages is not None
        assert len(result.messages) == 2
        assert result.messages[0].role == "system"
        assert result.messages[0].content == "You are a helpful assistant."
        assert result.messages[1].role == "user"
        assert result.messages[1].content == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tools(
        self,
        converters: CortexConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with tools."""
        # Create a tool
        get_weather_tool = ToolDefinition(
            name="get_weather",
            description="Get the weather for a location",
            input_schema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get weather for",
                    },
                },
                "required": ["location"],
            },
            function=lambda location: {"temp": 72, "condition": "sunny"},
        )

        # Create a prompt with the tool
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage(
                    content=[PromptTextContent(text="What's the weather in New York?")],
                ),
            ],
            tools=[get_weather_tool],
        )

        # Convert the prompt
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt)

        # Check that the result is a CortexPrompt
        assert isinstance(result, CortexPrompt)

        # Check that the prompt has the expected structure
        assert result.messages is not None
        assert len(result.messages) == 2
        assert result.messages[0].role == "system"
        assert result.messages[0].content == "You are a helpful assistant."
        assert result.messages[1].role == "user"
        assert result.messages[1].content == "What's the weather in New York?"

        # Check that the tool config is present
        assert result.tools is not None
        assert len(result.tools) == 1
        assert result.tools[0].name == "get_weather"
        assert result.tools[0].description == "Get the weather for a location"
        assert result.tools[0].input_schema == {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location to get weather for",
                },
            },
            "required": ["location"],
        }

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tool_cycle(
        self,
        converters: CortexConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt including a full tool use/result cycle."""
        get_weather_tool = ToolDefinition(
            name="get_weather",
            description="Get weather",
            input_schema={},
            function=lambda: None,
        )
        prompt = Prompt(
            messages=[
                PromptUserMessage(
                    content=[PromptTextContent(text="What's the weather?")],
                ),
                PromptAgentMessage(
                    content=[
                        PromptToolUseContent(
                            tool_call_id="call1",
                            tool_name="get_weather",
                            tool_input_raw="{}",
                        ),
                    ],
                ),
                PromptUserMessage(
                    content=[
                        PromptToolResultContent(
                            tool_call_id="call1",
                            tool_name="get_weather",
                            content=[PromptTextContent(text='{"temp": 70}')],
                        ),
                    ],
                ),
            ],
            tools=[get_weather_tool],
        )

        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt)

        assert isinstance(result, CortexPrompt)
        assert result.messages is not None
        # System (None) + User + Assistant (Tool Use) + User (Tool Result)
        assert len(result.messages) == 3
        assert result.messages[0].role == "user"
        assert result.messages[0].content == "What's the weather?"
        assert result.messages[1].role == "assistant"
        # Cortex never allows for empty text content, if it ever is we inject
        # a "." to avoid Cortex API errors
        assert result.messages[1].content == "."
        assert result.messages[1].content_list is not None
        assert len(result.messages[1].content_list) == 1
        assert result.messages[1].content_list[0].type == "tool_use"
        assert result.messages[1].content_list[0].tool_use is not None
        assert result.messages[1].content_list[0].tool_use.tool_use_id == "call1"
        assert result.messages[2].role == "user"
        # Check the fixup for empty content with tool results
        assert result.messages[2].content == "Tool results:"
        assert result.messages[2].content_list is not None
        assert len(result.messages[2].content_list) == 1
        assert result.messages[2].content_list[0].type == "tool_results"
        assert result.messages[2].content_list[0].tool_results is not None
        assert result.messages[2].content_list[0].tool_results.tool_use_id == "call1"
        assert result.messages[2].content_list[0].tool_results.content[0].text == (
            '{"temp": 70}'
        )

        assert result.tools is not None
        assert len(result.tools) == 1

    @pytest.mark.asyncio
    async def test_convert_prompt_with_message_collapsing(
        self,
        converters: CortexConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt where messages should be collapsed."""
        # In Cortex, we can't have "runs" of the same message right now,
        # so we need to collapse them manually. When we do this, we use two
        # newlines to separate the collapsed messages.

        prompt = Prompt(
            messages=[
                PromptUserMessage(content=[PromptTextContent(text="Hello.")]),
                PromptUserMessage(content=[PromptTextContent(text="Are you there?")]),
                PromptAgentMessage(content=[PromptTextContent(text="Hi!")]),
                PromptAgentMessage(content=[PromptTextContent(text="How can I help?")]),
            ],
        )

        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt)

        assert isinstance(result, CortexPrompt)
        assert result.messages is not None
        # System (None) + User (Collapsed) + Assistant (Collapsed)
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        # Check collapsed content
        assert result.messages[0].content == "Hello.\n\nAre you there?"
        assert result.messages[0].content_list == []
        assert result.messages[1].role == "assistant"
        # Check collapsed content
        assert result.messages[1].content == "Hi!\n\nHow can I help?"
        assert result.messages[1].content_list == []
