import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from agent_platform.core.delta import GenericDelta
from agent_platform.core.errors import ErrorCode
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.platforms.azure.converters import AzureOpenAIConverters
from agent_platform.core.platforms.azure.parameters import AzureOpenAIPlatformParameters
from agent_platform.core.platforms.azure.parsers import AzureOpenAIParsers
from agent_platform.core.platforms.azure.prompts import AzureOpenAIPrompt
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.configs import (
    resolve_generic_model_id_to_platform_specific_model_id,
)
from agent_platform.core.platforms.openai.utils import build_llm_async_http_client, log_token_usage
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)
T = TypeVar("T")


class AzureOpenAIClient(
    PlatformClient[
        AzureOpenAIConverters,
        AzureOpenAIParsers,
        AzureOpenAIPlatformParameters,
        AzureOpenAIPrompt,
    ],
):
    """A client for the AzureOpenAI platform."""

    NAME: ClassVar[str] = "azure"

    # ---- Retry knobs (tune as desired) ---------------------------------------
    # NOTE: 5xx errors are retried generically by the predicate in retry.py
    # (any 5xx except 501 and 505). This set is for explicit, non-5xx statuses
    # we also want to retry:
    # - 408 Request Timeout: transient network/server timeout
    # - 409 Conflict: may be returned by Azure during transient deployment/capacity
    #   conflicts or concurrency issues
    # - 429 Too Many Requests: rate limiting; honor Retry-After when present
    _RETRYABLE_STATUS: ClassVar[set[int]] = {408, 409, 429}
    _MAX_RETRY_ATTEMPTS: ClassVar[int] = 3
    _BACKOFF_BASE_S: ClassVar[float] = 0.5
    _BACKOFF_MAX_S: ClassVar[float] = 8.0

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
        self._azure_embeddings_client: AsyncAzureOpenAI | None = None

    @property
    def azure_embeddings_client(self) -> "AsyncAzureOpenAI":
        """Lazily initialize and return the Azure OpenAI embeddings client."""
        if self._azure_embeddings_client is None:
            self._azure_embeddings_client = self._init_embeddings_client(self._parameters)
        return self._azure_embeddings_client

    def _init_client(
        self,
        parameters: AzureOpenAIPlatformParameters,
    ) -> "AsyncOpenAI":
        """Initialize the Azure OpenAI client."""
        from openai import AsyncOpenAI

        # Required parameters check
        if parameters.azure_api_key is None:
            raise ValueError("AzureOpenAI API key is required")

        if parameters.azure_endpoint_url is None or parameters.azure_deployment_name is None:
            raise ValueError(
                "AzureOpenAI endpoint URL and/or deployment name are required",
            )

        # Initialize the client with the API key and endpoint URL
        http = build_llm_async_http_client()
        return AsyncOpenAI(
            api_key=parameters.azure_api_key.get_secret_value(),
            base_url=f"{parameters.azure_endpoint_url}/openai/v1",
            default_query={"api-version": "preview"},
            http_client=http,
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
        http = build_llm_async_http_client()
        return AsyncAzureOpenAI(
            api_key=parameters.azure_api_key.get_secret_value(),
            azure_endpoint=parameters.azure_generated_endpoint_url_embeddings,
            api_version=parameters.azure_api_version,
            http_client=http,
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

        # We build a decorator dynamically here, to share between Azure and OpenAI
        # internally, this decorator uses tenacity for retries (see retry.py)
        retry_deco = build_openai_retry_decorator(
            logger=logger,
            provider_name="Azure OpenAI",
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
            raise self._handle_openai_error(e, model, error_type) from e

    def _handle_openai_error(  # noqa: C901, PLR0911
        self, error: Exception, model: str, error_type: type[PlatformError] = PlatformError
    ) -> PlatformError:
        """Handle OpenAI errors and convert them to PlatformError instances.

        Args:
            error: The OpenAI exception that was raised
            model: The model being used when the error occurred
            error_type: The type of error to return. Defaults to PlatformError.

        Returns:
            PlatformError: The appropriate error for the given OpenAI error
        """
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
                    message=f"LLM usage limit reached. Please increase the limit for '{model}' "
                    f"or switch to an available model.",
                    data={"model": model},
                )
            case AuthenticationError():
                return error_type(
                    error_code=ErrorCode.UNAUTHORIZED,
                    message="Authentication failed for Azure OpenAI. Please check your API "
                    "key and credentials.",
                    data={"model": model, "azure_endpoint": self._parameters.azure_endpoint_url},
                )
            case PermissionDeniedError():
                return error_type(
                    error_code=ErrorCode.FORBIDDEN,
                    message=f"Access denied for Azure OpenAI model '{model}'. Please check "
                    "your permissions.",
                    data={"model": model},
                )
            case BadRequestError():
                # Better error for context length exceeded
                if error.code == "context_length_exceeded":
                    return error_type(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=(
                            f"The request to model '{model}' was rejected because it "
                            f"exceeded the context length limit. Please try again with a "
                            f"shorter request.\n\nDetails: {error.message}"
                        ),
                        data={"model": model, "error_message": error.message},
                    )

                return error_type(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=f"Something went wrong while sending the request to Azure OpenAI model "
                    f"'{model}', please try again or contact support.",
                    data={"model": model},
                )
            case NotFoundError():
                return error_type(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Azure OpenAI model '{model}' or deployment not found. Please "
                    "verify the model name and deployment.",
                    data={"model": model, "deployment": self._parameters.azure_deployment_name},
                )
            case UnprocessableEntityError():
                return error_type(
                    error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                    message=f"Something went wrong while sending the request to Azure OpenAI model "
                    f"'{model}', please try again or contact support.",
                    data={"model": model},
                )
            case APITimeoutError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=f"Request to Azure OpenAI model '{model}' timed out. Please try again.",
                    data={"model": model},
                )
            case APIConnectionError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Failed to connect to Azure OpenAI service. Please check your "
                    "network connection and endpoint.",
                    data={"model": model, "azure_endpoint": self._parameters.azure_endpoint_url},
                )
            case InternalServerError():
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Azure OpenAI service encountered an internal error. Please "
                    "try again later or contact support.",
                    data={"model": model},
                )
            case APIError():
                # Base OpenAI error - catch any other OpenAI-specific errors
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message=f"An unexpected error occurred with Azure OpenAI model '{model}'. "
                    "Please try again or contact support.",
                    data={"model": model},
                )
            case _:
                # For any other unexpected errors, re-raise them
                raise error

    async def generate_response(
        self,
        prompt: AzureOpenAIPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a response from the AzureOpenAI platform."""
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
        request = prompt.as_platform_request(model_id)
        request["model"] = self._parameters.azure_deployment_name

        response = await self._call_with_retries(
            lambda: self._azure_client.responses.create(**request),
            model,
            stream=False,
            context="responses.create",
        )
        return self._parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: AzureOpenAIPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the AzureOpenAI platform."""
        from copy import deepcopy

        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
        logger.info(f"Streaming with Azure OpenAI model: {model_id}")
        request = prompt.as_platform_request(model_id, stream=True)
        request["model"] = self._parameters.azure_deployment_name

        # Initialize message state
        message: dict[str, Any] = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message: dict[str, Any] = {}

        # Retry only the initial stream creation to keep idempotency of outputs/tool calls
        response = await self._call_with_retries(
            lambda: self._azure_client.responses.create(**request),
            model,
            stream=True,
            context="responses.create(stream)",
        )

        # Process each event through the parser
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
        message.setdefault("metadata", {}).update(final_event)
        log_token_usage(logger, message.get("usage", {}))

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
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)
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
            response = await self._call_with_retries(
                lambda the_text=text: self.azure_embeddings_client.embeddings.create(
                    model=model_id,
                    input=the_text,
                ),
                model,
                stream=False,
                context="embeddings.create",
            )
            embedding = response.data[0].embedding
            total_tokens += response.usage.total_tokens
            embeddings.append(embedding)

        return {
            "embeddings": embeddings,
            "model": model,
            "usage": {"total_tokens": total_tokens},
        }

    async def get_available_models(self) -> dict[str, list[str]]:
        # There's just really nothing good to do here unless we have the management plane
        # APIs (which require _different_ auth...)
        return {
            "openai": [
                self._parameters.azure_model_backing_deployment_name or "gpt-5",
                self._parameters.azure_model_backing_deployment_name_embeddings
                or "text-embedding-3-large",
            ],
        }


PlatformClient.register_platform_client("azure", AzureOpenAIClient)
