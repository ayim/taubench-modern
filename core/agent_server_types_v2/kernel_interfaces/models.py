from abc import ABC, abstractmethod

from agent_server_types_v2.models import ModelResponse
from agent_server_types_v2.prompts import Prompt


class ModelsInterface(ABC):
    """Provides interface for interacting with the agent's configured LLM."""

    @abstractmethod
    async def generate_response(self, prompt: Prompt) -> ModelResponse:
        """Generates a response to a prompt.

        Arguments:
            prompt: The prompt to generate a response for.

        Returns:
            The generated model response.
        """
        pass