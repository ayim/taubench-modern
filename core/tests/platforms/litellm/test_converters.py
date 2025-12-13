"""Tests for LiteLLM converters."""

from typing import TYPE_CHECKING, TypeGuard, cast

import pytest

from agent_platform.core.platforms.litellm.converters import LiteLLMConverters
from agent_platform.core.prompts import PromptAgentMessage, PromptTextContent, PromptUserMessage
from agent_platform.core.prompts.content.reasoning import PromptReasoningContent
from agent_platform.core.prompts.prompt import Prompt

if TYPE_CHECKING:
    from openai.types.responses import ResponseInputItemParam
    from openai.types.responses.response_reasoning_item_param import ResponseReasoningItemParam


def _is_reasoning_item(item: "ResponseInputItemParam") -> TypeGuard["ResponseReasoningItemParam"]:
    """Type guard for narrowing reasoning items emitted by the converter."""
    return isinstance(item, dict) and "type" in item and item["type"] == "reasoning"


@pytest.mark.asyncio
async def test_convert_prompt_drops_reasoning_before_last_user_message() -> None:
    """LiteLLM conversion should strip reasoning items that precede the final user turn."""
    prompt = Prompt(
        messages=[
            PromptUserMessage(content=[PromptTextContent(text="first user")]),
            PromptAgentMessage(
                content=[
                    PromptReasoningContent(
                        reasoning="early reasoning",
                        summary=["early summary"],
                        content=["early content"],
                        encrypted_content=None,
                    )
                ]
            ),
            PromptUserMessage(content=[PromptTextContent(text="final user")]),
            PromptAgentMessage(
                content=[
                    PromptReasoningContent(
                        reasoning="kept reasoning",
                        summary=["kept summary"],
                        content=["kept content"],
                        encrypted_content=None,
                    )
                ]
            ),
        ]
    )
    # Skip default finalizers to avoid kernel dependencies for this unit test.
    await prompt.finalize_messages(prompt_finalizers=[], finalizer_kwargs={})

    converters = LiteLLMConverters()
    converted = await converters.convert_prompt(prompt, model_id="gpt-4o")

    from openai.types.responses.response_reasoning_item_param import (
        ResponseReasoningItemParam,
    )

    reasoning_items = [cast(ResponseReasoningItemParam, item) for item in converted.input if _is_reasoning_item(item)]
    assert len(reasoning_items) == 1

    kept_reasoning = reasoning_items[0]
    assert "summary" in kept_reasoning
    assert "content" in kept_reasoning
    kept_summary = next(iter(kept_reasoning["summary"]))
    kept_content = next(iter(kept_reasoning["content"]))
    assert kept_summary["text"] == "kept summary"
    assert kept_content["text"] == "kept content"
    assert "early" not in str(converted.input)
