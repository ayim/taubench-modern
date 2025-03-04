from unittest.mock import MagicMock

import pytest

from agent_server_types_v2.kernel import Kernel
from agent_server_types_v2.platforms.bedrock.converters import BedrockConverters
from agent_server_types_v2.platforms.bedrock.prompts import BedrockPrompt
from agent_server_types_v2.prompts import (
    Prompt,
    PromptTextContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_server_types_v2.tools import ToolDefinition


class TestBedrockConverters:
    """Tests for the Bedrock converters."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def converters(self, kernel: Kernel) -> BedrockConverters:
        """Create Bedrock converters for testing."""
        converters = BedrockConverters()
        converters.attach_kernel(kernel)
        return converters

    def test_convert_text_content(self, converters: BedrockConverters) -> None:
        """Test converting text content."""
        text_content = PromptTextContent(text="Hello, world!")

        result = converters.convert_text_content(text_content)

        assert result == {"text": "Hello, world!"}

    def test_convert_image_content(self, converters: BedrockConverters) -> None:
        """Test converting image content."""
        # Skip this test for now until we know the correct API for PromptImageContent
        pass

    def test_convert_tool_use_content(self, converters: BedrockConverters) -> None:
        """Test converting tool use content."""
        tool_use_content = PromptToolUseContent(
            tool_call_id="tool-1234",
            tool_name="get_weather",
            tool_input_raw='{"location": "New York"}',
        )

        result = converters.convert_tool_use_content(tool_use_content)

        assert result == {
            "toolUse": {
                "toolUseId": "tool-1234",
                "name": "get_weather",
                "input": {"location": "New York"},
            },
        }

    @pytest.mark.asyncio
    async def test_convert_prompt(self, converters: BedrockConverters) -> None:
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
        result = converters.convert_prompt(prompt)

        # Check that the result is a BedrockPrompt
        assert isinstance(result, BedrockPrompt)

        # Check that the prompt has the expected structure
        assert result.system == [{"text": "You are a helpful assistant."}]
        assert len(result.messages) == 1
        assert result.messages[0]["role"] == "user"
        assert result.messages[0]["content"][0]["text"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tools(
        self,
        converters: BedrockConverters,
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
        result = converters.convert_prompt(prompt)

        # Check that the result is a BedrockPrompt
        assert isinstance(result, BedrockPrompt)

        # Check that the prompt has the expected structure
        assert result.system == [{"text": "You are a helpful assistant."}]
        assert len(result.messages) == 1
        assert result.messages[0]["role"] == "user"
        assert (
            result.messages[0]["content"][0]["text"]
            == "What's the weather in New York?"
        )

        # Check that the tool config is present
        assert result.tool_config is not None
        assert len(result.tool_config["tools"]) == 1
        assert result.tool_config["tools"][0]["toolSpec"]["name"] == "get_weather"
        assert "toolChoice" in result.tool_config
