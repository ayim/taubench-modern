import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.messages import (
    AnyPromptMessage,
    PromptUserMessage,
)
from agent_platform.core.thread.base import ThreadMessage

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)

TRUNCATED_TOOL_OUTPUT_MARKER = "[TRUNCATED TOOL OUTPUT]"


@dataclass(frozen=True)
class ConversationCompressionConfig:
    max_tool_output_chars: int = 4000
    tool_output_head_ratio: float = 0.7
    tool_output_min_tail_chars: int = 400


DEFAULT_COMPRESSION_CONFIG = ConversationCompressionConfig()


async def format_thread_conversation_for_eval(
    kernel: "Kernel",
    messages: list[ThreadMessage],
    include: list[str] | None = None,
    compression_config: ConversationCompressionConfig = DEFAULT_COMPRESSION_CONFIG,
) -> str:
    converted_messages: list[Any] = await kernel.converters.thread_messages_to_prompt_messages(
        messages
    )
    if compression_config.max_tool_output_chars > 0:
        _compress_prompt_messages(converted_messages, compression_config)
    prompt = Prompt(
        messages=converted_messages,
    )
    return prompt.to_pretty_yaml(include=include or ["messages"])


def _compress_prompt_messages(
    messages: list[AnyPromptMessage],
    compression_config: ConversationCompressionConfig,
) -> None:
    for message in messages:
        if not isinstance(message, PromptUserMessage):
            continue
        for content in message.content:
            if isinstance(content, PromptToolResultContent):
                _compress_tool_result_content(content, compression_config)


def _compress_tool_result_content(
    content: PromptToolResultContent,
    compression_config: ConversationCompressionConfig,
) -> None:
    for text_content in content.content:
        if not isinstance(text_content, PromptTextContent):
            continue
        truncated_text = _truncate_tool_output_text(text_content.text, compression_config)
        if truncated_text == text_content.text:
            continue
        logger.debug(
            "Truncated tool output for %s (%s) from %s chars to %s chars",
            content.tool_name,
            content.tool_call_id,
            len(text_content.text),
            len(truncated_text),
        )
        text_content.text = truncated_text


def _truncate_tool_output_text(
    text: str,
    compression_config: ConversationCompressionConfig,
) -> str:
    limit = compression_config.max_tool_output_chars
    if limit <= 0:
        return text

    text_len = len(text)
    if text_len <= limit:
        return text

    if TRUNCATED_TOOL_OUTPUT_MARKER in text:
        return text

    head_len = max(1, min(int(limit * compression_config.tool_output_head_ratio), limit - 1))
    tail_len = limit - head_len

    if tail_len < compression_config.tool_output_min_tail_chars and limit > 1:
        tail_len = min(compression_config.tool_output_min_tail_chars, limit - 1)
        head_len = limit - tail_len

    omitted_chars = max(text_len - (head_len + tail_len), 0)
    if omitted_chars <= 0:
        return text

    notice = (
        f"\n... {TRUNCATED_TOOL_OUTPUT_MARKER}: omitted {omitted_chars} chars "
        "to fit evaluation context ...\n"
    )
    return f"{text[:head_len]}{notice}{text[-tail_len:]}"
