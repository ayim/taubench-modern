from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.prompts import (
        ConversationHistorySpecialMessage,
        DocumentsSpecialMessage,
        MemoriesSpecialMessage,
        Prompt,
        PromptAgentMessage,
        PromptUserMessage,
    )

    PromptMessageType = PromptUserMessage | PromptAgentMessage
    SpecialMessageType = ConversationHistorySpecialMessage | DocumentsSpecialMessage | MemoriesSpecialMessage
    MessageType = PromptMessageType | SpecialMessageType


class BaseFinalizer(ABC):
    """Base class for prompt finalizers.

    Prompt finalizers are responsible for modifying the list of messages
    in a prompt before it is sent to the model. This can include
    truncation, filtering, or other transformations.
    """

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    @abstractmethod
    async def __call__(
        self,
        messages: list["MessageType"],
        prompt: "Prompt",
        kernel: "Kernel | None" = None,
        **kwargs,
    ) -> list["MessageType"]:
        """Finalize the messages in a prompt.

        Args:
            messages: The list of messages to finalize.
            prompt: The prompt instance being finalized.
            kernel: The kernel instance, if available.
            **kwargs: Additional keyword arguments.

        Returns:
            The finalized list of messages.
        """
