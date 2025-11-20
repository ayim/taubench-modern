from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.messages import PromptAgentMessage, PromptUserMessage
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.server.evals.conversation_formatting import (
    TRUNCATED_TOOL_OUTPUT_MARKER,
    ConversationCompressionConfig,
    format_thread_conversation_for_eval,
)

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel


def _make_kernel(
    converted_messages: list[PromptUserMessage | PromptAgentMessage],
) -> "Kernel":
    async def _convert(
        _messages: list[ThreadMessage],
    ) -> list[PromptUserMessage | PromptAgentMessage]:
        return converted_messages

    fake_kernel = SimpleNamespace(
        converters=SimpleNamespace(
            thread_messages_to_prompt_messages=_convert,
        ),
    )
    return cast("Kernel", fake_kernel)


def _make_thread_messages() -> list[ThreadMessage]:
    return [
        ThreadMessage(
            role="user",
            content=[ThreadTextContent(text="User: describe your results.")],
        )
    ]


@pytest.mark.asyncio
async def test_format_thread_conversation_truncates_long_tool_outputs() -> None:
    long_text = "BEGIN\n" + ("x" * 500) + "\nEND"
    tool_content = PromptToolResultContent(
        tool_name="search",
        tool_call_id="tool-1",
        content=[
            PromptTextContent(text=long_text),
        ],
    )
    converted_messages: list[Any] = [
        PromptUserMessage(
            content=[tool_content],
        ),
    ]
    kernel = _make_kernel(converted_messages)

    yaml_output = await format_thread_conversation_for_eval(
        kernel=kernel,
        messages=_make_thread_messages(),
        compression_config=ConversationCompressionConfig(
            max_tool_output_chars=100,
            tool_output_head_ratio=0.5,
            tool_output_min_tail_chars=20,
        ),
    )

    content = tool_content.content[0]
    if isinstance(content, PromptTextContent):
        truncated_text = content.text
        assert len(truncated_text) < len(long_text)
        assert TRUNCATED_TOOL_OUTPUT_MARKER in truncated_text
        assert long_text[:8] in truncated_text
        assert long_text[-4:] in truncated_text
        assert TRUNCATED_TOOL_OUTPUT_MARKER in yaml_output


@pytest.mark.asyncio
async def test_format_thread_conversation_leaves_regular_text_untouched() -> None:
    user_text = "User said: " + ("details " * 20)
    agent_text = "Agent summary explaining results."
    converted_messages = [
        PromptUserMessage(
            content=[PromptTextContent(text=user_text)],
        ),
        PromptAgentMessage(
            content=[PromptTextContent(text=agent_text)],
        ),
    ]
    kernel = _make_kernel(converted_messages)

    yaml_output = await format_thread_conversation_for_eval(
        kernel=kernel,
        messages=_make_thread_messages(),
    )

    assert TRUNCATED_TOOL_OUTPUT_MARKER not in yaml_output
    assert converted_messages[0].content[0].text == user_text
    assert converted_messages[1].content[0].text == agent_text
