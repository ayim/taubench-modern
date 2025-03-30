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
    PromptMessage,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt

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
)

AgentPromptMessageContent = PromptTextContent | PromptToolUseContent

__all__ = [
    "AnyPromptMessageContent",
    "AgentPromptMessageContent",
    "UserPromptMessageContent",
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
]
