import logging

from agent_platform.core.agent_architectures import StateBase
from agent_platform.core.kernel import PromptsInterface
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

logger = logging.getLogger(__name__)


class AgentServerPromptsInterface(PromptsInterface, UsesKernelMixin):
    """Handles prompt building/management via importlib.resources."""

    async def format_prompt(
        self,
        prompt: Prompt,
        *,
        state: StateBase | None = None,
    ) -> Prompt:
        """
        Format a prompt using the kernel and state.

        Arguments:
            prompt: The prompt to format.
            state:   The agent architecture's state to use in formatting. (Optional.)

        Returns:
            A fully formatted Prompt.
        """
        # Format with kernel & state
        with self.kernel.otel.span("format_prompt") as span:
            span.add_event_with_artifacts(
                "formatting prompt",
                ("prompt-pre-format.yaml", prompt.to_pretty_yaml()),
            )

            final_prompt = prompt.format_with_values(
                kernel=self.kernel,
                state=state,
            )

            span.add_event_with_artifacts(
                "formatted prompt",
                ("prompt-post-format.yaml", final_prompt.to_pretty_yaml()),
            )

        return final_prompt
