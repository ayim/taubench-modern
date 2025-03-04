from abc import ABC
from dataclasses import dataclass
from typing import Literal

from agent_server_types_v2.prompts.content.base import PromptMessageContent


@dataclass(frozen=True)
class PromptMessage(ABC):
    """Base class for all messages."""

    content: list[PromptMessageContent]
    """The contents of the message."""

    role: Literal["user", "agent"]
    """The role of the message sender."""
