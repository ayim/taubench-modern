from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from structlog import get_logger

from agent_platform.core.prompts.messages import AnyPromptMessage
from agent_platform.core.prompts.special.base import SpecialPromptMessage

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel

logger = get_logger()


@dataclass
class ConversationHistoryParams:
    """Parameters for the conversation history special message."""

    maximum_number_of_turns: int = field(
        default=20,
        metadata={
            "description": ("The maximum number of turns to include in the conversation history."),
        },
    )
    """The maximum number of turns to include in the conversation history."""

    token_budget_as_percentage: float = field(
        default=0.50,
        metadata={
            "description": ("The token budget as a percentage of the total token budget."),
        },
    )
    """The token budget as a percentage of the total token budget."""

    @classmethod
    def model_validate(cls, data: dict) -> "ConversationHistoryParams":
        """Validate and convert a dictionary into a
        ConversationHistoryParams instance."""
        data = data.copy()
        return cls(**data)


@dataclass
class ConversationHistorySpecialMessage(SpecialPromptMessage):
    """Special message for including the conversation history in a prompt."""

    params: ConversationHistoryParams = field(
        default_factory=ConversationHistoryParams,
    )
    """The parameters for the conversation history special message."""

    async def hydrate(
        self,
        kernel: "Kernel",
    ) -> list[AnyPromptMessage]:
        """Hydrate the conversation history special message."""
        # Look in the agents settings for how much context to keep
        number_of_turns_to_keep = kernel.agent.extra.get("agent_settings", {}).get(
            "conversation_turns_kept_in_context", None
        )
        if number_of_turns_to_keep and not isinstance(number_of_turns_to_keep, int):
            number_of_turns_to_keep = int(number_of_turns_to_keep)

        # Log a bit about context (debug)
        if number_of_turns_to_keep:
            logger.debug(f"Will keep {number_of_turns_to_keep} turns of context (agent settings)")
        else:
            logger.debug(
                f"Will keep {self.params.maximum_number_of_turns} default number of "
                "turns of context (params)"
            )

        # Get the last N message turns
        historical_messages = kernel.thread.get_last_n_message_turns(
            # Take either the agents settings (has precedence) or whatever
            # was set on the params of this block (likely just the default)
            n=number_of_turns_to_keep or self.params.maximum_number_of_turns,
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


@dataclass
class ConversationHistoryMinusLatestUserSpecialMessage(ConversationHistorySpecialMessage):
    """Special message for conversation history excluding the latest user message.

    This keeps the same turn-based slicing as the standard conversation history,
    but drops the most recent user message so it can be injected separately.
    """

    async def hydrate(
        self,
        kernel: "Kernel",
    ) -> list[AnyPromptMessage]:
        """Hydrate conversation history without the latest user message."""
        number_of_turns_to_keep = kernel.agent.extra.get("agent_settings", {}).get(
            "conversation_turns_kept_in_context", None
        )
        if number_of_turns_to_keep and not isinstance(number_of_turns_to_keep, int):
            number_of_turns_to_keep = int(number_of_turns_to_keep)

        historical_messages = kernel.thread.get_last_n_message_turns(
            number_of_turns_to_keep or self.params.maximum_number_of_turns
        )

        # Remove the latest user message (if present) to avoid duplication.
        for idx in range(len(historical_messages) - 1, -1, -1):
            if historical_messages[idx].role == "user":
                del historical_messages[idx]
                break

        if not historical_messages:
            return []

        converted_messages = await kernel.converters.thread_messages_to_prompt_messages(
            historical_messages,
        )
        return converted_messages

    @classmethod
    def model_validate(cls, data: dict) -> "ConversationHistoryMinusLatestUserSpecialMessage":
        """Validate and convert a dictionary into a conversation-history special message."""
        data = data.copy()
        params = ConversationHistoryParams.model_validate(data.pop("params", {}))
        return cls(params=params, **data)


ConversationHistoryMinusLatestUserSpecialMessage.register_message_by_role(
    "$conversation-history-minus-latest-user-message",
    ConversationHistoryMinusLatestUserSpecialMessage,
)


@dataclass
class LatestUserMessageSpecialMessage(SpecialPromptMessage):
    """Special message that injects only the latest user message."""

    async def hydrate(
        self,
        kernel: "Kernel",
    ) -> list[AnyPromptMessage]:
        """Hydrate with the most recent user message only."""
        latest_user_msg = next(
            (msg for msg in reversed(kernel.thread.messages) if msg.role == "user"),
            None,
        )
        if latest_user_msg is None:
            return []

        converted = await kernel.converters.thread_messages_to_prompt_messages([latest_user_msg])
        return converted

    @classmethod
    def model_validate(cls, data: dict) -> "LatestUserMessageSpecialMessage":
        """Validate and convert a dictionary into a LatestUserMessageSpecialMessage."""
        data = data.copy()
        return cls(**data)


LatestUserMessageSpecialMessage.register_message_by_role(
    "$latest-user-message",
    LatestUserMessageSpecialMessage,
)
