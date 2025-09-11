from abc import ABC
from dataclasses import dataclass
from typing import ClassVar, Literal

from agent_platform.core.prompts.content.base import PromptMessageContent


@dataclass
class PromptMessage(ABC):
    """Base class for all messages in a prompt."""

    _message_by_role: ClassVar[dict[Literal["user", "agent"], type["PromptMessage"]]] = {}

    content: list[PromptMessageContent]
    """The contents of the message."""

    role: Literal["user", "agent"]
    """The role of the message sender."""

    include_expr: str | None = None
    """The Jinja2 expression to determine if the message should be included in the prompt."""

    include: bool = True
    """Whether the message should be included in the prompt.
    (Will be overridden by rendered value of include_expr if provided.)"""

    def count_tokens_approx(self) -> int:
        """Counts the approximate number of tokens in the message.

        This method sums the token counts of all content items in the message.
        """
        return sum(item.count_tokens_approx() for item in self.content)

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
        role = data.get("role")
        if role is None:
            raise ValueError("Message role is required")
        if role in cls._message_by_role:
            return cls._message_by_role[role].model_validate(data)
        else:
            raise ValueError(f"Unknown message role: {data.get('role')}")
