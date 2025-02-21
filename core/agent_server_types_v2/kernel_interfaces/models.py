from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from agent_server_types_v2.models import ModelResponse
from agent_server_types_v2.prompts import Prompt
from agent_server_types_v2.thread import Thread
from agent_server_types_v2.thread.content.base import ContentDelta


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

    @abstractmethod
    async def stream_response(
        self,
        prompt: Prompt,
    ) -> AsyncGenerator[ContentDelta, None]:
        """Streams a response to a prompt.

        Arguments:
            prompt: The prompt to generate a response for.

        Returns:
            An async generator of ThreadMessageChunk objects.
        """
        pass

    @abstractmethod
    async def stream_response_to_thread(
        self,
        prompt: Prompt,
        thread: Thread,
    ) -> None:
        """Streams a response to the provided thread.

        Arguments:
            prompt: The prompt to generate a response for.
            thread: The thread to stream the response to.
        """
        pass
