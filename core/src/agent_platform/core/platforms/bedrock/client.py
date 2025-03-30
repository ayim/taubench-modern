import json
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, cast

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import (
    PlatformClient,
)
from agent_platform.core.platforms.bedrock.configs import (
    BedrockModelMap,
    BedrockPlatformConfigs,
)
from agent_platform.core.platforms.bedrock.converters import BedrockConverters
from agent_platform.core.platforms.bedrock.parameters import (
    BedrockPlatformParameters,
)
from agent_platform.core.platforms.bedrock.parsers import BedrockParsers
from agent_platform.core.platforms.bedrock.prompts import BedrockPrompt
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from types_boto3_bedrock_runtime.client import BedrockRuntimeClient

    from agent_platform.core.kernel import Kernel


class BedrockClient(
    PlatformClient[
        BedrockConverters,
        BedrockParsers,
        BedrockPlatformParameters,
        BedrockPlatformConfigs,
    ],
):
    """A client for the Bedrock platform."""

    NAME: ClassVar[str] = "bedrock"

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: BedrockPlatformParameters | dict | None = None,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            kernel=kernel,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            parameters=parameters,
            **kwargs,
        )
        self._bedrock_runtime_client = self._init_clients(
            self._parameters,
        )

    def _init_converters(self, kernel: "Kernel | None" = None) -> BedrockConverters:
        converters = BedrockConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: BedrockPlatformParameters | dict | None = None,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        **kwargs: Any,
    ) -> BedrockPlatformParameters:
        if parameters is None:
            parameters = BedrockPlatformParameters(
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                **kwargs,
            )
        else:
            if region_name is not None:
                kwargs["region_name"] = region_name
            if aws_access_key_id is not None:
                kwargs["aws_access_key_id"] = aws_access_key_id
            if aws_secret_access_key is not None:
                kwargs["aws_secret_access_key"] = aws_secret_access_key
            parameters = parameters.model_copy(update=kwargs)
        return parameters

    def _init_parsers(self) -> BedrockParsers:
        return BedrockParsers()

    def _init_configs(self) -> BedrockPlatformConfigs:
        return BedrockPlatformConfigs()

    def _init_clients(
        self,
        parameters: BedrockPlatformParameters,
    ) -> "BedrockRuntimeClient":
        import boto3

        # Remove the kind from the parameters before passing them to boto3
        without_kind = parameters.model_dump(exclude_none=True)
        without_kind.pop("kind")

        return boto3.client(
            "bedrock-runtime",
            **without_kind,
        )

    async def generate_response(
        self,
        prompt: BedrockPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a complete response from the Bedrock platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.
        Returns:
            The complete model response.
        """
        model_id = cast(str, BedrockModelMap[model])
        request = prompt.as_platform_request(model_id)
        response = self._bedrock_runtime_client.converse(**request)
        return self.parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: BedrockPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the Bedrock platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        model_id = cast(str, BedrockModelMap[model])
        request = prompt.as_platform_request(model_id, stream=True)
        response = self._bedrock_runtime_client.converse_stream(**request)

        # Initialize message state
        message: dict[str, Any] = {}
        last_message: dict[str, Any] = {}

        # Process each event through the parser to get deltas
        for event in response["stream"]:
            async for delta in self._parsers.parse_stream_event(
                event,
                response,
                message,
                last_message,
            ):
                yield delta

            # Update last message state after processing each event
            last_message = deepcopy(message)

        final_event = self._generate_platform_metadata()
        response["stream"] = repr(response["stream"])
        if "metadata" not in message:
            message["metadata"] = {}
        message["metadata"].update(final_event)
        message["raw_response"] = response

        for delta in compute_generic_deltas(last_message, message):
            yield delta

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings using a Bedrock embedding model.

        Args:
            texts: List of text strings to create embeddings for.
            model: The model to use to generate embeddings.

        Returns:
            A dictionary containing the embeddings and any
            additional model-specific information.
        """
        model_id = cast(str, BedrockModelMap[model])

        # Different Bedrock embedding models use different request formats;
        # so we need to handle them differently.
        if model_id.startswith("amazon.titan-embed-text"):
            embeddings = []
            total_tokens = 0

            for text in texts:
                request = {"inputText": text}
                response = self._bedrock_runtime_client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(request),
                )
                response_body = json.loads(response["body"].read())
                # the JSON deserializer in the AWS SDK already converts the embeddings
                # to a Python list of floats.
                # Hence, we can just append the embedding to the list.
                embeddings.append(response_body["embedding"])
                total_tokens += response_body.get("inputTextTokenCount", 0)

            return {
                "embeddings": embeddings,
                "model": model,
                "usage": {"total_tokens": total_tokens},
            }

        elif model_id.startswith("cohere.embed"):
            # Cohere embedding models support batch processing
            request = {
                "texts": texts,
                "input_type": "search_document",
                "embedding_types": ["float"],
            }

            response = self._bedrock_runtime_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request),
            )

            response_body = json.loads(response["body"].read())

            return {
                "embeddings": response_body["embeddings"],
                "model": model,
                "usage": {"total_tokens": response_body.get("token_count", 0)},
            }

        else:
            raise ValueError(f"Model {model_id} is not a supported embedding model")

PlatformClient.register_platform_client("bedrock", BedrockClient)
