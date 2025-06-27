import json
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, cast

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.errors import ErrorCode
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.platforms.base import (
    PlatformClient,
    PlatformConfigs,
    PlatformModelMap,
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
        BedrockPrompt,
    ],
):
    """A client for the Bedrock platform."""

    NAME: ClassVar[str] = "bedrock"
    configs: ClassVar[type[PlatformConfigs]] = BedrockPlatformConfigs
    model_map: ClassVar[type[PlatformModelMap]] = BedrockModelMap

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: BedrockPlatformParameters | None = None,
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
        parameters: BedrockPlatformParameters | None = None,
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

    def _init_clients(
        self,
        parameters: BedrockPlatformParameters,
    ) -> "BedrockRuntimeClient":
        import boto3
        from botocore.config import Config

        # Remove the kind and config_params from the
        # parameters before passing them to boto3
        without_kind_and_config_params = parameters.model_dump(exclude_none=True)
        without_kind_and_config_params.pop("kind")
        without_kind_and_config_params.pop("config_params")

        # Create a new Config object from the config_params
        if parameters.config_params:
            config = Config(**parameters.config_params)
            without_kind_and_config_params["config"] = config

        return boto3.client(
            "bedrock-runtime",
            **without_kind_and_config_params,
        )

    def _handle_bedrock_error(  # noqa: C901, PLR0911, PLR0912
        self, error: Exception, model: str, error_type: type[PlatformError] = PlatformError
    ) -> PlatformError:
        """Handle Bedrock errors and convert them to PlatformError instances.

        Args:
            error: The boto3 exception that was raised
            model: The model being used when the error occurred
            error_type: The type of error to return. Defaults to PlatformError.

        Returns:
            PlatformError: The appropriate error for the given Bedrock error
        """
        from botocore.exceptions import ClientError

        # Handle ClientError (most common AWS service error)
        if isinstance(error, ClientError):
            error_code = error.response.get("Error", {}).get("Code", "Unknown")
            error_message = error.response.get("Error", {}).get("Message", str(error))

            match error_code:
                case "ThrottlingException":
                    return error_type(
                        error_code=ErrorCode.TOO_MANY_REQUESTS,
                        message=f"Request rate limit exceeded for Bedrock model '{model}'. "
                        "Please slow down your requests or try again later.",
                        data={
                            "model": model,
                            "error_code": error_code,
                            "technical_error_message": error_message,
                        },
                    )
                case "AccessDeniedException":
                    return error_type(
                        error_code=ErrorCode.FORBIDDEN,
                        message=f"Access denied for Bedrock model '{model}'. Please check "
                        "your permissions and ensure the model is accessible in your region.",
                        data={
                            "model": model,
                            "region": self._parameters.region_name,
                            "technical_error_message": error_message,
                        },
                    )
                case "ValidationException":
                    return error_type(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=f"Something went wrong while sending the request to Bedrock model "
                        f"'{model}', please try again or contact support.",
                        data={
                            "model": model,
                            "error_code": error_code,
                            "technical_error_message": error_message,
                        },
                    )
                case "ResourceNotFoundException":
                    return error_type(
                        error_code=ErrorCode.NOT_FOUND,
                        message=f"Bedrock model '{model}' not found. Please verify the model ID "
                        "and ensure it's available in your region.",
                        data={
                            "model": model,
                            "region": self._parameters.region_name,
                            "technical_error_message": error_message,
                        },
                    )
                case "ServiceQuotaExceededException":
                    return error_type(
                        error_code=ErrorCode.TOO_MANY_REQUESTS,
                        message=f"Service quota exceeded for Bedrock model '{model}'. "
                        "Please request a quota increase or try a different model.",
                        data={
                            "model": model,
                            "error_code": error_code,
                            "technical_error_message": error_message,
                        },
                    )
                case "ModelTimeoutException":
                    return error_type(
                        error_code=ErrorCode.UNEXPECTED,
                        message=f"Request to Bedrock model '{model}' timed out. Please try again.",
                        data={
                            "model": model,
                            "error_code": error_code,
                            "technical_error_message": error_message,
                        },
                    )
                case "InternalServerException":
                    return error_type(
                        error_code=ErrorCode.UNEXPECTED,
                        message="Bedrock service encountered an internal error. Please "
                        "try again later or contact support.",
                        data={
                            "model": model,
                            "error_code": error_code,
                            "technical_error_message": error_message,
                        },
                    )
                case "ServiceUnavailableException":
                    return error_type(
                        error_code=ErrorCode.UNEXPECTED,
                        message="Bedrock service is temporarily unavailable. "
                        "Please try again later.",
                        data={
                            "model": model,
                            "error_code": error_code,
                            "technical_error_message": error_message,
                        },
                    )
                case _:
                    # Handle any other ClientError codes
                    return error_type(
                        error_code=ErrorCode.UNEXPECTED,
                        message=f"Something went wrong while sending the request to Bedrock model "
                        f"'{model}', please try again or contact support.",
                        data={
                            "model": model,
                            "error_code": error_code,
                            "technical_error_message": error_message,
                        },
                    )

        # Handle other botocore exceptions
        from botocore.exceptions import (
            BotoCoreError,
            EndpointConnectionError,
            NoCredentialsError,
            ReadTimeoutError,
        )
        from botocore.exceptions import (
            ConnectionError as BotoConnectionError,
        )

        match error:
            case NoCredentialsError():
                return error_type(
                    error_code=ErrorCode.UNAUTHORIZED,
                    message="No AWS credentials found. Please configure your AWS credentials.",
                    data={"model": model},
                )
            case EndpointConnectionError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Failed to connect to Bedrock service. Please check your "
                    "network connection and region configuration.",
                    data={"model": model, "region": self._parameters.region_name},
                )
            case ReadTimeoutError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=f"Request to Bedrock model '{model}' timed out. Please try again.",
                    data={"model": model},
                )
            case BotoConnectionError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Network connection error occurred while connecting to Bedrock. "
                    "Please check your network connection.",
                    data={"model": model},
                )
            case BotoCoreError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=f"Something went wrong while sending the request to Bedrock model "
                    f"'{model}', please try again or contact support.",
                    data={"model": model},
                )
            case _:
                # For any other unexpected errors, re-raise them
                raise error

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
        from types_boto3_bedrock_runtime.type_defs import ConverseRequestTypeDef

        model_id = BedrockModelMap.model_aliases[model]
        request = cast(ConverseRequestTypeDef, prompt.as_platform_request(model_id))

        try:
            response = self._bedrock_runtime_client.converse(**request)
            return self.parsers.parse_response(response)
        except Exception as e:
            raise self._handle_bedrock_error(e, model, PlatformHTTPError) from e

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
        from types_boto3_bedrock_runtime.type_defs import ConverseStreamRequestTypeDef

        model_id = BedrockModelMap.model_aliases[model]
        request = cast(
            ConverseStreamRequestTypeDef,
            prompt.as_platform_request(model_id, stream=True),
        )

        try:
            response = self._bedrock_runtime_client.converse_stream(**request)
        except Exception as e:
            raise self._handle_bedrock_error(e, model, StreamingError) from e

        # Initialize message state
        message: dict[str, Any] = {}
        last_message: dict[str, Any] = {}

        # Process each event through the parser to get deltas
        for event in response["stream"]:
            async for delta in self._parsers.parse_stream_event(
                event,  # type: ignore
                response,
                message,
                last_message,
            ):
                yield delta

            # Update last message state after processing each event
            last_message = deepcopy(message)

        final_event = self._generate_platform_metadata()
        if "metadata" not in message:
            message["metadata"] = {}
        message["metadata"].update(final_event)
        message["raw_response"] = {
            **response,
            "stream": None,
        }

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
        model_id = BedrockModelMap.model_aliases[model]

        try:
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
        except ValueError:
            # Re-raise ValueError for unsupported models without modification
            raise
        except Exception as e:
            raise self._handle_bedrock_error(e, model, PlatformHTTPError) from e

    async def count_tokens(
        self,
        prompt: BedrockPrompt,
        model: str,
    ) -> int:
        """Count the tokens in a prompt.

        Args:
            prompt: The prompt to count the tokens of.
            model: The model to use to count the tokens.

        Returns:
            The number of tokens in the prompt.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """
        raise NotImplementedError("count_tokens is not yet implemented for Bedrock")


PlatformClient.register_platform_client("bedrock", BedrockClient)
