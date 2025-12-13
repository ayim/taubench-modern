from abc import ABC, abstractmethod

from agent_platform.core.thread import ThreadUserMessage


class UserInteractionsInterface(ABC):
    """Access to the user in the kernel interface."""

    @abstractmethod
    async def prompt_user(self) -> ThreadUserMessage:
        """Prompts the user for input and blocks until the user responds.

        Returns:
            The user's response as a ThreadUserMessage.
        """
