"""Unit tests for the OpenAI platform prompts."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptImageContent,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


class TestOpenAIPrompt:
    """Tests for the OpenAI prompt."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    async def prompt(self, kernel: Kernel) -> Prompt:
        """Create a prompt for testing."""
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
        await prompt.finalize_messages(kernel)
        return prompt

    @pytest.fixture
    def openai_prompt(self, prompt: Prompt) -> OpenAIPrompt:
        """Create an OpenAI prompt for testing."""
        return OpenAIPrompt(prompt=prompt)

    def test_as_platform_request(self, openai_prompt: OpenAIPrompt) -> None:
        """Test converting to platform request."""
        request = openai_prompt.as_platform_request(model="gpt-4")

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
    async def test_as_platform_request_with_tools(self, kernel: Kernel) -> None:
        """Test converting to platform request with tools."""
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
            function=lambda key: {"result": key},
        )
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
            tools=[tool],
        )
        await prompt.finalize_messages(kernel)
        openai_prompt = OpenAIPrompt(prompt=prompt)
        request = openai_prompt.as_platform_request(model="gpt-4")

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
    async def test_as_platform_request_with_tool_choice(self, kernel: Kernel) -> None:
        """Test converting to platform request with tool choice."""
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
            function=lambda key: {"result": key},
        )
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
            tools=[tool],
            tool_choice="test-tool",
        )
        await prompt.finalize_messages(kernel)
        openai_prompt = OpenAIPrompt(prompt=prompt)
        request = openai_prompt.as_platform_request(model="gpt-4")

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

    @pytest.mark.asyncio
    async def test_as_platform_request_with_additional_fields(
        self,
        kernel: Kernel,
    ) -> None:
        """Test converting to platform request with additional fields."""
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
            temperature=0.7,
            max_output_tokens=100,
            top_p=0.9,
            stop_sequences=["\n"],
        )
        await prompt.finalize_messages(kernel)
        openai_prompt = OpenAIPrompt(prompt=prompt)
        request = openai_prompt.as_platform_request(model="gpt-4")

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
        assert request["temperature"] == 0.7
        assert request["max_tokens"] == 100
        assert request["top_p"] == 0.9
        assert request["stop"] == ["\n"]
