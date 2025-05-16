from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from agent_platform.core.prompts.finalizers.base import BaseFinalizer
from agent_platform.core.prompts.special.base import SpecialPromptMessage

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.prompts import Prompt
    from agent_platform.core.prompts.finalizers.base import MessageType

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SpecialMessageFinalizer(BaseFinalizer):
    """
    Finalizer that hydrates special messages in a prompt.

    This finalizer is responsible for replacing special messages like
    ConversationHistorySpecialMessage with their hydrated counterparts.
    It should typically be the first finalizer in a chain.

    Usage:
    ```python
    special_message_finalizer = SpecialMessageFinalizer()
    # Use it as the first finalizer in a chain
    finalized_prompt = await prompt.finalize_messages(
        kernel=kernel,
        prompt_finalizers=[special_message_finalizer, truncation_finalizer],
    )
    ```
    """

    async def __call__(
        self,
        messages: list["MessageType"],
        prompt: "Prompt",
        kernel: "Kernel | None" = None,
        **kwargs,
    ) -> list["MessageType"]:
        """
        Hydrate any special messages in the message list.

        Args:
            messages: The list of messages to finalize, including special messages.
            prompt: The prompt being finalized.
            kernel: The kernel instance (required for hydration).
            **kwargs: Additional keyword arguments (not used).

        Returns:
            The list of messages with special messages replaced by their
            hydrated versions.
        """
        if not kernel:
            logger.warning("No kernel provided, cannot hydrate special messages")
            return [m for m in messages if not isinstance(m, SpecialPromptMessage)]

        # Process messages to hydrate special messages
        hydrated_messages = []
        for message in messages:
            if isinstance(message, SpecialPromptMessage):
                # Hydrate special message and add resulting messages
                hydrated = await message.hydrate(kernel)
                hydrated_messages.extend(hydrated)
            else:
                # Regular message, add as is
                hydrated_messages.append(message)

        return hydrated_messages
