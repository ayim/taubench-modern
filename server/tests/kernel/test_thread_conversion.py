import importlib
from collections.abc import Callable
from importlib.metadata import entry_points

import pytest

from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.core.thread.messages import ThreadAgentMessage


def _conversion_functions() -> list[Callable]:
    """Resolve thread conversion functions exposed by agent architectures."""

    conversions: list[Callable] = []
    eps = entry_points().select(group="agent_platform.architectures")

    for ep in eps:
        try:
            entry_func = ep.load()
        except Exception as load_error:  # pragma: no cover - defensive guard
            raise RuntimeError(f"Failed to load architecture entry point {ep.name}") from load_error

        module = importlib.import_module(entry_func.__module__)
        conversion = getattr(module, "thread_messages_to_prompt_messages", None)
        if conversion and conversion not in conversions:
            conversions.append(conversion)

    return conversions


class _DummyFiles:
    async def get_file_by_id(self, file_id: str):  # pragma: no cover - interface stub
        return None


class _DummyThreadState:
    def __init__(self) -> None:
        self.active_message_content: list = []


class _DummyKernel:
    def __init__(self) -> None:
        self.files = _DummyFiles()
        self.thread_state = _DummyThreadState()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conversion_func",
    _conversion_functions(),
    ids=lambda func: func.__module__,
)
async def test_thread_conversion_preserves_tool_error_in_prompt(conversion_func: Callable) -> None:
    tool_usage = ThreadToolUsageContent(
        name="fail_tool",
        tool_call_id="call-123",
        arguments_raw="{}",
        status="failed",
        # No result, but an error
        result=None,
        error="ReadTimeout",
    )

    agent_message = ThreadAgentMessage(content=[tool_usage])
    kernel = _DummyKernel()

    prompt_messages = await conversion_func(kernel, [agent_message])

    tool_result_contents = [
        content
        for message in prompt_messages
        if isinstance(message, PromptUserMessage)
        for content in message.content
        if isinstance(content, PromptToolResultContent)
    ]

    assert tool_result_contents, "Expected at least one tool result converted to prompt"

    prompt_tool_result = tool_result_contents[0]
    assert prompt_tool_result.is_error is True

    text_contents = [
        item for item in prompt_tool_result.content if isinstance(item, PromptTextContent)
    ]
    assert text_contents, "Tool result should include textual content"
    # Error surfaces in the prompt we build
    assert "ReadTimeout" in text_contents[0].text
