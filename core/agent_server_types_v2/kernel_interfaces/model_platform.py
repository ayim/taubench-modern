from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from agent_server_types_v2.models.model import Model
from agent_server_types_v2.prompts import Prompt
from agent_server_types_v2.responses import ResponseMessage
from agent_server_types_v2.thread import Thread
from agent_server_types_v2.thread.content.base import ContentDelta

if TYPE_CHECKING:
    from agent_server_types_v2.model_selector import ModelSelector


class PlatformInterface(ABC):
    """Provides interface for interacting with the agent's configured LLM."""

    # TODO: Currently, this assumes we will have only one platform bound to
    # the kernel. But there are use cases where we would want to have multiple
    # platforms bound to the kernel. We need to revisit this interface to
    # support this. Perhaps we just need to make the `platform` property
    # a list of platforms, but it needs to be thought out.

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the platform."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        prompt: Prompt,
        model: "Model | ModelSelector",
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
    async def stream_response(
        self,
        prompt: Prompt,
        model: "Model | ModelSelector",
    ) -> AsyncGenerator[ContentDelta, None]:
        """Streams a response to a prompt.

        Arguments:
            prompt: The prompt to generate a response for.
            model: The model to use to generate the response.
        Returns:
            An async generator of ThreadMessageChunk objects.
        """
        pass

    @abstractmethod
    async def stream_response_to_thread(
        self,
        prompt: Prompt,
        model: "Model | ModelSelector",
        thread: Thread,
    ) -> None:
        """Streams a response to the provided thread.

        Arguments:
            prompt: The prompt to generate a response for.
            model: The model to use to generate the response.
            thread: The thread to stream the response to.
        """
        pass

    @abstractmethod
    def get_model(self, selection: str | None = None) -> Model:
        """Uses the default model selector for the current platform to
        return a model based on the provided selection criteria.

        Args:
            selection: Optional selection criteria, which could be a model name,
                       quality tier, or other selector-specific identifier. If
                       no selection is provided, the default model for the
                       platform will be selected.

        Returns:
            The selected Model instance.

        Raises:
            ValueError: If no suitable model can be selected.
        """
        pass
