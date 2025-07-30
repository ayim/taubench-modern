"""Unit tests for the OpenAI platform prompts."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.groq.prompts import GroqPrompt


class TestOpenAIPrompt:
    """Tests for the OpenAI prompt."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def messages(self):
        """Create a list of messages for testing."""
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, world!"},
        ]

    @pytest.fixture
    def groq_prompt(self, messages) -> GroqPrompt:
        """Create an OpenAI prompt for testing."""
        return GroqPrompt(
            messages=messages,
            temperature=0.0,
            top_p=1.0,
            max_tokens=4096,
        )

    def test_as_platform_request(self, groq_prompt: GroqPrompt) -> None:
        """Test converting to platform request."""
        request = groq_prompt.as_platform_request(model="llama-3.3")

        assert isinstance(request, dict)
        assert request["model"] == "llama-3.3-70b-versatile"
        assert len(request["messages"]) == 2
        assert request["messages"][0]["role"] == "system"
        assert request["messages"][0]["content"] == "You are a helpful assistant."
        assert request["messages"][1]["role"] == "user"
        assert request["messages"][1]["content"] == "Hello, world!"

    def test_as_platform_request_with_stream(self, groq_prompt: GroqPrompt) -> None:
        """Test converting to platform request with streaming enabled."""
        request = groq_prompt.as_platform_request(model="llama-3.3", stream=True)

        assert isinstance(request, dict)
        assert request["model"] == "llama-3.3-70b-versatile"
        assert len(request["messages"]) == 2
        assert request["messages"][0]["role"] == "system"
        assert request["messages"][1]["role"] == "user"
        assert request["stream"] is True

    def test_as_platform_request_no_tools(self) -> None:
        """Test converting to platform request with no tools."""
        from groq.types.chat import (
            ChatCompletionMessageParam,
            ChatCompletionSystemMessageParam,
            ChatCompletionUserMessageParam,
        )

        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(
                role="system",
                content="You are a helpful assistant.",
            ),
            ChatCompletionUserMessageParam(
                role="user",
                content="Hello, world!",
            ),
        ]

        prompt = GroqPrompt(
            messages=messages,
        )

        request = prompt.as_platform_request(model="llama-3.3")

        assert isinstance(request, dict)
        assert request["model"] == "llama-3.3-70b-versatile"
        assert len(request["messages"]) == 2
        assert "tools" not in request

    def test_as_platform_request_with_tools(self) -> None:
        """Test converting to platform request with tools."""
        from groq.types.chat import (
            ChatCompletionMessageParam,
            ChatCompletionSystemMessageParam,
            ChatCompletionToolParam,
            ChatCompletionUserMessageParam,
        )
        from groq.types.shared_params.function_definition import FunctionDefinition

        tool_def = FunctionDefinition(
            name="test-tool",
            description="A test tool",
            parameters={
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

        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(
                role="system",
                content="You are a helpful assistant.",
            ),
            ChatCompletionUserMessageParam(
                role="user",
                content="Hello, world!",
            ),
        ]

        tool_param = ChatCompletionToolParam(
            type="function",
            function=tool_def,
        )

        prompt = GroqPrompt(
            messages=messages,
            tools=[tool_param],
        )

        request = prompt.as_platform_request(model="llama-3.3")

        assert isinstance(request, dict)
        assert request["model"] == "llama-3.3-70b-versatile"
        assert len(request["messages"]) == 2
        assert "tools" in request
        assert len(request["tools"]) == 1
        assert request["tools"][0]["function"]["name"] == "test-tool"

    def test_prompt_properties(self) -> None:
        """Test prompt properties and defaults."""
        from groq.types.chat import (
            ChatCompletionMessageParam,
            ChatCompletionToolParam,
            ChatCompletionUserMessageParam,
        )
        from groq.types.shared_params.function_definition import FunctionDefinition

        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionUserMessageParam(role="user", content="Hello"),
        ]
        # Test with defaults
        prompt = GroqPrompt(messages=messages)
        assert prompt.messages == messages
        assert prompt.temperature == 0.0
        assert prompt.top_p == 1.0
        assert prompt.max_tokens == 4096
        assert prompt.tools is None

        # Test with custom values
        tools = [
            ChatCompletionToolParam(
                type="function",
                function=FunctionDefinition(
                    name="test",
                    description="Test tool",
                    parameters={},
                ),
            ),
        ]
        prompt = GroqPrompt(
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
