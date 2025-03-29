from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal

from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptUserMessage,
)

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel


@dataclass(frozen=True)
class SpecialPromptMessage(ABC):
    """Base class for special messages in a prompt.

    Special messages are messages that are "abstract" in the sense that
    they will eventually be _translated_ to "normal/converte" PromptMessages
    with the help of data provided by the kernel.

    Mostly, special messages are an affordance used for writing prompt
    templates for our agents, allowing us to capture concepts without
    putting a large burden on agent architectures to re-implement code
    for familiar patterns like "include the last N messages from the
    conversation history" or "get relevant memories from the agent's
    memory store".
    """

    _special_message_by_role: ClassVar[
        dict[
            Literal[
                "$conversation-history",
                "$documents",
                "$memories",
            ],
            type["SpecialPromptMessage"],
        ]
    ] = {}

    role: Literal[
        "$conversation-history",
        "$documents",
        "$memories",
    ]
    """The role of the message sender. Special messages are always
    prefixed with a `$` to make them easy to spot in a prompt."""

    @classmethod
    def register_message_by_role(
        cls,
        role: Literal["$conversation-history", "$documents", "$memories"],
        message_class: type["SpecialPromptMessage"],
    ) -> None:
        """Register a special message by its role with its corresponding class.

        Args:
            role: The role of the special message
            message_class: The class that handles this special message
        """
        cls._special_message_by_role[role] = message_class

    @classmethod
    def model_validate(cls, data: dict) -> "SpecialPromptMessage":
        """Validate and convert a dictionary into a SpecialPromptMessage instance."""
        if data.get("role") in cls._special_message_by_role:
            return cls._special_message_by_role[data.get("role")].model_validate(data)
        else:
            raise ValueError(f"Unknown special message role: {data.get('role')}")

    @abstractmethod
    async def hydrate(
        self,
        kernel: "Kernel",
    ) -> list[PromptUserMessage | PromptAgentMessage]:
        """Hydrate the special message."""
        pass
