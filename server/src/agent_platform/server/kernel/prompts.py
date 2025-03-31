import logging

from agent_platform.core.agent_architectures import StateBase
from agent_platform.core.kernel import PromptsInterface
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

logger = logging.getLogger(__name__)

class AgentServerPromptsInterface(PromptsInterface, UsesKernelMixin):
    """Handles prompt building/management via importlib.resources."""

    async def load_and_format(
        self,
        path: str,
        *,
        package: str | None = None,
        state: StateBase | None = None,
    ) -> Prompt:
        """
        Load a prompt from a YAML file stored as package data, then format it.

        Arguments:
            path:    The relative path to the YAML file within `package`.
            package: The fully-qualified Python package where the YAML file lives.
                     For example, "agent_platform.architectures.default".
            state:   The agent architecture's state to use in formatting. (Optional.)

        Returns:
            A fully formatted Prompt.
        """
        from importlib import resources

        # Locate the data file in the specified package
        try:
            resource_path = resources.files(package) / path
        except AttributeError as ex:
            # (In older Pythons without resources.files, use
            # `importlib_resources.files` or fallback)
            raise ValueError(
                f"Failed to locate resource files in package {package}. "
                "Are you sure it's a valid Python package?",
            ) from ex

        if not resource_path.is_file():
            raise FileNotFoundError(
                f"Prompt file not found in package '{package}' at path '{path}'",
            )

        # Load the YAML into a Prompt
        with resource_path.open('r') as f:
            pre_format_prompt = Prompt.load_yaml(f)

        # Format with kernel & state
        with self.kernel.otel.span("format_prompt") as span:
            span.add_event_with_artifacts(
                "formatting prompt",
                ("prompt-pre-format.yaml", pre_format_prompt.to_pretty_yaml()),
            )

            final_prompt = pre_format_prompt.format_with_values(
                kernel=self.kernel,
                state=state,
            )

            span.add_event_with_artifacts(
                "formatted prompt",
                ("prompt-post-format.yaml", final_prompt.to_pretty_yaml()),
            )

        return final_prompt
