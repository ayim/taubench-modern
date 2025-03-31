"""Unit tests for the OpenAI platform converters."""

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.converters import OpenAIConverters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
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
        from unittest.mock import MagicMock

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
    async def test_convert_image_content(self, converters: OpenAIConverters) -> None:
        """Test converting image content."""
        content = PromptImageContent(
            mime_type="image/jpeg",
            value="base64_encoded_image",
            sub_type="url",
        )
        result = await converters.convert_image_content(content)

        assert isinstance(result, dict)
        assert result["type"] == "image_url"
        assert result["image_url"]["url"] == "base64_encoded_image"

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(self, converters: OpenAIConverters) -> None:
        """Test converting tool use content."""
        content = PromptToolUseContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            tool_input_raw={"key": "value"},
        )
        result = await converters.convert_tool_use_content(content)

        assert isinstance(result, dict)
        assert result["type"] == "function_call"
        assert result["function_call"]["name"] == "test-tool"
        assert result["function_call"]["arguments"] == content.tool_input

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
        result = await converters.convert_prompt(finalized_prompt)

        assert isinstance(result, OpenAIPrompt)
        request = result.as_platform_request(model="gpt-4")
        assert isinstance(request, dict)
        assert request["model"] == "gpt-4"
        assert request["messages"] == [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, world!",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "base64_encoded_image",
                            "detail": "high_res",
                        },
                    },
                ],
            },
        ]

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
        request = result.as_platform_request(model="gpt-4")
        assert isinstance(request, dict)
        assert request["model"] == "gpt-4"
        assert request["messages"] == [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, world!",
                    },
                ],
            },
        ]
        assert request["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "test-tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "A test key",
                            },
                        },
                        "required": ["key"],
                    },
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tool_choice(
        self,
        converters: OpenAIConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with tool choice."""
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
            tool_choice="test-tool",
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(finalized_prompt)

        assert isinstance(result, OpenAIPrompt)
        request = result.as_platform_request(model="gpt-4")
        assert isinstance(request, dict)
        assert request["model"] == "gpt-4"
        assert request["messages"] == [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, world!",
                    },
                ],
            },
        ]
        assert request["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "test-tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "A test key",
                            },
                        },
                        "required": ["key"],
                    },
                },
            },
        ]
        assert request["tool_choice"] == {
            "type": "function",
            "function": {"name": "test-tool"},
        }
