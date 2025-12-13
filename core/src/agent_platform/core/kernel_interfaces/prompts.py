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
        **kwargs,
    ) -> Prompt:
        """
        Format a prompt using the kernel and state.

        Arguments:
            prompt: The prompt to format.
            state:   The agent architecture's state to use in formatting. (Optional.)
            **kwargs: Additional values to pass into prompt templating.

        Returns:
            A fully formatted Prompt.
        """

    @abstractmethod
    def record_tools_in_trace(self, prompt: Prompt, span_name: str = "prompt_tools") -> None:
        """Record tools from a prompt in a trace.

        This method should be called just before submission to a provider,
        after tools have been attached to the prompt.

        Args:
            prompt: The prompt containing tools
            span_name: Optional name for the span
        """
