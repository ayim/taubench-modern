from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.prompts.base import PromptMessage
from agent_platform.core.prompts.content.audio import PromptAudioContent
from agent_platform.core.prompts.content.base import PromptMessageContent
from agent_platform.core.prompts.content.image import PromptImageContent
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.content.tool_use import PromptToolUseContent


@dataclass(frozen=True)
class PromptUserMessage(PromptMessage):
    """Represents a user message in the prompt."""

    content: list[  # type: ignore
        PromptTextContent | PromptImageContent | PromptAudioContent
        | PromptToolResultContent
    ] = field(metadata={"description": "The contents of the prompt message"})
    # Type ignore here as we have a refinement on the kinds of content
    # that can be in the list for a PromptUserMessage
    """The contents of the prompt message"""

    role: Literal["user"] = field(
        default="user",
        metadata={"description": "The role of the message sender"},
    )
    """The role of the message sender"""

    @classmethod
    def model_validate(cls, data: dict) -> "PromptUserMessage":
        """Validate and convert a dictionary into a PromptUserMessage instance."""
        data = data.copy()
        raw_content = data.pop("content", [])
        content = []
        for item in raw_content:
            content.append(PromptMessageContent.model_validate(item))
        data["content"] = content
        return cls(**data)

@dataclass(frozen=True)
class PromptAgentMessage(PromptMessage):
    """Represents an agent message in the prompt."""

    content: list[PromptTextContent | PromptToolUseContent] = field(  # type: ignore
        metadata={"description": "The contents of the prompt message"},
    )
    # Type ignore here as we have a refinement on the kinds of content
    # that can be in the list for a PromptAgentMessage
    """The contents of the prompt message"""

    role: Literal["agent"] = field(
        default="agent",
        metadata={"description": "The role of the message sender"},
    )
    """The role of the message sender"""

    @classmethod
    def model_validate(cls, data: dict) -> "PromptAgentMessage":
        """Validate and convert a dictionary into a PromptAgentMessage instance."""
        data = data.copy()
        raw_content = data.pop("content", [])
        content = []
        for item in raw_content:
            content.append(PromptMessageContent.model_validate(item))
        data["content"] = content
        return cls(**data)


AnyPromptMessage = PromptUserMessage | PromptAgentMessage

PromptMessage.register_message_by_role("user", PromptUserMessage)
PromptMessage.register_message_by_role("agent", PromptAgentMessage)
