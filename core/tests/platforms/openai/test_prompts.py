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
    def input_items(self):
        """Create a list of Responses API input items for testing."""
        return [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello, world!"}],
            }
        ]

    @pytest.fixture
    def openai_prompt(self, input_items) -> OpenAIPrompt:
        """Create an OpenAI prompt for testing."""
        return OpenAIPrompt(
            input=input_items,
            instructions="You are a helpful assistant.",
            temperature=0.0,
            top_p=1.0,
        )

    def test_as_platform_request(self, openai_prompt: OpenAIPrompt) -> None:
        """Test converting to platform request."""
        request = openai_prompt.as_platform_request(model="gpt-4o")

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4o"
        assert request["instructions"] == "You are a helpful assistant."
        assert len(request["input"]) == 1
        assert request["input"][0]["role"] == "user"

    def test_as_platform_request_with_stream(self, openai_prompt: OpenAIPrompt) -> None:
        """Test converting to platform request with streaming enabled."""
        request = openai_prompt.as_platform_request(model="gpt-4o", stream=True)

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4o"
        assert len(request["input"]) == 1
        assert request["input"][0]["role"] == "user"
        assert request["stream"] is True

    def test_as_platform_request_no_tools(self) -> None:
        """Test converting to platform request with no tools."""
        openai_prompt = OpenAIPrompt(
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello, world!"}],
                }
            ]
        )

        request = openai_prompt.as_platform_request(model="gpt-4o")

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4o"
        assert len(request["input"]) == 1
        assert request["tools"] == []

    def test_as_platform_request_with_tools(self) -> None:
        """Test converting to platform request with tools."""
        from openai.types.responses import FunctionToolParam

        tool_param: FunctionToolParam = {
            "type": "function",
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
            "strict": True,
        }

        openai_prompt = OpenAIPrompt(
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello, world!"}],
                }
            ],
            instructions="You are a helpful assistant.",
            tools=[tool_param],  # type: ignore[arg-type]
        )

        request = openai_prompt.as_platform_request(model="gpt-4o")

        assert isinstance(request, dict)
        assert request["model"] == "gpt-4o"
        assert len(request["input"]) == 1
        assert request["instructions"] == "You are a helpful assistant."
        assert "tools" in request
        assert len(request["tools"]) == 1
        assert request["tools"][0]["name"] == "test-tool"

    def test_as_platform_request_with_reasoning_models(self) -> None:
        """Test converting to platform request with reasoning set."""
        from openai.types.shared_params import Reasoning

        openai_prompt = OpenAIPrompt(
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello, world!"}],
                }
            ],
            reasoning=Reasoning(effort="medium"),
        )

        request = openai_prompt.as_platform_request(model="gpt-4.1")

        # gpt-4-1 does not support reasoning
        assert "reasoning" in request
        assert request["reasoning"] is None

        openai_prompt = OpenAIPrompt(
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello, world!"}],
                }
            ],
            reasoning=Reasoning(effort="high"),
        )
        request = openai_prompt.as_platform_request(model="gpt-5")

        assert "reasoning" in request
        assert request["reasoning"]["effort"] == "high"

    def test_prompt_properties(self) -> None:
        """Test prompt properties and defaults."""

        # Test with defaults
        prompt = OpenAIPrompt(
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello"}],
                }
            ]
        )
        assert isinstance(prompt.input, list)
        assert prompt.temperature == 0.0
        assert prompt.top_p == 1.0
        assert prompt.max_output_tokens is None
        assert prompt.tools is None

        # Test with custom values
        tools: list = [  # type: ignore[assignment]
            {
                "type": "function",
                "name": "test",
                "description": "Test tool",
                "parameters": {},
                "strict": True,
            }
        ]
        prompt = OpenAIPrompt(
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello"}],
                }
            ],
            tools=tools,  # type: ignore[arg-type]
            temperature=0.7,
            top_p=0.9,
            max_output_tokens=1000,
        )
        assert isinstance(prompt.input, list)
        assert prompt.tools == tools
        assert prompt.temperature == 0.7
        assert prompt.top_p == 0.9
        assert prompt.max_output_tokens == 1000
