import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from agent_platform.core.errors import ErrorCode
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.litellm.converters import LiteLLMConverters
from agent_platform.core.platforms.litellm.parameters import LiteLLMPlatformParameters
from agent_platform.core.platforms.litellm.parsers import LiteLLMParsers
from agent_platform.core.platforms.openai.client import OpenAIClient
from agent_platform.core.platforms.openai.utils import build_llm_async_http_client

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)
T = TypeVar("T")


class LiteLLMClient(OpenAIClient):
    """Client for interacting with the OpenRouter platform."""

    NAME: ClassVar[str] = "litellm"

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: LiteLLMPlatformParameters | None = None,
        **kwargs: Any,
    ):
        self._litellm_parameters = self._init_parameters(parameters)
        self._converters = self._init_converters(kernel)
        self._parsers = self._init_parsers()
        self._openai_client = self._init_client(self._litellm_parameters)

    def _init_client(self, parameters: LiteLLMPlatformParameters) -> "AsyncOpenAI":
        from openai import AsyncOpenAI

        if parameters.litellm_api_key is None:
            raise ValueError("LiteLLM API key is required")

        http = build_llm_async_http_client()
        default_headers: dict[str, str] = {}

        return AsyncOpenAI(
            api_key=parameters.litellm_api_key.get_secret_value(),
            base_url=parameters.litellm_base_url,
            http_client=http,
            default_headers=default_headers or None,
        )

    def _init_parameters(
        self,
        parameters: LiteLLMPlatformParameters | None = None,
        **kwargs: Any,
    ) -> LiteLLMPlatformParameters:
        if parameters is None:
            raise ValueError("Parameters are required for LiteLLM client")
        return parameters

    def _init_converters(self, kernel: "Kernel | None" = None) -> LiteLLMConverters:
        converters = LiteLLMConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parsers(self) -> LiteLLMParsers:
        return LiteLLMParsers()

    @property
    def parameters(self) -> LiteLLMPlatformParameters:
        return self._litellm_parameters

    async def _call_with_retries(
        self,
        call: Callable[[], Awaitable[T]],
        model: str,
        *,
        stream: bool = False,
        context: str = "request",
    ) -> T:
        from agent_platform.core.platforms.retry import build_openai_retry_decorator

        retry_deco = build_openai_retry_decorator(
            logger=logger,
            provider_name="LiteLLM",
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
        except Exception as e:
            error_type = StreamingError if stream else PlatformHTTPError
            raise self._handle_litellm_error(e, model, error_type) from e

    def _handle_litellm_error(
        self, error: Exception, model: str, error_type: type[PlatformError] = PlatformError
    ) -> PlatformError:
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
                        "LLM usage limit reached. Please increase the limit for "
                        f"'{model}' or switch to an available model on LiteLLM."
                    ),
                    data={"model": model},
                )
            case AuthenticationError():
                return error_type(
                    error_code=ErrorCode.UNAUTHORIZED,
                    message=("Authentication failed for LiteLLM. Please check your API key and credentials."),
                    data={"model": model},
                )
            case PermissionDeniedError():
                return error_type(
                    error_code=ErrorCode.FORBIDDEN,
                    message=(f"Access denied for LiteLLM model '{model}'. Please check your permissions."),
                    data={"model": model},
                )
            case BadRequestError():
                if getattr(error, "code", None) == "context_length_exceeded":
                    return error_type(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=(
                            f"The request to model '{model}' was rejected because it exceeded the "
                            "context length limit. "
                            "Please try again with a shorter request.\n\n"
                            f"Details: {error.message}"
                        ),
                        data={"model": model, "error_message": error.message},
                    )
                if getattr(error, "code", None) == "unsupported_value":
                    logger.info("Error object: %s", error)
                    return error_type(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=(
                            "Your organization must be verified to stream this model. "
                            "Please go to: https://openai.com/settings and ensure your "
                            "organization is verified. "
                            "If you just verified, it can take up to 15 minutes for access to "
                            "propagate."
                        ),
                        data={"model": model},
                    )
                return error_type(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        f"The request to the LiteLLM model '{model}' failed."
                        f" Details: {getattr(error, 'message', str(error))}"
                    ),
                    data={"model": model, "error_message": getattr(error, "message", str(error))},
                )
            case APIConnectionError() | APITimeoutError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=(
                        "Unable to connect to the LiteLLM service. Please check your network connection and try again."
                    ),
                    data={"model": model},
                )
            case InternalServerError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=("LiteLLM returned an internal server error while processing the request."),
                    data={"model": model},
                )
            case NotFoundError():
                return error_type(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"The requested LiteLLM model '{model}' was not found.",
                    data={"model": model},
                )
            case UnprocessableEntityError():
                return error_type(
                    error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                    message=(
                        f"The request to LiteLLM model '{model}' could not be processed. "
                        f"Details: {getattr(error, 'message', str(error))}"
                    ),
                    data={"model": model, "error_message": getattr(error, "message", str(error))},
                )
            case APIError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=("LiteLLM encountered an internal error while processing the request."),
                    data={"model": model},
                )
            case _:
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=(
                        "An unexpected error occurred while communicating with LiteLLM. "
                        f"Details: {getattr(error, 'message', str(error))}"
                    ),
                    data={"model": model, "error": getattr(error, "message", str(error))},
                )

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        raise NotImplementedError("Embeddings are not supported for the LiteLLM platform.")

    async def get_available_models(self) -> dict[str, list[str]]:
        # This is an "anything goes" platform, so we'll just say whatever
        # we are configured with is available
        return self.parameters.models or {}


PlatformClient.register_platform_client("litellm", LiteLLMClient)
