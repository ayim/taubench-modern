import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, ParamSpec, TypeVar

from agent_platform.core.delta import GenericDelta, compute_generic_deltas
from agent_platform.core.errors import ErrorCode
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.bedrock.converters import BedrockConverters
from agent_platform.core.platforms.bedrock.parameters import (
    BedrockPlatformParameters,
)
from agent_platform.core.platforms.bedrock.parsers import BedrockParsers
from agent_platform.core.platforms.bedrock.prompts import BedrockPrompt
from agent_platform.core.platforms.configs import (
    resolve_generic_model_id_to_platform_specific_model_id,
)
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
    _GLOBAL_MODEL_ARN_CACHE: ClassVar[dict[str, str]] = {}
    _GLOBAL_PROFILE_ARN_CACHE: ClassVar[dict[str, str]] = {}
    _GLOBAL_AVAILABLE_MODELS_CACHE: ClassVar[dict[str, list[str]]] = {}
    _GLOBAL_AVAILABLE_MODELS_LOCK: ClassVar[asyncio.Lock] = asyncio.Lock()

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
        import aiobotocore.session
        from aiobotocore.config import AioConfig

        super().__init__(kernel=kernel, parameters=parameters, **overrides)

        # 1. Build one global aiobotocore session
        self._session = aiobotocore.session.get_session()
        # We don't need automatic metadata generation
        # (Extra network requests and exceptions in debug logs when
        # metadata is enabled...)
        self._session.set_config_variable("metadata_disabled", True)

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
        self._bedrock_control_plane_client: Any | None = None
        # Warm local caches from any previously discovered ARNs so new
        # clients do not repeat the control-plane discovery.
        self._model_arn_cache: dict[str, str] = dict(self._GLOBAL_MODEL_ARN_CACHE)
        self._profile_arn_cache: dict[str, str] = dict(self._GLOBAL_PROFILE_ARN_CACHE)
        self._available_models_cache: dict[str, list[str]] = deepcopy(
            self._GLOBAL_AVAILABLE_MODELS_CACHE,
        )

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

    async def _control_plane_client(self):
        if self._bedrock_control_plane_client is None:
            self._bedrock_control_plane_client = await self._session.create_client(
                "bedrock",
                config=self._config,
                **self._parameters.aws_client_params(),
            ).__aenter__()
        return self._bedrock_control_plane_client

    async def _get_model_arn_from_local_model_id(self, model_id: str) -> str:
        # So bedrock is complex... we need to list _inference profiles_ and
        # try and find a matching one... can fall back to the foundation model
        # listing (but that likely wont work, unless on-demand is enabled)
        if model_id in self._model_arn_cache:
            return self._model_arn_cache[model_id]
        if model_id in self._GLOBAL_MODEL_ARN_CACHE:
            arn = self._GLOBAL_MODEL_ARN_CACHE[model_id]
            self._model_arn_cache[model_id] = arn
            return arn

        def _find_matching_profile_from_cache(model_id: str) -> str | None:
            for cache in (self._profile_arn_cache, self._GLOBAL_PROFILE_ARN_CACHE):
                for profile_id, profile_arn in cache.items():
                    if profile_id.endswith(model_id):
                        # Synchronise both caches when we hit on a global entry.
                        self._profile_arn_cache[profile_id] = profile_arn
                        self._GLOBAL_PROFILE_ARN_CACHE[profile_id] = profile_arn
                        self._model_arn_cache[model_id] = profile_arn
                        self._GLOBAL_MODEL_ARN_CACHE[model_id] = profile_arn
                        return profile_arn
            return None

        if profile_arn := _find_matching_profile_from_cache(model_id):
            return profile_arn

        # First, try and find a matching profile
        client = await self._control_plane_client()
        response = await client.list_inference_profiles()
        for profile in response.get("inferenceProfileSummaries", []):
            profile_id = profile["inferenceProfileId"]
            profile_arn = profile["inferenceProfileArn"]
            self._profile_arn_cache[profile_id] = profile_arn
            self._GLOBAL_PROFILE_ARN_CACHE[profile_id] = profile_arn

        if profile_arn := _find_matching_profile_from_cache(model_id):
            return profile_arn

        log.warning(f"No inference profile found for model '{model_id}'")
        log.warning("Falling back to foundation model listing, this may not work")

        # If no profile found, fall back to foundation model
        if model_id in self._model_arn_cache:
            return self._model_arn_cache[model_id]

        response = await client.list_foundation_models()
        for model in response.get("modelSummaries", []):
            model_key = model["modelId"]
            model_arn = model["modelArn"]
            self._model_arn_cache[model_key] = model_arn
            self._GLOBAL_MODEL_ARN_CACHE[model_key] = model_arn

        if model_id not in self._model_arn_cache:
            raise ValueError(
                f"Neither inference profile nor foundation model ARN found for '{model_id}'",
            )

        arn = self._model_arn_cache[model_id]
        self._GLOBAL_MODEL_ARN_CACHE[model_id] = arn
        return arn

    # ------------------------------------------------------------------#
    # Public API
    # ------------------------------------------------------------------#

    async def generate_response(
        self,
        prompt: BedrockPrompt,
        model: str,
    ) -> ResponseMessage:
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
        # Need to get the model_arn and use that
        model_arn = await self._get_model_arn_from_local_model_id(model_id)

        try:
            # Bedrock's `converse` is POST; returns JSON body.
            client = await self._client()
            response = await client.converse(
                **prompt.as_platform_request(model_arn, stream=False),
            )
            return self._parsers.parse_response(response)
        except Exception as exc:
            raise self._handle_bedrock_error(exc, model, PlatformHTTPError) from exc

    async def generate_stream_response(
        self,
        prompt: BedrockPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
        # Need to get the model_arn and use that
        model_arn = await self._get_model_arn_from_local_model_id(model_id)

        try:
            # Returns an async iterator over SSE / HTTP2 frames
            client = await self._client()
            response = await client.converse_stream(
                **prompt.as_platform_request(model_arn, stream=True),
            )
        except Exception as exc:
            raise self._handle_bedrock_error(exc, model, StreamingError) from exc

        # ------------------------------------------------------------ #
        # Streaming loop: parse each partial event and yield deltas
        # ------------------------------------------------------------ #
        message_state: dict[str, Any] = {}
        last_msg_state: dict[str, Any] = {}

        try:
            async for event in response["stream"]:
                async for delta in self._parsers.parse_stream_event(event, response, message_state, last_msg_state):
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

        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
        # Need to get the model_arn and use that
        model_arn = await self._get_model_arn_from_local_model_id(model_id)

        try:
            if model_id.startswith("amazon.titan-embed-text"):
                # Titan does *not* batch today

                async def titan_single(txt: str):
                    body = {"inputText": txt}
                    client = await self._client()
                    response = await client.invoke_model(
                        modelId=model_arn,
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
                    modelId=model_arn,
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

    async def get_available_models(self) -> dict[str, list[str]]:
        if self._available_models_cache:
            return deepcopy(self._available_models_cache)

        if self._GLOBAL_AVAILABLE_MODELS_CACHE:
            self._available_models_cache = deepcopy(self._GLOBAL_AVAILABLE_MODELS_CACHE)
            return deepcopy(self._available_models_cache)

        async with self._GLOBAL_AVAILABLE_MODELS_LOCK:
            if self._GLOBAL_AVAILABLE_MODELS_CACHE:
                self._available_models_cache = deepcopy(self._GLOBAL_AVAILABLE_MODELS_CACHE)
                return deepcopy(self._available_models_cache)

            client = await self._control_plane_client()
            response = await client.list_foundation_models()
            result: dict[str, list[str]] = {}
            for model in response.get("modelSummaries", []):
                provider = model["providerName"].lower()
                result.setdefault(provider, []).append(model["modelId"])

            # Refresh the shared cache in-place so existing references stay valid.
            self._GLOBAL_AVAILABLE_MODELS_CACHE.clear()
            for provider, models in result.items():
                self._GLOBAL_AVAILABLE_MODELS_CACHE[provider] = list(models)

            self._available_models_cache = deepcopy(self._GLOBAL_AVAILABLE_MODELS_CACHE)
            return deepcopy(self._available_models_cache)

    # ------------------------------------------------------------------#
    # Error handling
    # ------------------------------------------------------------------#

    def _handle_bedrock_error(
        self,
        error: Exception,
        model: str,
        err_cls: type[PlatformError] = PlatformError,
    ) -> PlatformError:
        from botocore.exceptions import (
            BotoCoreError,
            ClientError,
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
