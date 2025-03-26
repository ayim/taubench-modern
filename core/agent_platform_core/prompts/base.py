from abc import ABC
from dataclasses import dataclass
from typing import ClassVar, Literal

from agent_server_types_v2.prompts.content.base import PromptMessageContent


@dataclass(frozen=True)
class PromptMessage(ABC):
    """Base class for all messages in a prompt."""

    _message_by_role: ClassVar[
        dict[Literal["user", "agent"], type["PromptMessage"]]
    ] = {}

    content: list[PromptMessageContent]
    """The contents of the message."""

    role: Literal["user", "agent"]
    """The role of the message sender."""

    @classmethod
    def register_message_by_role(
        cls,
        role: Literal["user", "agent"],
        message_class: type["PromptMessage"],
    ) -> None:
        """Register a message by its role with its corresponding class.

        Args:
            role: The role of the message
            message_class: The class that handles this message
        """
        cls._message_by_role[role] = message_class

    @classmethod
    def model_validate(cls, data: dict) -> "PromptMessage":
        """Validate and convert a dictionary into a PromptMessage instance."""
        if data.get("role") in cls._message_by_role:
            return cls._message_by_role[data.get("role")].model_validate(data)
        else:
            raise ValueError(f"Unknown message role: {data.get('role')}")
