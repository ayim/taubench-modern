from agent_server_types_v2.kernel import ModelsInterface
from agent_server_types_v2.models import ModelResponse
from agent_server_types_v2.prompts import Prompt
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerModelsInterface(ModelsInterface, UsesKernelMixin):
    """Provides interface for interacting with the agent's configured LLM."""

    async def generate_response(self, prompt: Prompt) -> ModelResponse:
        """Generates a response to a prompt.

        Arguments:
            prompt: The prompt to generate a response for.

        Returns:
            The generated model response.
        """
        # Pick out from the configured providers on the model
        # (maybe based on a model arg, or a default)

        raise NotImplementedError("Not implemented")