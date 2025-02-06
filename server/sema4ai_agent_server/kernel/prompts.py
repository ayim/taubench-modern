from agent_server_types_v2.kernel import PromptsInterface
from agent_server_types_v2.prompts.messages import PromptUserMessage
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerPromptsInterface(PromptsInterface, UsesKernelMixin):
    """Handles prompt building and management with opinionated formatting."""

    async def format_prompt_string(self, prompt: str, **kwargs: object) -> str:
        """Formats a prompt string with the given arguments.

        Kernel-related prompt placeholders will be auto-replaced with the appropriate values.
        For any other placeholders, the caller is responsible for providing the
        appropriate values via kwargs.

        Arguments:
            prompt: The prompt string to format.
            **kwargs: Additional keyword arguments for formatting.

        Returns:
            The formatted prompt string.
        """
        raise NotImplementedError("Not implemented")

    async def format_as_user_message(self, prompt: str, **kwargs: object) -> PromptUserMessage:
        """Formats a string and produces a PromptMessageUser object.

        The resulting PromptMessageUser object can be used directly when
        building a Prompt's messages array to submit to a model.

        Arguments:
            prompt: The string to format as a user message.
            **kwargs: Additional keyword arguments for formatting.

        Returns:
            A PromptUserMessage object.
        """
        raise NotImplementedError("Not implemented")
