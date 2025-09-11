import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, ParamSpec, TypeVar

import aiobotocore.session
from aiobotocore.config import AioConfig
from botocore.exceptions import ClientError

from agent_platform.core.delta import GenericDelta, compute_generic_deltas
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
    from agent_platform.core.kernel import Kernel

log = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class BedrockClient(
    PlatformClient[
        BedrockConverters,
        BedrockParsers,
        BedrockPlatformParameters,
        BedrockPrompt,
    ]
):
    NAME: ClassVar[str] = "bedrock"
    configs: ClassVar[type[PlatformConfigs]] = BedrockPlatformConfigs
    model_map: ClassVar[type[PlatformModelMap]] = BedrockModelMap

    # ------------------------------------------------------------------#
    # Construction
    # ------------------------------------------------------------------#

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: BedrockPlatformParameters | None = None,
        **overrides: Any,
    ):
        super().__init__(kernel=kernel, parameters=parameters, **overrides)

        # 1. Build one global aiobotocore session
        self._session = aiobotocore.session.get_session()

        # user-supplied botocore.Config is converted to its async twin
        botocore_cfg = self._parameters.config_params or {}
        self._config = AioConfig(
            retries={
                "mode": "standard",  # or 'adaptive'
                "max_attempts": 4,  # initial call + 3 retries
            },
            **botocore_cfg,  # keeps any user-supplied overrides
        )

        self._bedrock_client: Any | None = None

    async def _client(self):
        """
        Lazily create a single connection-pooled runtime client.
        """
        if self._bedrock_client is None:
            self._bedrock_client = await self._session.create_client(
                "bedrock-runtime",
                config=self._config,
                **self._parameters.aws_client_params(),
            ).__aenter__()
        return self._bedrock_client

    async def aclose(self) -> None:
        """Close the underlying aiobotocore client if open."""
        if self._bedrock_client is not None:
            try:
                # Symmetric to explicit __aenter__ above
                await self._bedrock_client.__aexit__(None, None, None)
            finally:
                self._bedrock_client = None

    # ------------------------------------------------------------------#
    # Public API
    # ------------------------------------------------------------------#

    async def generate_response(
        self,
        prompt: BedrockPrompt,
        model: str,
    ) -> ResponseMessage:
        model_id = BedrockModelMap.model_aliases[model]

        try:
            # Bedrock's `converse` is POST; returns JSON body.
            # Rely on botocore/aiobotocore built-in retry policy (AioConfig.retries)
            client = await self._client()
            response = await client.converse(
                **prompt.as_platform_request(model_id, stream=False),
            )
            return self._parsers.parse_response(response)
        except Exception as exc:
            # Surface as a PlatformHTTPError with Bedrock-specific mapping
            raise self._handle_bedrock_error(exc, model, PlatformHTTPError) from exc

    async def generate_stream_response(
        self,
        prompt: BedrockPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        model_id = BedrockModelMap.model_aliases[model]

        try:
            # Returns an async iterator over SSE / HTTP2 frames
            # Rely on botocore/aiobotocore built-in retry policy (AioConfig.retries)
            client = await self._client()
            response = await client.converse_stream(
                **prompt.as_platform_request(model_id, stream=True),
            )
        except Exception as exc:
            # Surface as a StreamingError with Bedrock-specific mapping
            raise self._handle_bedrock_error(exc, model, StreamingError) from exc

        # ------------------------------------------------------------ #
        # Streaming loop: parse each partial event and yield deltas
        # ------------------------------------------------------------ #
        message_state: dict[str, Any] = {}
        last_msg_state: dict[str, Any] = {}

        try:
            async for event in response["stream"]:
                async for delta in self._parsers.parse_stream_event(
                    event, response, message_state, last_msg_state
                ):
                    yield delta
                last_msg_state = deepcopy(message_state)
        except Exception as exc:
            raise self._handle_bedrock_error(exc, model, StreamingError) from exc

        # Attach final metadata delta
        final_event = self._generate_platform_metadata()
        message_state.setdefault("metadata", {}).update(final_event)
        message_state["raw_response"] = {**response, "stream": None}

        for delta in compute_generic_deltas(last_msg_state, message_state):
            yield delta

    # ------------------------------------------------------------------#
    # Embeddings (batch capable)
    # ------------------------------------------------------------------#

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings and translate any Bedrock/HTTP errors.

        This helper wraps the low-level Bedrock call so that *any* boto-core
        or client exceptions are normalised via ``_handle_bedrock_error`` into
        a ``PlatformHTTPError`` --- mirroring the behaviour of the chat-based
        helpers. Non-Bedrock errors such as a missing model (``ValueError``)
        continue to propagate unchanged to satisfy test expectations.
        """

        model_id = BedrockModelMap.model_aliases[model]

        try:
            if model_id.startswith("amazon.titan-embed-text"):
                # Titan does *not* batch today

                async def titan_single(txt: str):
                    body = {"inputText": txt}
                    client = await self._client()
                    response = await client.invoke_model(
                        modelId=model_id,
                        body=json.dumps(body),
                    )
                    # The response body is a stream; read() returns the raw JSON bytes
                    data = json.loads(response["body"].read())
                    return data["embedding"], data.get("inputTextTokenCount", 0)

                results = await asyncio.gather(*(titan_single(t) for t in texts))
                embeddings, token_counts = zip(*results, strict=True)
                return {
                    "embeddings": list(embeddings),
                    "model": model,
                    "usage": {"total_tokens": sum(token_counts)},
                }

            if model_id.startswith("cohere.embed"):
                request = {
                    "texts": texts,
                    "input_type": "search_document",
                    "embedding_types": ["float"],
                }
                client = await self._client()
                response = await client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(request),
                )
                # The response body is a stream; read() returns the raw JSON bytes
                data = json.loads(response["body"].read())
                return {
                    "embeddings": data["embeddings"],
                    "model": model,
                    "usage": {"total_tokens": data.get("token_count", 0)},
                }

            # Maintain backwards-compatibility with earlier error message expectation
            raise ValueError(f"{model_id!r} is not a supported embedding model")
        except ValueError:
            # Not a Bedrock error, so propagate it unchanged so calling code can
            # decide how to handle unsupported models.
            raise
        except Exception as exc:
            # Translate all other exceptions via the shared Bedrock handler.
            raise self._handle_bedrock_error(exc, model, PlatformHTTPError) from exc

    def _init_converters(self, kernel: "Kernel | None" = None) -> BedrockConverters:
        converters = BedrockConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: BedrockPlatformParameters | None = None,
        **kwargs: Any,
    ) -> BedrockPlatformParameters:
        if parameters is None:
            parameters = BedrockPlatformParameters(**kwargs)
        elif kwargs:
            parameters = parameters.model_copy(update=kwargs)
        return parameters

    def _init_parsers(self) -> BedrockParsers:
        return BedrockParsers()

    # ------------------------------------------------------------------#
    # Error handling
    # ------------------------------------------------------------------#

    def _handle_bedrock_error(  # noqa: PLR0911
        self,
        error: Exception,
        model: str,
        err_cls: type[PlatformError] = PlatformError,
    ) -> PlatformError:
        from botocore.exceptions import (
            BotoCoreError,
            EndpointConnectionError,
            NoCredentialsError,
            ReadTimeoutError,
        )
        from botocore.exceptions import (
            ConnectionError as BotoConnectionError,
        )

        if isinstance(error, ClientError):
            code = error.response.get("Error", {}).get("Code", "Unknown")
            message = error.response.get("Error", {}).get("Message", str(error))

            mapping: dict[str, tuple[ErrorCode, str]] = {
                "ThrottlingException": (
                    ErrorCode.TOO_MANY_REQUESTS,
                    "Request rate limit exceeded.",
                ),
                "AccessDeniedException": (
                    ErrorCode.FORBIDDEN,
                    "Access denied.",
                ),
                "ValidationException": (
                    ErrorCode.BAD_REQUEST,
                    "Something went wrong while validating your request.",
                ),
                "ResourceNotFoundException": (
                    ErrorCode.NOT_FOUND,
                    "Model not found.",
                ),
                "ServiceQuotaExceededException": (
                    ErrorCode.TOO_MANY_REQUESTS,
                    "Service quota exceeded.",
                ),
                "ModelTimeoutException": (
                    ErrorCode.UNEXPECTED,
                    "Bedrock model request timed out.",
                ),
                "InternalServerException": (
                    ErrorCode.UNEXPECTED,
                    "Bedrock internal error.",
                ),
                "ServiceUnavailableException": (
                    ErrorCode.UNEXPECTED,
                    "Bedrock service is temporarily unavailable.",
                ),
            }

            err_code, user_msg = mapping.get(code, (ErrorCode.UNEXPECTED, "Something went wrong."))

            data: dict[str, Any] = {
                "technical_error_message": message,
                "model": model,
                "error_code": code,
            }

            # Region info for AccessDenied to satisfy tests
            if code == "AccessDeniedException":
                data["region"] = self._parameters.region_name
            if "Input is too long" in message:
                # Handle context length exceeded better
                return err_cls(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        f"The request to model '{model}' was rejected because it "
                        f"exceeded the context length limit. Please try again with a "
                        f"shorter request.\n\nDetails: {message}"
                    ),
                    data={"model": model, "error_message": message},
                )

            return err_cls(
                error_code=err_code,
                message=f"{user_msg} (model='{model}', code='{code}')",
                data=data,
            )

        match error:
            case NoCredentialsError():
                return err_cls(
                    error_code=ErrorCode.UNAUTHORIZED,
                    message="No AWS credentials found.",
                    data={"model": model},
                )
            case EndpointConnectionError():
                return err_cls(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Failed to connect to Bedrock endpoint.",
                    data={"region": self._parameters.region_name, "model": model},
                )
            case ReadTimeoutError():
                return err_cls(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Bedrock request timed out.",
                    data={"model": model},
                )
            case BotoConnectionError():
                return err_cls(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Network connection error.",
                    data={"model": model},
                )
            case BotoCoreError():
                return err_cls(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Something went wrong.",
                    data={"model": model},
                )
            case _:
                raise error


PlatformClient.register_platform_client("bedrock", BedrockClient)
