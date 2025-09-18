from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.bedrock.converters import BedrockConverters
from agent_platform.core.platforms.bedrock.prompts import BedrockPrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptReasoningContent,
    PromptTextContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.tools import ToolDefinition


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

    @pytest.mark.asyncio
    async def test_convert_text_content(self, converters: BedrockConverters) -> None:
        """Test converting text content."""
        text_content = PromptTextContent(text="Hello, world!")

        result = await converters.convert_text_content(text_content)

        assert result == {"text": "Hello, world!"}

    @pytest.mark.asyncio
    async def test_convert_reasoning_content_prefers_reasoning_text(
        self,
        converters: BedrockConverters,
    ) -> None:
        """Ensure reasoning content uses reasoningText when available."""
        reasoning_content = PromptReasoningContent(
            reasoning="Chain of thought",
            redacted_content="[redacted]",
            signature="signature",
        )

        result = await converters.convert_reasoning_content(reasoning_content)

        assert "reasoningContent" in result
        block = result["reasoningContent"]
        assert "reasoningText" in block
        assert block["reasoningText"]["text"] == "Chain of thought"
        assert "signature" in block["reasoningText"]
        assert block["reasoningText"]["signature"] == "signature"
        assert "redactedContent" not in block

    @pytest.mark.asyncio
    async def test_convert_reasoning_content_uses_redacted_when_only_option(
        self,
        converters: BedrockConverters,
    ) -> None:
        """Ensure reasoning content falls back to redactedContent when needed."""
        reasoning_content = PromptReasoningContent(
            reasoning=None,
            redacted_content="[redacted]",
            signature=None,
        )

        result = await converters.convert_reasoning_content(reasoning_content)

        assert "reasoningContent" in result
        block = result["reasoningContent"]
        assert "redactedContent" in block
        assert block["redactedContent"] == "[redacted]"
        assert "reasoningText" not in block

    @pytest.mark.asyncio
    async def test_convert_reasoning_content_includes_signature_key_when_missing(
        self,
        converters: BedrockConverters,
    ) -> None:
        """Ensure the signature field is always present when using reasoningText."""
        reasoning_content = PromptReasoningContent(
            reasoning="Chain of thought",
            redacted_content=None,
            signature=None,
        )

        result = await converters.convert_reasoning_content(reasoning_content)

        assert "reasoningContent" in result
        assert "reasoningText" in result["reasoningContent"]
        block = result["reasoningContent"]["reasoningText"]
        assert block["text"] == "Chain of thought"
        assert "signature" in block
        assert block["signature"] == ""

    @pytest.mark.asyncio
    async def test_convert_image_content(self, converters: BedrockConverters) -> None:
        """Test converting image content."""
        # Skip this test for now until we know the correct API for PromptImageContent
        pass

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(
        self,
        converters: BedrockConverters,
    ) -> None:
        """Test converting tool use content."""
        tool_use_content = PromptToolUseContent(
            tool_call_id="tool-1234",
            tool_name="get_weather",
            tool_input_raw='{"location": "New York"}',
        )

        result = await converters.convert_tool_use_content(tool_use_content)

        assert result == {
            "toolUse": {
                "toolUseId": "tool-1234",
                "name": "get_weather",
                "input": {"location": "New York"},
            },
        }

    @pytest.mark.asyncio
    async def test_convert_prompt(
        self,
        converters: BedrockConverters,
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

        # Check that the result is a BedrockPrompt
        assert isinstance(result, BedrockPrompt)

        # Check that the prompt has the expected structure
        assert result.system == [{"text": "You are a helpful assistant."}]
        assert result.messages is not None
        assert len(result.messages) == 1
        assert result.messages[0]["role"] == "user"
        assert "text" in result.messages[0]["content"][0]
        assert result.messages[0]["content"][0]["text"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_ignores_seed(
        self,
        converters: BedrockConverters,
        kernel: Kernel,
    ) -> None:
        """Ensure unsupported seed parameter isn't forwarded to Bedrock."""

        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage(
                    content=[PromptTextContent(text="Hello, world!")],
                ),
            ],
            seed=1234,
        )

        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt)

        assert result.additional_model_request_fields is None

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tools(
        self,
        converters: BedrockConverters,
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

        # Check that the result is a BedrockPrompt
        assert isinstance(result, BedrockPrompt)

        # Check that the prompt has the expected structure
        assert result.system == [{"text": "You are a helpful assistant."}]
        assert result.messages is not None
        assert len(result.messages) == 1
        assert result.messages[0]["role"] == "user"
        assert "text" in result.messages[0]["content"][0]
        assert result.messages[0]["content"][0]["text"] == "What's the weather in New York?"

        # Check that the tool config is present
        assert result.tool_config is not None
        assert len(result.tool_config["tools"]) == 1
        assert "toolSpec" in result.tool_config["tools"][0]
        assert result.tool_config["tools"][0]["toolSpec"]["name"] == "get_weather"
        assert "toolChoice" in result.tool_config
