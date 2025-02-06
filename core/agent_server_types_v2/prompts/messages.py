from dataclasses import dataclass, field
from typing import Literal

from agent_server_types_v2.prompts.base import PromptMessage
from agent_server_types_v2.prompts.content.audio import PromptAudioContent
from agent_server_types_v2.prompts.content.image import PromptImageContent
from agent_server_types_v2.prompts.content.text import PromptTextContent
from agent_server_types_v2.prompts.content.tool_result import PromptToolResultContent
from agent_server_types_v2.prompts.content.tool_use import PromptToolUseContent


@dataclass(frozen=True)
class PromptUserMessage(PromptMessage):
    """Represents a user message in the prompt."""

    content: list[
        PromptTextContent | PromptImageContent | PromptAudioContent | PromptToolResultContent
    ] = field(metadata={"description": "The contents of the prompt message"})
    """The contents of the prompt message"""

    role: Literal["user"] = field(default="user", metadata={"description": "The role of the message sender"})
    """The role of the message sender"""


@dataclass(frozen=True)
class PromptAgentMessage(PromptMessage):
    """Represents an agent message in the prompt."""

    content: list[PromptTextContent | PromptToolUseContent] = field(
        metadata={"description": "The contents of the prompt message"},
    )
    """The contents of the prompt message"""

    role: Literal["agent"] = field(default="agent", metadata={"description": "The role of the message sender"})
    """The role of the message sender"""