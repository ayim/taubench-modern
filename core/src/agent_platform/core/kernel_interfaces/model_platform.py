from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING

from agent_platform.core.delta import GenericDelta
from agent_platform.core.prompts import Prompt
from agent_platform.core.responses import ResponseMessage
from agent_platform.core.responses.streaming import ResponseStreamPipe

if TYPE_CHECKING:
    from agent_platform.core.platforms.base import PlatformClient


class PlatformInterface(ABC):
    """Provides interface for interacting with the agent's configured LLM."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the platform."""
        pass

    @property
    @abstractmethod
    def client(self) -> "PlatformClient":
        """The client for the platform."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        prompt: Prompt,
        model: str,
    ) -> ResponseMessage:
        """Generates a response to a prompt.

        Arguments:
            prompt: The prompt to generate a response for.
            model: The model to use to generate the response.

        Returns:
            The generated model response.
        """
        pass

    @abstractmethod
    def stream_response(
        self,
        prompt: Prompt,
        model: str,
    ) -> AbstractAsyncContextManager[ResponseStreamPipe]:
        """Streams a response to a prompt.

        Arguments:
            prompt: The prompt to generate a response for.
            model: The model to use to generate the response.

        Returns:
            An async context manager that yields a ResponseStreamPipe
            object managing the response stream.
        """
        pass

    @abstractmethod
    async def stream_raw_response(
        self,
        prompt: Prompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Streams raw GenericDeltas from a prompt response.

        This method bypasses the ResponseStreamPipe and returns the raw delta stream
        directly from the platform client. Intended for special endpoints that need
        the raw delta stream.

        Arguments:
            prompt: The prompt to generate a response for.
            model: The model to use to generate the response.

        Returns:
            An async generator yielding GenericDelta objects.
        """
        pass
