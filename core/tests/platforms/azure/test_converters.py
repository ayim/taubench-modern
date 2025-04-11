"""Unit tests for the AzureOpenAI platform converters."""

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from openai.types.chat import (
    ChatCompletionMessageToolCall,
)

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
        assert result["type"] == "text"
        assert result["text"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_image_content_not_implemented(
        self,
        converters: AzureOpenAIConverters,
    ) -> None:
        """Test converting image content."""
        content = PromptImageContent(
            mime_type="image/jpeg",
            value="base64_encoded_image",
            sub_type="url",
        )

        with pytest.raises(NotImplementedError):
            await converters.convert_image_content(content)

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

        assert isinstance(result, ChatCompletionMessageToolCall)
        assert result.id == "test-tool-call-id"
        assert result.function.name == "test-tool"

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
        assert result.messages is not None
        assert len(result.messages) == 2

        # Use .get() to safely access dictionary keys that might be optional
        system_msg = cast(dict[str, Any], result.messages[0])
        assert system_msg.get("role") == "developer"
        assert system_msg.get("content") == "You are a helpful assistant."

        user_msg = cast(dict[str, Any], result.messages[1])
        assert user_msg.get("role") == "user"
        assert user_msg.get("content") == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_o1_mini(
        self,
        converters: AzureOpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt for o1-mini model."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(
            finalized_prompt,
            model_id="o1-mini",
        )

        assert isinstance(result, OpenAIPrompt)
        assert result.messages is not None
        assert len(result.messages) == 2

        # Use .get() to safely access dictionary keys that might be optional
        system_msg = cast(dict[str, Any], result.messages[0])
        # Azure uses 'developer' role for system messages
        assert system_msg.get("role") == "developer"
        assert system_msg.get("content") == "You are a helpful assistant."

        user_msg = cast(dict[str, Any], result.messages[1])
        assert user_msg.get("role") == "user"
        assert user_msg.get("content") == "Hello, world!"

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

        # Handle both dictionary and object access patterns
        tool_obj = result.tools[0]
        if isinstance(tool_obj, dict):
            assert tool_obj.get("type") == "function"
            assert tool_obj.get("function", {}).get("name") == "test-tool"
        else:
            # If it's an object type
            assert getattr(tool_obj, "type", None) == "function"
            assert (
                getattr(getattr(tool_obj, "function", None), "name", None)
                == "test-tool"
            )

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
        assert result.get("role") == "tool"
        assert result.get("tool_call_id") == "test-tool-call-id"
        assert result.get("content") == "Hello, world!"

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
        assert result.messages is not None
        assert len(result.messages) == 1

        system_msg = cast(dict[str, Any], result.messages[0])
        assert system_msg.get("role") == "developer"
        assert system_msg.get("content") == "You are a helpful assistant."

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
        assert result.messages is not None
        assert len(result.messages) == 1

        user_msg = cast(dict[str, Any], result.messages[0])
        assert user_msg.get("role") == "user"
        assert user_msg.get("content") == "Hello, world!"

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

        # Check using the safer pattern for accessing tools
        tool_obj = tools[0]
        assert isinstance(tool_obj, dict)
        assert tool_obj.get("type") == "function"
        assert tool_obj.get("function", {}).get("name") == "test-tool"

    @pytest.mark.asyncio
    async def test_system_instruction_conversion(
        self,
        converters: AzureOpenAIConverters,
    ) -> None:
        """Test converting system instruction."""
        system_msg = await converters._convert_system_instruction_to_openai(
            "Test instruction",
            model_id="gpt-4o",
        )
        assert len(system_msg) == 1

        msg = cast(dict[str, Any], system_msg[0])
        assert msg.get("role") == "developer"
        assert msg.get("content") == "Test instruction"

        # Test with None
        empty_system = await converters._convert_system_instruction_to_openai(
            None,
            model_id="gpt-4o",
        )
        assert len(empty_system) == 0

        # Test with o1-mini (Azure handles all models the same way for system messages)
        o1_mini_system = await converters._convert_system_instruction_to_openai(
            "Test instruction",
            model_id="o1-mini",
        )
        assert len(o1_mini_system) == 1
        assert o1_mini_system[0].get("role") == "developer"
        assert o1_mini_system[0].get("content") == "Test instruction"

        # Test with o1-mini and None
        o1_mini_empty_system = await converters._convert_system_instruction_to_openai(
            None,
            model_id="o1-mini",
        )
        assert len(o1_mini_empty_system) == 0

    @pytest.mark.asyncio
    async def test_process_message_content(
        self,
        converters: AzureOpenAIConverters,
    ) -> None:
        """Test processing message content."""
        # Test with just text
        text_content = [PromptTextContent(text="Hello, world!")]
        result = await converters._process_message_content(text_content)
        assert result.get("text") == "Hello, world!"
        assert len(result.get("tool_calls", [])) == 0

        # Test with text and tool use
        mixed_content = [
            PromptTextContent(text="Hello, world!"),
            PromptToolUseContent(
                tool_call_id="test-id",
                tool_name="test-tool",
                tool_input_raw='{"key": "value"}',
            ),
        ]
        result = await converters._process_message_content(mixed_content)
        assert result.get("text") == "Hello, world!"
        tool_calls = result.get("tool_calls", [])
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "test-id"
        assert tool_calls[0].function.name == "test-tool"
