"""Unit tests for the Groq converters."""

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.groq.converters import GroqConverters
from agent_platform.core.platforms.groq.prompts import GroqPrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptTextContent,
    PromptToolUseContent,
    PromptUserMessage,
)


class TestGroqConverters:
    """Tests for Groq converter behaviour."""

    @pytest.fixture
    def converters(self) -> GroqConverters:
        return GroqConverters()

    @pytest.fixture
    def kernel(self) -> Kernel:
        from unittest.mock import MagicMock

        return MagicMock(spec=Kernel)

    @pytest.mark.asyncio
    async def test_convert_text_content(self, converters: GroqConverters) -> None:
        content = PromptTextContent(text="Hello, Groq!")
        result = await converters.convert_text_content(content)
        assert result["type"] == "input_text"
        assert result["text"] == "Hello, Groq!"

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(self, converters: GroqConverters) -> None:
        content = PromptToolUseContent(
            tool_call_id="call-1",
            tool_name="test",  # type: ignore[arg-type]
            tool_input_raw="{}",
        )
        result = await converters.convert_tool_use_content(content)
        assert result["call_id"] == "call-1"
        assert result["name"] == "test"

    @pytest.mark.asyncio
    async def test_convert_prompt(self, converters: GroqConverters, kernel: Kernel) -> None:
        prompt = Prompt(
            system_instruction="You are helpful.",
            messages=[PromptUserMessage([PromptTextContent(text="Hi")])],
        )
        finalized_prompt = await prompt.finalize_messages(kernel)
        groq_prompt = await converters.convert_prompt(finalized_prompt, model_id="openai/gpt-oss-20b")

        assert isinstance(groq_prompt, GroqPrompt)
        request = groq_prompt.as_platform_request("openai/gpt-oss-20b")
        assert request["model"] == "openai/gpt-oss-20b"
        assert request["input"], "Converted prompt should include input messages"
        assert "include" not in request
        assert "store" not in request
