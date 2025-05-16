"""Prompt-related types and utilities."""

from agent_platform.core.prompts.content import (
    PromptAudioContent,
    PromptImageContent,
    PromptMessageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)
from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptDocumentContent,
    PromptMessage,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.prompts.selector import select_prompt
from agent_platform.core.prompts.special import (
    ConversationHistorySpecialMessage,
    DocumentsSpecialMessage,
    MemoriesSpecialMessage,
)
from agent_platform.core.prompts.utils import (
    count_role_indicator_tokens,
    count_tokens_approx,
    count_tools_tokens,
    format_tool_use_for_token_counting,
)

AnyPromptMessage = (
    PromptUserMessage
    | PromptAgentMessage
    | ConversationHistorySpecialMessage
    | DocumentsSpecialMessage
    | MemoriesSpecialMessage
)

AnyPromptMessageContent = (
    PromptAudioContent
    | PromptImageContent
    | PromptTextContent
    | PromptToolResultContent
    | PromptToolUseContent
)

UserPromptMessageContent = (
    PromptTextContent
    | PromptImageContent
    | PromptAudioContent
    | PromptToolResultContent
    | PromptDocumentContent
)

AgentPromptMessageContent = PromptTextContent | PromptToolUseContent

__all__ = [
    "AgentPromptMessageContent",
    "AnyPromptMessageContent",
    "Prompt",
    "PromptAgentMessage",
    "PromptAudioContent",
    "PromptImageContent",
    "PromptMessage",
    "PromptMessageContent",
    "PromptTextContent",
    "PromptToolResultContent",
    "PromptToolUseContent",
    "PromptUserMessage",
    "UserPromptMessageContent",
    "count_role_indicator_tokens",
    "count_tokens_approx",
    "count_tools_tokens",
    "format_tool_use_for_token_counting",
    "select_prompt",
]
