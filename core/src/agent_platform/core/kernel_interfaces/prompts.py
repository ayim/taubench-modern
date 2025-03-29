from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from agent_platform.core.prompts.prompt import Prompt

if TYPE_CHECKING:
    from agent_platform.core.agent_architectures.state import StateBase


class PromptsInterface(ABC):
    """Handles prompt building and management with opinionated formatting."""

    @abstractmethod
    async def load_and_format(
        self,
        path: str,
        state: "StateBase | None" = None,
        package: str | None = None,
    ) -> Prompt:
        """Load a prompt from a YAML file and format it with values from the
        kernel and the given architecture state.

        Arguments:
            path: The path to the YAML file containing the prompt (relative to
                  the agent architecture's root directory).
            state: The architecture's state to use in formatting. (Optional.)

        Returns:
            The fully formatted prompt.
        """
        pass
