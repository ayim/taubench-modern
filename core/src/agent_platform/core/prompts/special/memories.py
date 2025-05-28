from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptUserMessage,
)
from agent_platform.core.prompts.special.base import SpecialPromptMessage

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel


@dataclass(frozen=True)
class MemoriesParams:
    """Parameters for the memories special message."""

    maximum_number_of_memories: int = field(
        default=20,
        metadata={
            "description": ("The maximum number of memories to include in the prompt."),
        },
    )
    """The maximum number of memories to include in the prompt."""

    token_budget_as_percentage: float = field(
        default=0.50,
        metadata={
            "description": ("The token budget as a percentage of the total token budget."),
        },
    )
    """The token budget as a percentage of the total token budget."""

    @classmethod
    def model_validate(cls, data: dict) -> "MemoriesParams":
        """Validate and convert a dictionary into a
        MemoriesParams instance."""
        data = data.copy()
        return cls(**data)


@dataclass(frozen=True)
class MemoriesSpecialMessage(SpecialPromptMessage):
    """Special message for including the memories in a prompt."""

    params: MemoriesParams = field(
        default_factory=MemoriesParams,
    )
    """The parameters for the memories special message."""

    async def hydrate(
        self,
        kernel: "Kernel",
    ) -> list[PromptUserMessage | PromptAgentMessage]:
        """Hydrate the memories special message."""
        # TODO: handle memories
        return []

    @classmethod
    def model_validate(cls, data: dict) -> "MemoriesSpecialMessage":
        """Validate and convert a dictionary into a
        MemoriesSpecialMessage instance."""
        data = data.copy()
        params = MemoriesParams.model_validate(data.pop("params", {}))
        return cls(params=params, **data)


MemoriesSpecialMessage.register_message_by_role(
    "$memories",
    MemoriesSpecialMessage,
)
