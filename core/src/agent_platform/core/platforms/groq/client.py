import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import (
    PlatformClient,
    PlatformConfigs,
    PlatformModelMap,
)
from agent_platform.core.platforms.groq.configs import (
    GroqModelMap,
    GroqPlatformConfigs,
)
from agent_platform.core.platforms.groq.converters import GroqConverters
from agent_platform.core.platforms.groq.parameters import GroqPlatformParameters
from agent_platform.core.platforms.groq.parsers import GroqParsers
from agent_platform.core.platforms.groq.prompts import GroqPrompt
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from groq import AsyncGroq

    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)


class GroqClient(
    PlatformClient[
        GroqConverters,
        GroqParsers,
        GroqPlatformParameters,
        GroqPrompt,
    ],
):
    """A client for the Groq platform."""

    NAME: ClassVar[str] = "groq"
    configs: ClassVar[type[PlatformConfigs]] = GroqPlatformConfigs
    model_map: ClassVar[type[PlatformModelMap]] = GroqModelMap

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: GroqPlatformParameters | None = None,
        **kwargs: Any,
    ):
        super().__init__(kernel=kernel, parameters=parameters, **kwargs)
        self._client = self._init_client(self._parameters)

    def _init_client(self, parameters: GroqPlatformParameters) -> "AsyncGroq":
        from groq import AsyncGroq

        if parameters.groq_api_key is None:
            raise ValueError("Groq API key is required")

        return AsyncGroq(api_key=parameters.groq_api_key.get_secret_value())

    def _init_converters(self, kernel: "Kernel | None" = None) -> GroqConverters:
        converters = GroqConverters()
        if kernel:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: GroqPlatformParameters | None = None,
        **kwargs: Any,
    ) -> GroqPlatformParameters:
        if parameters is None:
            raise ValueError("Parameters are required for Groq client")
        return parameters

    def _init_parsers(self) -> GroqParsers:
        return GroqParsers()

    async def generate_response(
        self,
        prompt: GroqPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a response from the Groq platform."""
        # TODO: Otel Span?
        request = prompt.as_platform_request(model)
        response = await self._client.chat.completions.create(**request)
        return self._parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: GroqPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the Groq platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        logger.info(f"Streaming with Groq model: {model}")
        request = prompt.as_platform_request(model, stream=True)

        # Initialize message state
        message: dict[str, Any] = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message: dict[str, Any] = {}

        # Add stream=True to ensure streaming is enabled
        request["stream"] = True
        response = await self._client.chat.completions.create(**request)
        async for event in response:
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
        """Create embeddings using a Groq embedding model."""
        model_id = GroqModelMap.model_aliases[model]
        logger.info(
            f"Creating embeddings with Groq model: {model} (model_id: {model_id})",
        )

        if not texts:
            return {
                "embeddings": [],
                "model": model,
                "usage": {"total_tokens": 0},
            }
        embeddings = []
        total_tokens = 0
        for text in texts:
            response = await self._client.embeddings.create(
                model=model_id,
                input=text,
            )
            embedding = response.data[0].embedding
            total_tokens += response.usage.total_tokens
            embeddings.append(embedding)
        return {
            "embeddings": embeddings,
            "model": model,
            "usage": {"total_tokens": total_tokens},
        }


PlatformClient.register_platform_client("groq", GroqClient)
