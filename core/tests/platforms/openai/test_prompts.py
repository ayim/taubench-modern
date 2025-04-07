"""Unit tests for the OpenAI platform prompts."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt


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
    def openai_prompt(self, messages) -> OpenAIPrompt:
        """Create an OpenAI prompt for testing."""
        return OpenAIPrompt(
            messages=messages,
            temperature=0.0,
            top_p=1.0,
            max_tokens=4096,
        )

    def test_as_platform_request(self, openai_prompt: OpenAIPrompt) -> None:
        """Test converting to platform request."""
        request = openai_prompt.as_platform_request(model="gpt-4-turbo")

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4-turbo-2024-04-09"
        assert len(request["messages"]) == 2
        assert request["messages"][0]["role"] == "system"
        assert request["messages"][0]["content"] == "You are a helpful assistant."
        assert request["messages"][1]["role"] == "user"
        assert request["messages"][1]["content"] == "Hello, world!"

    def test_as_platform_request_with_stream(self, openai_prompt: OpenAIPrompt) -> None:
        """Test converting to platform request with streaming enabled."""
        request = openai_prompt.as_platform_request(model="gpt-4-turbo", stream=True)

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4-turbo-2024-04-09"
        assert len(request["messages"]) == 2
        assert request["messages"][0]["role"] == "system"
        assert request["messages"][1]["role"] == "user"
        assert request["stream"] is True

    def test_as_platform_request_no_tools(self) -> None:
        """Test converting to platform request with no tools."""
        from openai.types.chat import (
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

        openai_prompt = OpenAIPrompt(
            messages=messages,
        )

        request = openai_prompt.as_platform_request(model="gpt-4-turbo")

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4-turbo-2024-04-09"
        assert len(request["messages"]) == 2
        assert "tools" not in request

    def test_as_platform_request_with_tools(self) -> None:
        """Test converting to platform request with tools."""
        from openai.types.chat import (
            ChatCompletionMessageParam,
            ChatCompletionSystemMessageParam,
            ChatCompletionToolParam,
            ChatCompletionUserMessageParam,
        )
        from openai.types.shared_params.function_definition import FunctionDefinition

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

        openai_prompt = OpenAIPrompt(
            messages=messages,
            tools=[tool_param],
        )

        request = openai_prompt.as_platform_request(model="gpt-4-turbo")

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4-turbo-2024-04-09"
        assert len(request["messages"]) == 2
        assert "tools" in request
        assert len(request["tools"]) == 1
        assert request["tools"][0]["function"]["name"] == "test-tool"

    def test_as_platform_request_with_reasoning_models(self) -> None:
        """Test converting to platform request with reasoning models."""
        from openai.types.chat import (
            ChatCompletionMessageParam,
            ChatCompletionUserMessageParam,
        )

        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionUserMessageParam(
                role="user",
                content="Hello, world!",
            ),
        ]
        openai_prompt = OpenAIPrompt(
            messages=messages,
        )

        for model in ["o1", "o3-mini"]:
            # Test with high reasoning
            high_model = f"{model}-high"
            high_request = openai_prompt.as_platform_request(model=high_model)
            # not asserting model id because it's not always the same
            # plus, verified model id is appropriately set
            # in the above test with gpt-4-turbo.
            assert "reasoning_effort" in high_request
            assert high_request["reasoning_effort"] == "high"

            # Test with low reasoning
            low_model = f"{model}-low"
            low_request = openai_prompt.as_platform_request(model=low_model)
            # not asserting model id because it's not always the same
            assert "reasoning_effort" in low_request
            assert low_request["reasoning_effort"] == "low"

    def test_prompt_properties(self) -> None:
        """Test prompt properties and defaults."""
        from openai.types.chat import (
            ChatCompletionMessageParam,
            ChatCompletionToolParam,
            ChatCompletionUserMessageParam,
        )
        from openai.types.shared_params.function_definition import FunctionDefinition

        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionUserMessageParam(role="user", content="Hello"),
        ]
        # Test with defaults
        prompt = OpenAIPrompt(messages=messages)
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
