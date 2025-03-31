"""OpenAI platform client."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import (
    PlatformClient,
)
from agent_platform.core.platforms.openai.configs import (
    OpenAIModelMap,
    OpenAIPlatformConfigs,
)
from agent_platform.core.platforms.openai.converters import OpenAIConverters
from agent_platform.core.platforms.openai.parameters import (
    OpenAIPlatformParameters,
)
from agent_platform.core.platforms.openai.parsers import OpenAIParsers
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel


class OpenAIClient(
    PlatformClient[
        OpenAIConverters,
        OpenAIParsers,
        OpenAIPlatformParameters,
        OpenAIPlatformConfigs,
        OpenAIPrompt,
    ],
):
    """A client for the OpenAI platform."""

    NAME: ClassVar[str] = "openai"

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: OpenAIPlatformParameters | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            kernel=kernel,
            parameters=parameters,
            **kwargs,
        )
        self._openai_client = self._init_clients(
            self._parameters,
        )

    def _init_converters(self, kernel: "Kernel | None" = None) -> OpenAIConverters:
        converters = OpenAIConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: OpenAIPlatformParameters | None = None,
        **kwargs: Any,
    ) -> OpenAIPlatformParameters:
        if parameters is None:
            parameters = OpenAIPlatformParameters(**kwargs)
        else:
            parameters = parameters.model_copy(update=kwargs)
        return parameters

    def _init_parsers(self) -> OpenAIParsers:
        return OpenAIParsers()

    def _init_configs(self) -> OpenAIPlatformConfigs:
        return OpenAIPlatformConfigs()

    def _init_clients(
        self,
        parameters: OpenAIPlatformParameters,
    ) -> Any:
        import openai

        # Create OpenAI client with parameters
        client = openai.OpenAI(
            api_key=parameters.api_key,
            organization=parameters.organization_id,
            base_url=parameters.base_url,
        )

        return client

    async def generate_response(
        self,
        prompt: OpenAIPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a complete response from the OpenAI platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

        Returns:
            The complete model response.
        """
        model_id = OpenAIModelMap.mapping[model]
        request = prompt.as_platform_request(model_id)
        response = await self._openai_client.chat.completions.create(**request)
        return self.parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: OpenAIPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the OpenAI platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        model_id = OpenAIModelMap.mapping[model]
        request = prompt.as_platform_request(model_id, stream=True)
        response_stream = await self._openai_client.chat.completions.create(**request)

        # Initialize message state
        message = ResponseMessage(content=[], role="agent")
        last_message = ResponseMessage(content=[], role="agent")

        # Process each event through the parser to get deltas
        for event in response_stream:
            async for delta in self._parsers.parse_stream_event(
                event,
                response_stream,
                message,
                last_message,
            ):
                yield delta

            # Update last message state after processing each event
            last_message = deepcopy(message)

        final_event = self._generate_platform_metadata()
        metadata = message.metadata or {}
        metadata.update(final_event)

        # Handle raw response based on response type
        raw_response = (
            response_stream[-1]
            if isinstance(response_stream, list)
            else response_stream
        )
        raw_response_dict = {
            **raw_response,
            "stream": None,
        }

        # Create new message with updated metadata and raw response
        message = ResponseMessage(
            content=message.content,
            role=message.role,
            metadata=metadata,
            raw_response=raw_response_dict,
            stop_reason=message.stop_reason,
            usage=message.usage,
            metrics=message.metrics,
            additional_response_fields=message.additional_response_fields,
        )

        # Convert messages to dictionaries for delta computation
        last_message_dict = last_message.model_dump()
        message_dict = message.model_dump()

        for delta in compute_generic_deltas(last_message_dict, message_dict):
            yield delta

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings using an OpenAI embedding model.

        Args:
            texts: List of text strings to create embeddings for.
            model: The model to use to generate embeddings.

        Returns:
            A dictionary containing the embeddings and any
            additional model-specific information.
        """
        model_id = OpenAIModelMap.mapping[model]
        response = await self._openai_client.embeddings.create(
            model=model_id,
            input=texts,
        )

        return {
            "embeddings": [item["embedding"] for item in response["data"]],
            "model": model,
            "usage": {
                "total_tokens": response["usage"]["total_tokens"],
            },
        }


PlatformClient.register_platform_client("openai", OpenAIClient)
