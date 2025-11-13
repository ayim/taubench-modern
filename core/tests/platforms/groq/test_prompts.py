"""Unit tests for the Groq prompts."""

from typing import TYPE_CHECKING, Any, cast

import pytest

if TYPE_CHECKING:
    from openai.types.responses import ToolParam

from agent_platform.core.platforms.groq.prompts import GroqPrompt


class TestGroqPrompt:
    """Tests for the Groq prompt behaviour."""

    @pytest.fixture
    def groq_prompt(self) -> GroqPrompt:
        return GroqPrompt(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Hello, Groq!",
                        }
                    ],
                },
            ],
            instructions="You are helpful.",
            temperature=0.1,
            top_p=0.9,
        )

    def test_as_platform_request(self, groq_prompt: GroqPrompt) -> None:
        request = groq_prompt.as_platform_request("groq/openai/gpt-oss-20b")
        assert request["model"] == "groq/openai/gpt-oss-20b"
        assert request["input"] == groq_prompt.input
        assert "include" not in request
        assert "store" not in request

    def test_as_platform_request_with_stream(self, groq_prompt: GroqPrompt) -> None:
        request = groq_prompt.as_platform_request("groq/openai/gpt-oss-20b", stream=True)
        assert request["stream"] is True

    def test_as_platform_request_with_tools(self, groq_prompt: GroqPrompt) -> None:
        tools = cast(
            "list[ToolParam]",
            [
                {
                    "type": "function",
                    "function": {
                        "name": "test",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )

        prompt = GroqPrompt(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Hello, Groq!",
                        }
                    ],
                }
            ],
            instructions="You are helpful.",
            temperature=0.1,
            top_p=0.9,
            tools=tools,
        )

        request = prompt.as_platform_request("groq/openai/gpt-oss-20b")

        # basic shape checks without over-constraining the model mapping
        assert "tools" in request
        assert isinstance(request["tools"], list)
        first_tool = request["tools"][0]
        # handle both dict- and object-returns defensively
        tool_type = (
            first_tool.get("type")
            if isinstance(first_tool, dict)
            else getattr(first_tool, "type", None)
        )
        func = (
            first_tool.get("function")
            if isinstance(first_tool, dict)
            else getattr(first_tool, "function", None)
        )
        func_name = func.get("name") if isinstance(func, dict) else getattr(func, "name", None)

        assert tool_type == "function"
        assert func_name == "test"

    def test_prompt_defaults(self) -> None:
        prompt = GroqPrompt()
        assert prompt.temperature == 0.0
        assert prompt.top_p == 1.0
        assert prompt.include == ["reasoning.encrypted_content"]

    def test_prompt_custom_reasoning(self) -> None:
        prompt = GroqPrompt(reasoning={"effort": "low", "summary": "concise"})
        request = prompt.as_platform_request("groq/openai/gpt-oss-20b")
        assert "reasoning" not in request  # non-reasoning model strips reasoning include

    def test_prompt_accepts_additional_fields(self) -> None:
        prompt = GroqPrompt(max_output_tokens=256, tool_choice="required")
        request = prompt.as_platform_request("groq/openai/gpt-oss-20b")
        assert request["max_output_tokens"] == 256
        assert request["tool_choice"] == "required"

    def test_prompt_round_trip(self) -> None:
        prompt = GroqPrompt()
        data: dict[str, Any] = prompt.as_platform_request("groq/openai/gpt-oss-20b")
        assert data["model"] == "groq/openai/gpt-oss-20b"

    def test_prompt_preserves_provider_prefix(self) -> None:
        prompt = GroqPrompt()
        request = prompt.as_platform_request("meta-llama/llama-4-scout-17b-16e-instruct")
        assert request["model"] == "meta-llama/llama-4-scout-17b-16e-instruct"
