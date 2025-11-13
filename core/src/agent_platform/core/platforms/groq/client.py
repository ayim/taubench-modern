"""Groq platform client built on the OpenAI-compatible Responses API."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.errors import ErrorCode
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.configs import (
    resolve_generic_model_id_to_platform_specific_model_id,
)
from agent_platform.core.platforms.groq.converters import GroqConverters
from agent_platform.core.platforms.groq.parameters import GroqPlatformParameters
from agent_platform.core.platforms.groq.parsers import GroqParsers
from agent_platform.core.platforms.groq.prompts import GroqPrompt
from agent_platform.core.platforms.openai.utils import (
    build_llm_async_http_client,
    log_token_usage,
)
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)
T = TypeVar("T")


class GroqClient(
    PlatformClient[
        GroqConverters,
        GroqParsers,
        GroqPlatformParameters,
        GroqPrompt,
    ],
):
    """A client for the Groq platform using the Responses API."""

    NAME: ClassVar[str] = "groq"

    _RETRYABLE_STATUS: ClassVar[set[int]] = {408, 409, 429}
    _MAX_RETRY_ATTEMPTS: ClassVar[int] = 3
    _BACKOFF_BASE_S: ClassVar[float] = 0.5
    _BACKOFF_MAX_S: ClassVar[float] = 8.0
    _PROVIDER_NORMALIZATION: ClassVar[dict[str, str]] = {
        "meta-llama": "meta",
    }

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: GroqPlatformParameters | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(kernel=kernel, parameters=parameters, **kwargs)
        self._groq_client = self._build_async_client()
        self._test_mock_client: Any | None = None

    def _init_converters(self, kernel: "Kernel | None" = None) -> GroqConverters:
        converters = GroqConverters()
        if kernel is not None:
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

    def _build_async_client(self) -> "AsyncOpenAI":
        from openai import AsyncOpenAI

        http_client = build_llm_async_http_client()

        api_key_secret = self._parameters.groq_api_key
        if api_key_secret is None:
            raise ValueError("Groq API key is required")

        if hasattr(api_key_secret, "get_secret_value"):
            api_key = api_key_secret.get_secret_value()
        else:
            api_key = str(api_key_secret)

        return AsyncOpenAI(
            api_key=api_key,
            base_url=self._parameters.base_url,
            http_client=http_client,
            default_headers=None,
            organization=None,
        )

    def _validate_request(self, request: dict[str, Any]) -> None:
        """Validate request payload for unsupported Groq features."""
        unsupported_parameters = [
            field
            for field in ("logprobs", "logit_bias", "top_logprobs")
            if field in request and request[field] is not None
        ]
        if unsupported_parameters:
            joined = ", ".join(sorted(unsupported_parameters))
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=(
                    f"Groq Responses API does not support the following parameters: {joined}. "
                    "Remove them from the request."
                ),
                data={"unsupported_parameters": unsupported_parameters},
            )

        n_value = request.get("n")
        if n_value is not None and n_value != 1:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=(f"Groq Responses API currently supports only n=1. Received n={n_value}."),
                data={"n": n_value},
            )

    async def _call_with_retries(
        self,
        call: Callable[[], Awaitable[T]],
        model: str,
        *,
        stream: bool = False,
        context: str = "request",
    ) -> T:
        """Run an async SDK call with retries using a shared Tenacity decorator."""
        from agent_platform.core.platforms.retry import build_openai_retry_decorator

        retry_deco = build_openai_retry_decorator(
            logger=logger,
            provider_name="Groq",
            context=context,
            max_attempts=self._MAX_RETRY_ATTEMPTS,
            base_backoff_s=self._BACKOFF_BASE_S,
            max_backoff_s=self._BACKOFF_MAX_S,
            retryable_status=self._RETRYABLE_STATUS,
        )

        @retry_deco
        async def _inner() -> T:
            return await call()

        try:
            return await _inner()
        except Exception as exc:  # pragma: no cover - safety net
            error_type = StreamingError if stream else PlatformHTTPError
            raise self._handle_openai_error(exc, model, error_type) from exc

    def _handle_openai_error(  # noqa: C901, PLR0911, PLR0912
        self, error: Exception, model: str, error_type: type[PlatformError] = PlatformError
    ) -> PlatformError:
        """Handle OpenAI SDK errors surfaced via Groq and map them to PlatformErrors."""
        from openai import (
            APIConnectionError,
            APIError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            InternalServerError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
            UnprocessableEntityError,
        )

        match error:
            case RateLimitError():
                return error_type(
                    error_code=ErrorCode.TOO_MANY_REQUESTS,
                    message=(
                        "Groq API usage limit reached. Please increase the limit for "
                        f"'{model}' or switch to an available model."
                    ),
                    data={"model": model},
                )
            case AuthenticationError():
                return error_type(
                    error_code=ErrorCode.UNAUTHORIZED,
                    message="Authentication failed for Groq. Please check your API key.",
                    data={"model": model},
                )
            case PermissionDeniedError():
                return error_type(
                    error_code=ErrorCode.FORBIDDEN,
                    message=(
                        f"Access denied for Groq model '{model}'. Please verify your permissions."
                    ),
                    data={"model": model},
                )
            case BadRequestError():
                if getattr(error, "code", "") == "context_length_exceeded":
                    return error_type(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=(
                            f"Groq model '{model}' request exceeded the context length limit. "
                            f"Details: {getattr(error, 'message', '')}"
                        ),
                        data={"model": model, "error_message": getattr(error, "message", "")},
                    )
                return error_type(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        "Something went wrong while sending the request to Groq. "
                        "Please try again or contact support."
                    ),
                    data={"model": model},
                )
            case NotFoundError():
                return error_type(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Groq model '{model}' not found. Please verify the model name.",
                    data={"model": model},
                )
            case UnprocessableEntityError():
                return error_type(
                    error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                    message=(
                        "Groq could not process the request. "
                        "Please verify the payload and try again."
                    ),
                    data={"model": model},
                )
            case APITimeoutError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=f"Request to Groq model '{model}' timed out. Please try again.",
                    data={"model": model},
                )
            case APIConnectionError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=(
                        "Failed to connect to Groq service. Please check your network connection."
                    ),
                    data={"model": model},
                )
            case InternalServerError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Groq service encountered an internal error. Please try again later.",
                    data={"model": model},
                )
            case APIError() as api_error:
                error_message = getattr(api_error, "message", "") or str(api_error)
                if "tool call validation failed" in error_message.lower():
                    return error_type(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=(
                            f"Groq rejected a tool invocation for model '{model}'. "
                            "Please verify the tool schema and arguments."
                        ),
                        data={"model": model, "error_message": error_message},
                    )
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=(
                        f"An unexpected error occurred with Groq model '{model}'. "
                        "Please try again or contact support."
                    ),
                    data={"model": model, "error_message": error_message},
                )
            case _:
                raise error

    async def generate_response(
        self,
        prompt: GroqPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a response from the Groq platform."""
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
        request = prompt.as_platform_request(model_id)
        self._validate_request(request)

        response = await self._call_with_retries(
            lambda: self._groq_client.responses.create(**request),
            model,
            stream=False,
            context="groq.responses.create",
        )
        return self._parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: GroqPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the Groq platform."""
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
        request = prompt.as_platform_request(model_id, stream=True)
        self._validate_request(request)
        logger.info("Streaming with Groq model: %s", model_id)

        message: dict[str, Any] = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message: dict[str, Any] = {}

        response = await self._call_with_retries(
            lambda: self._groq_client.responses.create(**request),
            model,
            stream=True,
            context="groq.responses.create(stream)",
        )
        async for event in response:
            async for delta in self._parsers.parse_stream_event(
                event,
                message,
                last_message,
            ):
                yield delta
            last_message = deepcopy(message)

        final_event = self._generate_platform_metadata()
        message.setdefault("metadata", {}).update(final_event)

        log_token_usage(logger, message.get("usage", {}))

        request_id = message.get("additional_response_fields", {}).get("id", "unknown")
        message["raw_response"] = {
            "ResponseMetadata": {
                "RequestId": request_id,
                "HTTPStatusCode": 200,
                "RetryAttempts": 0,
            },
            "stream": None,
        }

        for delta in compute_generic_deltas(last_message, message):
            yield delta

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        raise PlatformError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Groq platform does not support embedding models.",
            data={"model": model},
        )

    async def get_available_models(self) -> dict[str, list[str]]:
        model_list = await self._groq_client.models.list()
        models_by_provider: dict[str, list[str]] = {}

        for model in getattr(model_list, "data", []):
            model_id = getattr(model, "id", None)
            if not isinstance(model_id, str):
                continue

            provider_slug, _, _ = model_id.partition("/")
            provider = self._PROVIDER_NORMALIZATION.get(provider_slug, provider_slug)
            models_by_provider.setdefault(provider, []).append(model_id)

        return models_by_provider


PlatformClient.register_platform_client("groq", GroqClient)
