from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar

import boto3

from agent_server_types_v2.delta import GenericDelta
from agent_server_types_v2.delta.compute_delta import compute_generic_deltas
from agent_server_types_v2.kernel import Kernel
from agent_server_types_v2.model_selector.base import ModelSelector
from agent_server_types_v2.models.model import Model
from agent_server_types_v2.platforms.base import (
    PlatformClient,
)
from agent_server_types_v2.platforms.bedrock.configs import (
    BedrockModelMap,
    BedrockPlatformConfigs,
)
from agent_server_types_v2.platforms.bedrock.converters import BedrockConverters
from agent_server_types_v2.platforms.bedrock.parameters import (
    BedrockPlatformParameters,
)
from agent_server_types_v2.platforms.bedrock.parsers import BedrockParsers
from agent_server_types_v2.platforms.bedrock.prompts import BedrockPrompt
from agent_server_types_v2.responses.response import ResponseMessage

if TYPE_CHECKING:
    from types_boto3_bedrock_runtime.client import BedrockRuntimeClient


class BedrockClient(PlatformClient):
    """A client for the Bedrock platform."""

    NAME: ClassVar[str] = "bedrock"

    def __init__(
        self,
        *,
        kernel: Kernel | None = None,
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

    def _init_converters(self, kernel: Kernel | None = None) -> BedrockConverters:
        self._converters = BedrockConverters()
        if kernel is not None:
            self._converters.attach_kernel(kernel)
        return self._converters

    def _init_parsers(self, kernel: Kernel | None = None) -> BedrockParsers:
        self._parsers = BedrockParsers()
        if kernel is not None:
            self._parsers.attach_kernel(kernel)
        return self._parsers

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

    def _init_configs(self, kernel: Kernel | None = None) -> BedrockPlatformConfigs:
        self._configs = BedrockPlatformConfigs()
        if kernel is not None:
            self._configs.attach_kernel(kernel)
        return self._configs

    def _init_clients(
        self,
        parameters: BedrockPlatformParameters,
    ) -> "BedrockRuntimeClient":
        return boto3.client(
            "bedrock-runtime",
            **parameters.model_dump(exclude_none=True),
        )

    async def generate_response(
        self,
        prompt: BedrockPrompt,
        model: Model | ModelSelector,
    ) -> ResponseMessage:
        """Generate a complete response from the Bedrock platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.
        Returns:
            The complete model response.
        """
        if isinstance(model, ModelSelector):
            model = model.select_model()
        model_id = BedrockModelMap[model.name]
        request = prompt.as_platform_request(model_id)
        response = self._bedrock_runtime_client.converse(**request)
        return self.parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: BedrockPrompt,
        model: Model | ModelSelector,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the Bedrock platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        if isinstance(model, ModelSelector):
            model = model.select_model()
        model_id = BedrockModelMap[model.name]
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
