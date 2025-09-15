"""Unit tests for the AzureOpenAI platform converters."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.azure.converters import AzureOpenAIConverters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptImageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


class TestAzureOpenAIConverters:
    """Test converters for AzureOpenAI."""

    @pytest.fixture
    def converters(self) -> AzureOpenAIConverters:
        """Create a converter instance for testing."""
        return AzureOpenAIConverters()

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a kernel instance for testing."""
        return MagicMock(spec=Kernel)

    @pytest.mark.asyncio
    async def test_convert_text_content(
        self,
        converters: AzureOpenAIConverters,
    ) -> None:
        """Test converting text content."""
        content = PromptTextContent(text="Hello, world!")
        result = await converters.convert_text_content(content)

        assert isinstance(result, dict)
        assert result.get("type") == "input_text"
        assert result.get("text") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_image_content_url(
        self,
        converters: AzureOpenAIConverters,
    ) -> None:
        """Test converting image content."""

        result = await converters.convert_image_content(
            PromptImageContent(
                mime_type="image/png",
                sub_type="url",
                value="https://example.com/image.png",
                detail="high_res",
            )
        )
        assert isinstance(result, dict)
        assert result.get("type") == "input_image"
        assert result.get("detail") == "high"
        image_url = result.get("image_url")
        assert isinstance(image_url, str)
        assert image_url == "https://example.com/image.png"

    @pytest.mark.asyncio
    async def test_convert_image_content_b64(
        self,
        converters: AzureOpenAIConverters,
        b64_image_prompt_content: PromptImageContent,
    ) -> None:
        """Test converting image content."""

        result = await converters.convert_image_content(b64_image_prompt_content)
        assert isinstance(result, dict)
        assert result.get("type") == "input_image"
        image_url = result.get("image_url")
        assert isinstance(image_url, str)
        assert image_url.startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(
        self,
        converters: AzureOpenAIConverters,
    ) -> None:
        """Test converting tool use content."""
        content = PromptToolUseContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            tool_input_raw='{"key": "value"}',
        )
        result = await converters.convert_tool_use_content(content)

        assert result.get("type") == "function_call"
        assert result.get("call_id") == "test-tool-call-id"
        assert result.get("name") == "test-tool"

    @pytest.mark.asyncio
    async def test_convert_prompt(
        self,
        converters: AzureOpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert result.instructions == "You are a helpful assistant."
        assert isinstance(result.input, list)
        assert len(result.input) == 1
        user_msg = result.input[0]
        assert user_msg.get("role") == "user"
        content_list = user_msg.get("content")
        assert isinstance(content_list, list)
        assert content_list[0].get("type") == "input_text"
        assert content_list[0].get("text") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_o4_mini(
        self,
        converters: AzureOpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt for o4-mini model."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(
            finalized_prompt,
            model_id="o4-mini",
        )

        assert isinstance(result, OpenAIPrompt)
        assert result.instructions == "You are a helpful assistant."
        assert isinstance(result.input, list)
        assert len(result.input) == 1
        user_msg = result.input[0]
        assert user_msg.get("role") == "user"
        content_list = user_msg.get("content")
        assert isinstance(content_list, list)
        assert content_list[0].get("type") == "input_text"
        assert content_list[0].get("text") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tools(
        self,
        converters: AzureOpenAIConverters,
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
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert result.tools is not None
        assert len(result.tools) == 1
        tool_obj = result.tools[0]
        assert tool_obj.get("type") == "function"
        assert tool_obj.get("name") == "test-tool"
        assert tool_obj.get("description") == "A test tool"
        parameters = tool_obj.get("parameters")
        assert isinstance(parameters, dict)
        assert parameters.get("type") == "object"
        assert isinstance(parameters.get("properties"), dict)
        assert parameters.get("required") == ["key"]

    @pytest.mark.asyncio
    async def test_convert_tool_result_content(
        self,
        converters: AzureOpenAIConverters,
    ) -> None:
        """Test converting tool result content."""
        content = PromptToolResultContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            content=[PromptTextContent(text="Hello, world!")],
        )
        result = await converters.convert_tool_result_content(content)

        assert isinstance(result, dict)
        assert result.get("type") == "function_call_output"
        assert result.get("call_id") == "test-tool-call-id"
        assert result.get("output") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_with_no_messages(
        self,
        converters: AzureOpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with no messages."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert isinstance(result.input, list)
        assert len(result.input) == 0
        assert result.instructions == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_convert_prompt_with_no_system_instruction(
        self,
        converters: AzureOpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with no system instruction."""
        prompt = Prompt(
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert isinstance(result.input, list)
        assert len(result.input) == 1
        user_msg = result.input[0]
        assert user_msg.get("role") == "user"
        content_list = user_msg.get("content")
        assert isinstance(content_list, list)
        assert len(content_list) == 1
        first_part = content_list[0]
        assert isinstance(first_part, dict)
        assert first_part.get("type") == "input_text"
        assert first_part.get("text") == "Hello, world!"
        assert result.instructions is None

    @pytest.mark.asyncio
    async def test_tool_conversion(self, converters: AzureOpenAIConverters) -> None:
        """Test converting tools."""
        tool = ToolDefinition(
            name="test-tool",
            description="A test tool",
            input_schema={"type": "object"},
            function=lambda: None,
        )

        tools = await converters._convert_tools([tool])
        assert len(tools) == 1

        tool_obj = tools[0]
        assert tool_obj.get("type") == "function"
        assert tool_obj.get("name") == "test-tool"
        assert tool_obj.get("description") == "A test tool"
        parameters = tool_obj.get("parameters")
        assert isinstance(parameters, dict)
        assert parameters.get("type") == "object"

    @pytest.mark.asyncio
    async def test_system_instruction_conversion(
        self,
        converters: AzureOpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test system instruction presence via Azure converter output."""
        prompt = Prompt(
            system_instruction="Test instruction",
            messages=[PromptUserMessage([PromptTextContent(text="Hi")])],
        )
        finalized = await prompt.finalize_messages(kernel)
        converted = await converters.convert_prompt(finalized, model_id="gpt-4o")
        assert converted.instructions == "Test instruction"

        prompt2 = Prompt(messages=[PromptUserMessage([PromptTextContent(text="Hi")])])
        finalized2 = await prompt2.finalize_messages(kernel)
        converted2 = await converters.convert_prompt(finalized2, model_id="gpt-4o")
        assert converted2.instructions is None

    @pytest.mark.asyncio
    async def test_process_message_content(
        self,
        converters: AzureOpenAIConverters,
    ) -> None:
        """Test processing message content."""
        # Test with just text
        text_content = [PromptTextContent(text="Hello, world!")]
        result, tools = await converters._process_user_message_content(text_content)
        assert len(result) == 1
        assert result[0].get("type") == "input_text"
        assert result[0].get("text") == "Hello, world!"
        assert len(tools) == 0

        # Test with text and tool use
        mixed_content = [
            PromptTextContent(text="Hello, world!"),
            PromptToolResultContent(
                tool_call_id="test-id",
                tool_name="test-tool",
                content=[PromptTextContent(text="ok")],
            ),
        ]
        result, tools = await converters._process_user_message_content(mixed_content)
        assert len(result) == 1
        assert result[0].get("type") == "input_text"
        assert result[0].get("text") == "Hello, world!"
        assert len(tools) == 1
        assert tools[0].get("type") == "function_call_output"
