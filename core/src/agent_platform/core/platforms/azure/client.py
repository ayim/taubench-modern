import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, ClassVar

from agent_platform.core.delta import GenericDelta
from agent_platform.core.platforms.azure.configs import (
    AzureOpenAIModelMap,
    AzureOpenAIPlatformConfigs,
)
from agent_platform.core.platforms.azure.converters import AzureOpenAIConverters
from agent_platform.core.platforms.azure.parameters import AzureOpenAIPlatformParameters
from agent_platform.core.platforms.azure.parsers import AzureOpenAIParsers
from agent_platform.core.platforms.azure.prompts import AzureOpenAIPrompt
from agent_platform.core.platforms.base import (
    PlatformClient,
)
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from openai import AsyncAzureOpenAI

    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)


class AzureOpenAIClient(
    PlatformClient[
        AzureOpenAIConverters,
        AzureOpenAIParsers,
        AzureOpenAIPlatformParameters,
        AzureOpenAIPlatformConfigs,
        AzureOpenAIPrompt,
    ],
):
    """A client for the AzureOpenAI platform."""

    NAME: ClassVar[str] = "azure"

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: AzureOpenAIPlatformParameters | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            kernel=kernel,
            parameters=parameters,
            **kwargs,
        )
        self._azure_client = self._init_client(self._parameters)
        self._azure_embeddings_client = self._init_embeddings_client(self._parameters)

    def _init_client(
        self,
        parameters: AzureOpenAIPlatformParameters,
    ) -> "AsyncAzureOpenAI":
        """Initialize the Azure OpenAI client."""
        from openai import AsyncAzureOpenAI

        # Required parameters check
        if parameters.azure_api_key is None:
            raise ValueError("AzureOpenAI API key is required")

        if (
            parameters.azure_endpoint_url is None
            or parameters.azure_deployment_name is None
        ):
            raise ValueError(
                "AzureOpenAI endpoint URL and/or deployment name are required",
            )

        # Initialize the client with the API key and endpoint URL
        return AsyncAzureOpenAI(
            api_key=parameters.azure_api_key.get_secret_value(),
            azure_endpoint=parameters.azure_generated_endpoint_url,
            api_version=parameters.azure_api_version,
        )

    def _init_embeddings_client(
        self,
        parameters: AzureOpenAIPlatformParameters,
    ) -> "AsyncAzureOpenAI":
        """Initialize the Azure OpenAI client for embeddings."""
        from openai import AsyncAzureOpenAI

        # Required parameters check
        if parameters.azure_api_key is None:
            raise ValueError("AzureOpenAI API key is required")

        if parameters.azure_endpoint_url is None:
            raise ValueError("AzureOpenAI endpoint URL is required")

        if parameters.azure_deployment_name_embeddings is None:
            raise ValueError("AzureOpenAI deployment name for embeddings is required")

        # Initialize the client with the API key and endpoint URL
        return AsyncAzureOpenAI(
            api_key=parameters.azure_api_key.get_secret_value(),
            azure_endpoint=parameters.azure_generated_endpoint_url_embeddings,
            api_version=parameters.azure_api_version,
        )

    def _init_converters(
        self,
        kernel: "Kernel | None" = None,
    ) -> AzureOpenAIConverters:
        converters = AzureOpenAIConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: AzureOpenAIPlatformParameters | None = None,
        **kwargs: Any,
    ) -> AzureOpenAIPlatformParameters:
        if parameters is None:
            raise ValueError("Parameters are required for AzureOpenAI client")
        return parameters

    def _init_parsers(self) -> AzureOpenAIParsers:
        return AzureOpenAIParsers()

    def _init_configs(self) -> AzureOpenAIPlatformConfigs:
        return AzureOpenAIPlatformConfigs()

    async def generate_response(
        self,
        prompt: AzureOpenAIPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a response from the AzureOpenAI platform."""
        request = prompt.as_platform_request(model)
        response = await self._azure_client.chat.completions.create(**request)
        return self._parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: AzureOpenAIPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the AzureOpenAI platform."""
        from copy import deepcopy

        logger.info(f"Streaming with Azure OpenAI model: {model}")
        request = prompt.as_platform_request(model, stream=True)

        # Initialize message state
        message: dict[str, Any] = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message: dict[str, Any] = {}

        # Process each event through the parser
        response = await self._azure_client.chat.completions.create(**request)
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
        from agent_platform.core.delta.compute_delta import compute_generic_deltas

        for delta in compute_generic_deltas(last_message, message):
            yield delta

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings using a AzureOpenAI embedding model."""
        model_id = AzureOpenAIModelMap.model_aliases[model]
        logger.info(
            f"Creating embeddings with Azure model: {model} (model_id: {model_id})",
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
            response = await self._azure_embeddings_client.embeddings.create(
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


PlatformClient.register_platform_client("azure", AzureOpenAIClient)
