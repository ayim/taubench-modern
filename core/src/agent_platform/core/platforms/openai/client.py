from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, cast

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
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.platforms.openai.parsers import OpenAIParsers
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from openai import OpenAI

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
        self._openai_client = self._init_client(self._parameters)

    def _init_client(self, parameters: OpenAIPlatformParameters) -> "OpenAI":
        from openai import OpenAI

        if parameters.openai_api_key is None:
            raise ValueError("OpenAI API key is required")

        return OpenAI(api_key=parameters.openai_api_key.get_secret_value())

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
            raise ValueError("Parameters are required for OpenAI client")
        return parameters

    def _init_parsers(self) -> OpenAIParsers:
        return OpenAIParsers()

    def _init_configs(self) -> OpenAIPlatformConfigs:
        return OpenAIPlatformConfigs()

    async def _generate_response(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a response from the OpenAI platform."""
        response = self._openai_client.chat.completions.create(**request)
        return response

    async def _generate_stream_response(
        self,
        request: dict[str, Any],
    ) -> AsyncGenerator[Any, None]:
        """Stream a response from the OpenAI platform."""
        # Add stream=True to ensure streaming is enabled
        request["stream"] = True

        # Get the streaming response
        response = self._openai_client.chat.completions.create(**request)

        # Yield each chunk directly
        for chunk in response:
            yield chunk

    async def generate_response(
        self,
        prompt: OpenAIPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a response from the OpenAI platform."""
        # TODO: Otel Span?
        model_id = cast(str, OpenAIModelMap[model])
        request = prompt.as_platform_request(model_id)
        response = await self._generate_response(request)
        return self._parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: OpenAIPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the OpenAI platform."""

        model_id = cast(str, OpenAIModelMap[model])
        request = prompt.as_platform_request(model_id, stream=True)

        # Initialize message state
        message: dict[str, Any] = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message: dict[str, Any] = {}

        # Process each event through the parser
        async for event in self._generate_stream_response(request):
            async for delta in self._parsers.parse_stream_event(
                event,
                message,
                last_message,
            ):
                yield delta

            # Update last message state after processing each event
            last_message = deepcopy(message)

        # Add final metadata and platform info
        final_event = self._generate_platform_metadata()
        if "metadata" not in message:
            message["metadata"] = {}
        message["metadata"].update(final_event)

        # Put request ID (if any) into raw_response
        request_id = message.get("additional_response_fields", {}).get("id", "unknown")
        message["raw_response"] = {
            "ResponseMetadata": {
                "RequestId": request_id,
                "HTTPStatusCode": 200,
                "RetryAttempts": 0,
            },
            "stream": None,
        }

        # Generate final deltas
        for delta in compute_generic_deltas(last_message, message):
            yield delta

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings using a OpenAI embedding model."""
        # TODO: Implement embeddings
        # with self.kernel.otel.span("create_embeddings") as span:
        #     model_id = cast(str, OpenAIModelMap[model])
        #     span.add_event("embedding on model", {"model": model_id})

        #     if not texts:
        #         span.add_event("no texts provided to embed; returning empty list")
        #         return {
        #             "embeddings": [],
        #             "model": model,
        #             "usage": {"total_tokens": 0},
        #         }

        #     request = {
        #         "model": model_id,
        #         "input": texts,
        #     }
        #     response = await self._openai_client.embeddings.create(**request)
        #     return response
        raise NotImplementedError("OpenAI embeddings are not yet implemented")


PlatformClient.register_platform_client("openai", OpenAIClient)
