from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, ParamSpec, TypeVar

from agent_platform.core.delta import GenericDelta, compute_generic_deltas
from agent_platform.core.errors import ErrorCode
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.configs import (
    resolve_generic_model_id_to_platform_specific_model_id,
)
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from anthropic import AsyncAnthropicFoundry

    from agent_platform.core.kernel import Kernel
    from agent_platform.core.platforms.azure_foundry.converters import AzureFoundryConverters
    from agent_platform.core.platforms.azure_foundry.parameters import (
        AzureFoundryPlatformParameters,
    )
    from agent_platform.core.platforms.azure_foundry.parsers import AzureFoundryParsers
    from agent_platform.core.platforms.azure_foundry.prompts import AzureFoundryPrompt

log = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class AzureFoundryClient(
    PlatformClient[
        "AzureFoundryConverters",
        "AzureFoundryParsers",
        "AzureFoundryPlatformParameters",
        "AzureFoundryPrompt",
    ]
):
    NAME: ClassVar[str] = "azure_foundry"
    _GLOBAL_AVAILABLE_MODELS_CACHE: ClassVar[dict[str, list[str]]] = {}
    _GLOBAL_AVAILABLE_MODELS_LOCK: ClassVar[asyncio.Lock] = asyncio.Lock()

    # ------------------------------------------------------------------#
    # Construction
    # ------------------------------------------------------------------#

    def __init__(
        self,
        *,
        kernel: Kernel | None = None,
        parameters: AzureFoundryPlatformParameters | None = None,
        **overrides: Any,
    ) -> None:
        """Initialize the Azure Foundry client.

        Args:
            kernel: Optional kernel instance for tool/function access.
            parameters: Platform-specific configuration parameters.
            **overrides: Additional parameter overrides.
        """
        super().__init__(kernel=kernel, parameters=parameters, **overrides)

        self._client: AsyncAnthropicFoundry | None = None
        # Copy cache efficiently (strings are immutable, only need to copy the lists)
        self._available_models_cache: dict[str, list[str]] = {
            k: list(v) for k, v in self._GLOBAL_AVAILABLE_MODELS_CACHE.items()
        }

    async def _get_client(self) -> AsyncAnthropicFoundry:
        """Lazily create the Anthropic Foundry client."""
        if self._client is None:
            from anthropic import AsyncAnthropicFoundry

            if not self._parameters.endpoint_url:
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        "Azure Foundry endpoint URL is required. "
                        "Provide the full endpoint URL "
                        "(e.g., 'https://my-resource.services.ai.azure.com/v1/messages')."
                    ),
                    data={},
                )

            base_url = self._parameters.get_base_url()
            assert base_url is not None  # guaranteed by endpoint_url check above

            self._client = AsyncAnthropicFoundry(
                api_key=self._parameters.api_key,
                base_url=base_url,
            )
        return self._client

    # ------------------------------------------------------------------#
    # Public API
    # ------------------------------------------------------------------#

    async def generate_response(
        self,
        prompt: AzureFoundryPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a non-streaming response from Azure Foundry.

        Args:
            prompt: The prompt to send to the model.
            model: The model identifier to use.

        Returns:
            The parsed response message.

        Raises:
            PlatformHTTPError: If the API request fails.
        """
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)

        try:
            client = await self._get_client()

            # Build request parameters
            request_params = prompt.as_platform_request(model_id)

            # Add betas if specified
            extra_headers = {}
            if prompt.betas:
                extra_headers["anthropic-beta"] = ",".join(prompt.betas)

            response = await client.messages.create(
                **request_params,
                extra_headers=extra_headers if extra_headers else None,
            )
            return self._parsers.parse_response(response.model_dump())
        except Exception as exc:
            raise self._handle_anthropic_error(exc, model, PlatformHTTPError) from exc

    async def generate_stream_response(
        self,
        prompt: AzureFoundryPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Generate a streaming response from Azure Foundry.

        Args:
            prompt: The prompt to send to the model.
            model: The model identifier to use.

        Yields:
            GenericDelta objects representing incremental response updates.

        Raises:
            StreamingError: If the streaming request fails.
        """
        model_id = await resolve_generic_model_id_to_platform_specific_model_id(self, model)

        try:
            client = await self._get_client()

            # Build request parameters
            request_params = prompt.as_platform_request(model_id)

            # Add betas if specified
            extra_headers = {}
            if prompt.betas:
                extra_headers["anthropic-beta"] = ",".join(prompt.betas)

            stream = await client.messages.create(
                **request_params,
                stream=True,
                extra_headers=extra_headers if extra_headers else None,
            )
        except Exception as exc:
            raise self._handle_anthropic_error(exc, model, StreamingError) from exc

        # ------------------------------------------------------------ #
        # Streaming loop: parse each partial event and yield deltas
        # ------------------------------------------------------------ #
        message_state: dict[str, Any] = {}
        last_msg_state: dict[str, Any] = {}

        try:
            async for event in stream:
                event_dict = event.model_dump() if hasattr(event, "model_dump") else dict(event)
                async for delta in self._parsers.parse_stream_event(event_dict, stream, message_state, last_msg_state):
                    yield delta
                last_msg_state = deepcopy(message_state)
        except Exception as exc:
            raise self._handle_anthropic_error(exc, model, StreamingError) from exc

        # Attach final metadata delta
        final_event = self._generate_platform_metadata()
        message_state.setdefault("metadata", {}).update(final_event)

        for delta in compute_generic_deltas(last_msg_state, message_state):
            yield delta

    # ------------------------------------------------------------------#
    # Embeddings - not supported for Anthropic
    # ------------------------------------------------------------------#

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings - not supported for Anthropic models."""
        raise NotImplementedError("Embeddings are not supported for Azure Foundry/Anthropic models")

    def _init_converters(self, kernel: Kernel | None = None) -> AzureFoundryConverters:
        """Initialize the converters for Azure Foundry.

        Args:
            kernel: Optional kernel instance to attach to converters.

        Returns:
            Configured AzureFoundryConverters instance.
        """
        from agent_platform.core.platforms.azure_foundry.converters import AzureFoundryConverters

        converters = AzureFoundryConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: AzureFoundryPlatformParameters | None = None,
        **kwargs: Any,
    ) -> AzureFoundryPlatformParameters:
        """Initialize platform parameters.

        Args:
            parameters: Optional existing parameters to use or copy.
            **kwargs: Additional parameter overrides.

        Returns:
            Configured AzureFoundryPlatformParameters instance.
        """
        from agent_platform.core.platforms.azure_foundry.parameters import (
            AzureFoundryPlatformParameters,
        )

        if parameters is None:
            parameters = AzureFoundryPlatformParameters(**kwargs)
        elif kwargs:
            parameters = parameters.model_copy(update=kwargs)
        return parameters

    def _init_parsers(self) -> AzureFoundryParsers:
        """Initialize the parsers for Azure Foundry.

        Returns:
            Configured AzureFoundryParsers instance.
        """
        from agent_platform.core.platforms.azure_foundry.parsers import AzureFoundryParsers

        return AzureFoundryParsers()

    async def get_available_models(self) -> dict[str, list[str]]:
        """Get available models for the platform.

        For Azure Foundry, we return a static list of Anthropic Claude models
        that are generally available through the platform.
        """

        # Helper to copy cache (shallow dict copy + list copies, strings are immutable)
        def _copy_cache(cache: dict[str, list[str]]) -> dict[str, list[str]]:
            return {k: list(v) for k, v in cache.items()}

        if self._available_models_cache:
            return _copy_cache(self._available_models_cache)

        if self._GLOBAL_AVAILABLE_MODELS_CACHE:
            self._available_models_cache = _copy_cache(self._GLOBAL_AVAILABLE_MODELS_CACHE)
            return _copy_cache(self._available_models_cache)

        async with self._GLOBAL_AVAILABLE_MODELS_LOCK:
            if self._GLOBAL_AVAILABLE_MODELS_CACHE:
                self._available_models_cache = _copy_cache(self._GLOBAL_AVAILABLE_MODELS_CACHE)
                return _copy_cache(self._available_models_cache)

            # Static list of Anthropic models available through Azure Foundry
            result: dict[str, list[str]] = {
                "anthropic": [
                    "claude-4-5-opus",
                    "claude-4-5-sonnet",
                    "claude-4-5-haiku",
                ],
            }

            # Update global cache
            self._GLOBAL_AVAILABLE_MODELS_CACHE.clear()
            for provider, models in result.items():
                self._GLOBAL_AVAILABLE_MODELS_CACHE[provider] = list(models)

            self._available_models_cache = _copy_cache(self._GLOBAL_AVAILABLE_MODELS_CACHE)
            return _copy_cache(self._available_models_cache)

    # ------------------------------------------------------------------#
    # Error handling
    # ------------------------------------------------------------------#

    def _handle_anthropic_error(
        self,
        error: Exception,
        model: str,
        err_cls: type[PlatformError] = PlatformError,
    ) -> PlatformError:
        """Convert Anthropic SDK exceptions to platform errors.

        Args:
            error: The exception raised by the Anthropic SDK.
            model: The model identifier for error context.
            err_cls: The error class to instantiate.

        Returns:
            A PlatformError subclass with appropriate error code and message.

        Raises:
            Exception: Re-raises unknown errors that are not Anthropic SDK errors.
        """
        from anthropic import (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            BadRequestError,
            InternalServerError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
        )

        if isinstance(error, AuthenticationError):
            return err_cls(
                error_code=ErrorCode.UNAUTHORIZED,
                message="Invalid Azure Foundry API key.",
                data={"model": model},
            )

        if isinstance(error, PermissionDeniedError):
            return err_cls(
                error_code=ErrorCode.FORBIDDEN,
                message="Access denied to Azure Foundry.",
                data={"model": model},
            )

        if isinstance(error, RateLimitError):
            return err_cls(
                error_code=ErrorCode.TOO_MANY_REQUESTS,
                message="Rate limit exceeded for Azure Foundry.",
                data={"model": model},
            )

        if isinstance(error, NotFoundError):
            return err_cls(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Model or deployment not found: {model}",
                data={"model": model},
            )

        if isinstance(error, BadRequestError):
            message = str(error)
            if "context length" in message.lower() or "too long" in message.lower():
                return err_cls(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        f"The request to model '{model}' was rejected because it "
                        f"exceeded the context length limit. Please try again with a "
                        f"shorter request."
                    ),
                    data={"model": model, "error_message": message},
                )
            return err_cls(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"Bad request: {message}",
                data={"model": model},
            )

        if isinstance(error, InternalServerError):
            return err_cls(
                error_code=ErrorCode.UNEXPECTED,
                message="Azure Foundry internal server error.",
                data={"model": model},
            )

        if isinstance(error, APIConnectionError):
            return err_cls(
                error_code=ErrorCode.UNEXPECTED,
                message="Failed to connect to Azure Foundry.",
                data={"model": model},
            )

        if isinstance(error, APIStatusError):
            return err_cls(
                error_code=ErrorCode.UNEXPECTED,
                message=f"Azure Foundry API error: {error.message}",
                data={"model": model, "status_code": error.status_code},
            )

        # Re-raise unknown errors
        raise error


PlatformClient.register_platform_client("azure_foundry", AzureFoundryClient)
