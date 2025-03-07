from agent_server_types_v2.agent_architectures import StateBase
from agent_server_types_v2.kernel import PromptsInterface
from agent_server_types_v2.prompts.prompt import Prompt
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerPromptsInterface(PromptsInterface, UsesKernelMixin):
    """Handles prompt building and management with opinionated formatting."""

    async def load_and_format(
        self,
        path: str,
        state: StateBase | None = None,
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
        pre_format_prompt = None
        try:
            # This is a little wonky, but we're making the dev UX nicer
            # on the other side by allowing for file references relative
            # to the agent architecture's root directory.
            from importlib import resources
            from inspect import getmodule, stack
            from pathlib import PurePosixPath

            # Inspect the call stack to find the caller's module
            caller_frame = stack()[1]
            caller_module = getmodule(caller_frame[0])
            if caller_module is None or caller_module.__package__ is None:
                raise ValueError(
                    "Cannot determine caller's package for relative resource loading.",
                )

            # Split the relative path into parts
            path_parts = PurePosixPath(path).parts
            package = caller_module.__package__ + "." + ".".join(path_parts[:-1])
            resource_name = path_parts[-1]

            # Use importlib resources to open the prompt file
            pre_format_prompt = Prompt.load_yaml(
                resources.files(package).joinpath(resource_name),
            )
        except Exception as outer_ex:
            try:
                # If we can't load the prompt from the resource, try the
                # file system the "regular" way.
                pre_format_prompt = Prompt.load_yaml(path)
            except Exception as inner_ex:
                raise inner_ex from outer_ex

        # If we have a None prompt, raise an error
        if pre_format_prompt is None:
            raise ValueError(f"Failed to load prompt from {path}")

        # Next, let's format the prompt with applicable values from the kernel
        # and the architecture state.
        final_prompt = pre_format_prompt.format_with_values(
            kernel=self.kernel,
            state=state,
        )

        return final_prompt
