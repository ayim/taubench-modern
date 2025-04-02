"""Unit tests for the OpenAI platform prompts."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.platforms.openai.types import (
    OpenAIPromptMessage,
    OpenAIPromptToolSpec,
)


class TestOpenAIPrompt:
    """Tests for the OpenAI prompt."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def messages(self) -> list[OpenAIPromptMessage]:
        """Create a list of messages for testing."""
        return [
            OpenAIPromptMessage(role="system", content="You are a helpful assistant."),
            OpenAIPromptMessage(role="user", content="Hello, world!"),
        ]

    @pytest.fixture
    def openai_prompt(self, messages: list[OpenAIPromptMessage]) -> OpenAIPrompt:
        """Create an OpenAI prompt for testing."""
        return OpenAIPrompt(
            messages=messages,
            temperature=0.0,
            top_p=1.0,
            max_tokens=4096,
        )

    def test_as_platform_request(self, openai_prompt: OpenAIPrompt) -> None:
        """Test converting to platform request."""
        request = openai_prompt.as_platform_request(model="gpt-4")

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4"
        assert len(request["messages"]) == 2
        assert request["messages"][0]["role"] == "system"
        assert request["messages"][0]["content"] == "You are a helpful assistant."
        assert request["messages"][1]["role"] == "user"
        assert request["messages"][1]["content"] == "Hello, world!"

    def test_as_platform_request_with_stream(self, openai_prompt: OpenAIPrompt) -> None:
        """Test converting to platform request with streaming enabled."""
        request = openai_prompt.as_platform_request(model="gpt-4", stream=True)

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4"
        assert len(request["messages"]) == 2
        assert request["messages"][0]["role"] == "system"
        assert request["messages"][1]["role"] == "user"

    def test_as_platform_request_with_tools(self) -> None:
        """Test converting to platform request with tools."""
        tool_spec = OpenAIPromptToolSpec(
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
        )

        messages = [
            OpenAIPromptMessage(role="system", content="You are a helpful assistant."),
            OpenAIPromptMessage(role="user", content="Hello, world!"),
        ]

        openai_prompt = OpenAIPrompt(
            messages=messages,
            tools=[tool_spec],
        )

        request = openai_prompt.as_platform_request(model="gpt-4")

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4"
        assert len(request["messages"]) == 2
        assert "tools" in request
        assert len(request["tools"]) == 1
        assert request["tools"][0]["function"]["name"] == "test-tool"
        assert request["tools"][0]["function"]["description"] == "A test tool"
        assert "parameters" in request["tools"][0]["function"]

    def test_prompt_properties(self) -> None:
        """Test prompt properties and defaults."""
        messages = [OpenAIPromptMessage(role="user", content="Hello")]

        # Test with defaults
        prompt = OpenAIPrompt(messages=messages)
        assert prompt.messages == messages
        assert prompt.temperature == 0.0
        assert prompt.top_p == 1.0
        assert prompt.max_tokens == 4096
        assert prompt.tools == []

        # Test with custom values
        tools = [
            OpenAIPromptToolSpec(name="test", description="Test tool", input_schema={}),
        ]
        prompt = OpenAIPrompt(
            messages=messages,
            tools=tools,
            temperature=0.7,
            top_p=0.9,
            max_tokens=1000,
        )
        assert prompt.messages == messages
        assert prompt.tools == tools
        assert prompt.temperature == 0.7
        assert prompt.top_p == 0.9
        assert prompt.max_tokens == 1000
