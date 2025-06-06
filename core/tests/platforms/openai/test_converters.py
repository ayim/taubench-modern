"""Unit tests for the OpenAI platform converters."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.converters import OpenAIConverters
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


class TestOpenAIConverters:
    """Test converters for OpenAI."""

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

        assert isinstance(result, dict)
        assert result["type"] == "text"
        assert result["text"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_image_content_url(
        self,
        converters: OpenAIConverters,
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
        assert result["type"] == "image_url"
        assert result["image_url"]["url"] == "https://example.com/image.png"
        assert "detail" in result["image_url"]
        assert result["image_url"]["detail"] == "high"

    @pytest.mark.asyncio
    async def test_convert_image_content_b64(
        self,
        converters: OpenAIConverters,
        b64_image_prompt_content: PromptImageContent,
    ) -> None:
        """Test converting image content."""

        result = await converters.convert_image_content(b64_image_prompt_content)
        assert isinstance(result, dict)
        assert result["type"] == "image_url"
        assert result["image_url"]["url"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(self, converters: OpenAIConverters) -> None:
        """Test converting tool use content."""
        content = PromptToolUseContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            tool_input_raw='{"key": "value"}',
        )
        result = await converters.convert_tool_use_content(content)

        assert result["type"] == "function"
        assert result["id"] == "test-tool-call-id"
        assert result["function"]["name"] == "test-tool"

    @pytest.mark.asyncio
    async def test_convert_prompt(
        self,
        converters: OpenAIConverters,
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

        developer_msg = result.messages[0]
        assert developer_msg["role"] == "developer"
        assert isinstance(developer_msg["content"], list)
        assert len(developer_msg["content"]) == 1
        assert developer_msg["content"][0]["type"] == "text"
        assert developer_msg["content"][0]["text"] == "You are a helpful assistant."

        user_msg = result.messages[1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert len(user_msg["content"]) == 1
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][0]["text"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt_o1_mini(
        self,
        converters: OpenAIConverters,
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
        result = await converters.convert_prompt(
            finalized_prompt,
            model_id="o1-mini-2024-07-18",
        )

        assert isinstance(result, OpenAIPrompt)
        assert result.messages is not None
        assert len(result.messages) == 2

        developer_msg = result.messages[0]
        # NOTE: here, for o1-mini, the role is indeed "user" as this
        # model does not support system/developer messages!!
        assert developer_msg["role"] == "user"
        assert isinstance(developer_msg["content"], list)
        assert len(developer_msg["content"]) == 1
        assert developer_msg["content"][0]["type"] == "text"
        assert developer_msg["content"][0]["text"] == "You are a helpful assistant."

        user_msg = result.messages[1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert len(user_msg["content"]) == 1
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][0]["text"] == "Hello, world!"

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
        result = await converters.convert_prompt(finalized_prompt, model_id="gpt-4o")

        assert isinstance(result, OpenAIPrompt)
        assert result.tools is not None
        assert len(result.tools) == 1

        tool_obj = result.tools[0]
        assert tool_obj["type"] == "function"
        assert tool_obj["function"]["name"] == "test-tool"
        assert "description" in tool_obj["function"]
        assert tool_obj["function"]["description"] == "A test tool"
        assert "parameters" in tool_obj["function"]
        assert tool_obj["function"]["parameters"]["type"] == "object"
        assert "properties" in tool_obj["function"]["parameters"]
        assert "required" in tool_obj["function"]["parameters"]
        assert tool_obj["function"]["parameters"]["required"] == ["key"]

    @pytest.mark.asyncio
    async def test_convert_tool_result_content(
        self,
        converters: OpenAIConverters,
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
        converters: OpenAIConverters,
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

        developer_msg = result.messages[0]
        assert developer_msg["role"] == "developer"
        assert isinstance(developer_msg["content"], list)
        assert len(developer_msg["content"]) == 1
        assert developer_msg["content"][0]["type"] == "text"
        assert developer_msg["content"][0]["text"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_convert_prompt_with_no_system_instruction(
        self,
        converters: OpenAIConverters,
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

        user_msg = result.messages[0]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert len(user_msg["content"]) == 1
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][0]["text"] == "Hello, world!"

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

        tool_obj = tools[0]
        assert tool_obj["type"] == "function"
        assert tool_obj["function"]["name"] == "test-tool"
        assert "description" in tool_obj["function"]
        assert tool_obj["function"]["description"] == "A test tool"
        assert "parameters" in tool_obj["function"]
        assert tool_obj["function"]["parameters"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_system_instruction_conversion(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test converting system instruction."""
        developer_msg = await converters._convert_system_instruction_to_openai(
            "Test instruction",
            model_id="gpt-4o",
        )
        assert len(developer_msg) == 1

        msg = developer_msg[0]
        assert msg["role"] == "developer"
        assert isinstance(msg["content"], list)
        assert len(msg["content"]) == 1
        assert msg["content"][0]["type"] == "text"
        assert msg["content"][0]["text"] == "Test instruction"

        # Test with None
        empty_system = await converters._convert_system_instruction_to_openai(
            None,
            model_id="gpt-4o",
        )
        assert len(empty_system) == 0

        # Test with o1-mini (which does not support system/developer messages)
        o1_mini_system = await converters._convert_system_instruction_to_openai(
            "Test instruction",
            model_id="o1-mini-2024-07-18",
        )
        assert len(o1_mini_system) == 1
        assert o1_mini_system[0]["role"] == "user"
        assert isinstance(o1_mini_system[0]["content"], list)
        assert len(o1_mini_system[0]["content"]) == 1
        assert o1_mini_system[0]["content"][0]["type"] == "text"
        assert o1_mini_system[0]["content"][0]["text"] == "Test instruction"

        # Test with o1-mini and None
        o1_mini_empty_system = await converters._convert_system_instruction_to_openai(
            None,
            model_id="o1-mini-2024-07-18",
        )
        assert len(o1_mini_empty_system) == 0

    @pytest.mark.asyncio
    async def test_process_message_content(
        self,
        converters: OpenAIConverters,
    ) -> None:
        """Test processing message content."""
        # Test with just text
        text_content = [PromptTextContent(text="Hello, world!")]
        result, tools = await converters._process_message_content(text_content)
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello, world!"
        assert len(tools) == 0

        # Test with text and tool use
        mixed_content = [
            PromptTextContent(text="Hello, world!"),
            PromptToolUseContent(
                tool_call_id="test-id",
                tool_name="test-tool",
                tool_input_raw='{"key": "value"}',
            ),
        ]
        result, tools = await converters._process_message_content(mixed_content)
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello, world!"
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "test-tool"
