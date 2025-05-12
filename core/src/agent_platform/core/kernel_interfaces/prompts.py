from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from agent_platform.core.prompts.prompt import Prompt

if TYPE_CHECKING:
    from agent_platform.core.agent_architectures.state import StateBase


class PromptsInterface(ABC):
    """Handles prompt building and management with opinionated formatting."""

    @abstractmethod
    async def format_prompt(
        self,
        prompt: Prompt,
        *,
        state: "StateBase | None" = None,
    ) -> Prompt:
        """
        Format a prompt using the kernel and state.

        Arguments:
            prompt: The prompt to format.
            state:   The agent architecture's state to use in formatting. (Optional.)

        Returns:
            A fully formatted Prompt.
        """
        pass
