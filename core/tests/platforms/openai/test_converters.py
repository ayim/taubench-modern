"""Unit tests for the OpenAI platform converters."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.converters import OpenAIConverters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.platforms.openai.types import (
    OpenAIPromptContent,
    OpenAIPromptToolSpec,
)
from agent_platform.core.prompts import (
    Prompt,
    PromptImageContent,
    PromptTextContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.tools import ToolDefinition


class TestOpenAIConverters:
    """Tests for the OpenAI converters."""

    @pytest.fixture
    def converters(self) -> OpenAIConverters:
        """Create a converter instance for testing."""
        return OpenAIConverters()

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a kernel instance for testing."""
        return MagicMock(spec=Kernel)

    @pytest.mark.asyncio
    async def test_convert_text_content(self, converters: OpenAIConverters) -> None:
        """Test converting text content."""
        content = PromptTextContent(text="Hello, world!")
        result = await converters.convert_text_content(content)

        assert isinstance(result, OpenAIPromptContent)
        assert result.type == "text"
        assert result.text == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_image_content_not_implemented(
        self, converters: OpenAIConverters
    ) -> None:
        """Test converting image content."""
        content = PromptImageContent(
            mime_type="image/jpeg",
            value="base64_encoded_image",
            sub_type="url",
        )

        with pytest.raises(NotImplementedError, match="Image not supported yet"):
            await converters.convert_image_content(content)

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(self, converters: OpenAIConverters) -> None:
        """Test converting tool use content."""
        content = PromptToolUseContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            tool_input_raw='{"key": "value"}',
        )
        result = await converters.convert_tool_use_content(content)

        assert isinstance(result, OpenAIPromptContent)
        assert result.type == "tool_use"
        assert result.tool_use is not None
        assert result.tool_use.tool_use_id == "test-tool-call-id"
        assert result.tool_use.name == "test-tool"

    @pytest.mark.asyncio
    async def test_convert_prompt_image_content_not_implemented(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with image content."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage(
                    [
                        PromptTextContent(text="Hello, world!"),
                        PromptImageContent(
                            mime_type="image/jpeg",
                            value="base64_encoded_image",
                            sub_type="url",
                        ),
                    ],
                ),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)

        # This should fail because image content is not supported
        with pytest.raises(NotImplementedError, match="Image not supported yet"):
            await converters.convert_prompt(finalized_prompt)

    @pytest.mark.asyncio
    async def test_convert_prompt_text_only(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with text content only."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt)

        assert isinstance(result, OpenAIPrompt)
        assert result.messages is not None
        assert len(result.messages) == 2
        assert result.messages[0].role == "system"
        assert result.messages[0].content == "You are a helpful assistant."
        assert result.messages[1].role == "user"
        assert "Hello, world!" in result.messages[1].content

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tools(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with tools."""
        tool = ToolDefinition(
            name="test-tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "A test key",
                    },
                },
                "required": ["key"],
            },
            function=lambda key: key,
        )
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
            tools=[tool],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt)

        assert isinstance(result, OpenAIPrompt)
        assert result.tools is not None
        assert len(result.tools) == 1
        assert result.tools[0].name == "test-tool"
        assert result.tools[0].description == "A test tool"
        assert result.tools[0].input_schema is not None
        assert "properties" in result.tools[0].input_schema

        # Test the conversion to platform request
        request = result.as_platform_request("gpt-4")
        assert "tools" in request
        assert len(request["tools"]) == 1
        assert request["tools"][0]["function"]["name"] == "test-tool"

    @pytest.mark.asyncio
    async def test_system_instruction_conversion(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test converting system instruction."""
        system_msg = await converters._convert_system_instruction("Test instruction")
        assert len(system_msg) == 1
        assert system_msg[0].role == "system"
        assert system_msg[0].content == "Test instruction"

        # Test with None
        empty_system = await converters._convert_system_instruction(None)
        assert len(empty_system) == 0

    @pytest.mark.asyncio
    async def test_tool_conversion(self, converters: OpenAIConverters) -> None:
        """Test converting tools."""
        tool = ToolDefinition(
            name="test-tool",
            description="A test tool",
            input_schema={"type": "object"},
            function=lambda: None,
        )

        tools = await converters._convert_tools([tool])
        assert len(tools) == 1
        assert isinstance(tools[0], OpenAIPromptToolSpec)
        assert tools[0].name == "test-tool"
        assert tools[0].description == "A test tool"
