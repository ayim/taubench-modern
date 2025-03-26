from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agent_platform_core.prompts.messages import (
    PromptAgentMessage,
    PromptUserMessage,
)
from agent_platform_core.prompts.special.base import SpecialPromptMessage

if TYPE_CHECKING:
    from agent_platform_core.kernel import Kernel


@dataclass(frozen=True)
class ConversationHistoryParams:
    """Parameters for the conversation history special message."""

    maximum_number_of_turns: int = field(
        default=5,
        metadata={
            "description": (
                "The maximum number of turns to include in the conversation history."
            ),
        },
    )
    """The maximum number of turns to include in the conversation history."""

    token_budget_as_percentage: float = field(
        default=0.50,
        metadata={
            "description": (
                "The token budget as a percentage of the total token budget."
            ),
        },
    )
    """The token budget as a percentage of the total token budget."""

    @classmethod
    def model_validate(cls, data: dict) -> "ConversationHistoryParams":
        """Validate and convert a dictionary into a
        ConversationHistoryParams instance."""
        data = data.copy()
        return cls(**data)


@dataclass(frozen=True)
class ConversationHistorySpecialMessage(SpecialPromptMessage):
    """Special message for including the conversation history in a prompt."""

    params: ConversationHistoryParams = field(
        default_factory=ConversationHistoryParams,
    )
    """The parameters for the conversation history special message."""

    async def hydrate(
        self,
        kernel: "Kernel",
    ) -> list[PromptUserMessage | PromptAgentMessage]:
        """Hydrate the conversation history special message."""
        # Get the last N message turns
        historical_messages = kernel.thread.get_last_n_message_turns(
            n=self.params.maximum_number_of_turns,
        )

        # Convert the historical messages to prompt messages
        converted_messages = await kernel.converters.thread_messages_to_prompt_messages(
            historical_messages,
        )

        # Return the hydrated messages
        return converted_messages

    @classmethod
    def model_validate(cls, data: dict) -> "ConversationHistorySpecialMessage":
        """Validate and convert a dictionary into a
        ConversationHistorySpecialMessage instance."""
        data = data.copy()
        params = ConversationHistoryParams.model_validate(data.pop("params", {}))
        return cls(params=params, **data)


ConversationHistorySpecialMessage.register_message_by_role(
    "$conversation-history",
    ConversationHistorySpecialMessage,
)
