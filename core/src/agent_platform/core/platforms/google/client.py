import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, cast

from fastapi import status
from google import genai
from google.genai.types import (
    ContentListUnion,
    GenerateContentConfig,
    GenerateContentResponse,
)

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
from agent_platform.core.platforms.google.configs import (
    GoogleModelMap,
    GooglePlatformConfigs,
)
from agent_platform.core.platforms.google.converters import GoogleConverters
from agent_platform.core.platforms.google.parameters import GooglePlatformParameters
from agent_platform.core.platforms.google.parsers import GoogleParsers
from agent_platform.core.platforms.google.prompts import GooglePrompt
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)


class GoogleClient(
    PlatformClient[
        GoogleConverters,
        GoogleParsers,
        GooglePlatformParameters,
        GooglePrompt,
    ],
):
    """A client for the Google Gemini platform."""

    NAME: ClassVar[str] = "google"
    configs: ClassVar[type[PlatformConfigs]] = GooglePlatformConfigs
    model_map: ClassVar[type[PlatformModelMap]] = GoogleModelMap

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: GooglePlatformParameters | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            kernel=kernel,
            parameters=parameters,
            **kwargs,
        )
        self._google_client = self._init_client(self._parameters)

    def _init_client(self, parameters: GooglePlatformParameters) -> genai.Client:
        """Initialize the Google GenAI client.

        Args:
            parameters: The parameters for client initialization.

        Returns:
            A Google GenAI client.

        Raises:
            ValueError: If API key is not provided.
        """
        if parameters.google_api_key is None:
            raise ValueError("Google API key is required")

        return genai.Client(api_key=parameters.google_api_key.get_secret_value())

    def _init_converters(self, kernel: "Kernel | None" = None) -> GoogleConverters:
        """Initialize the Google converters.

        Args:
            kernel: The kernel to attach to the converters.

        Returns:
            The initialized converters.
        """
        converters = GoogleConverters()
        if kernel:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: GooglePlatformParameters | None = None,
        **kwargs: Any,
    ) -> GooglePlatformParameters:
        """Initialize the platform parameters.

        Args:
            parameters: The parameters to initialize.
            **kwargs: Additional keyword arguments.

        Returns:
            The initialized parameters.

        Raises:
            ValueError: If parameters are not provided.
        """
        if parameters is None:
            raise ValueError("Parameters are required for Google client")
        return parameters

    def _init_parsers(self) -> GoogleParsers:
        """Initialize the Google parsers.

        Returns:
            The initialized parsers.
        """
        return GoogleParsers()

    def _handle_google_error(  # noqa: PLR0911
        self, error: Exception, model: str, error_type: type[PlatformError] = PlatformError
    ) -> PlatformError:
        """Handle Google GenAI errors and convert them to PlatformError instances.

        Args:
            error: The Google GenAI exception that was raised
            model: The model being used when the error occurred
            error_type: The type of error to return. Defaults to PlatformError.

        Returns:
            PlatformError: The appropriate error for the given Google GenAI error
        """
        from google.genai.errors import APIError, ClientError, ServerError

        # Check if it's a Google API error type
        if not isinstance(error, ClientError | ServerError | APIError):
            # For any other unexpected errors, re-raise them
            raise error

        # Extract error details
        status_code = getattr(error, "code", 0)
        error_message = getattr(error, "message", str(error))
        error_status = getattr(error, "status", None)

        # Map HTTP status codes to platform error codes using match/case
        match status_code:
            case status.HTTP_400_BAD_REQUEST:
                return error_type(
                    error_code=ErrorCode.BAD_REQUEST,
                    message="Something went wrong while sending the request to Google model "
                    f"'{model}', please try again or contact support.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )
            case status.HTTP_401_UNAUTHORIZED:
                return error_type(
                    error_code=ErrorCode.UNAUTHORIZED,
                    message="Authentication failed for Google API. Please check your API "
                    "key and credentials.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )
            case status.HTTP_403_FORBIDDEN:
                return error_type(
                    error_code=ErrorCode.FORBIDDEN,
                    message=f"Access denied for Google model '{model}'. Please check "
                    "your permissions.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )
            case status.HTTP_404_NOT_FOUND:
                return error_type(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Google model '{model}' not found. Please verify the model name.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )
            case status.HTTP_422_UNPROCESSABLE_ENTITY:
                return error_type(
                    error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                    message=f"Something went wrong while sending the request to Google model "
                    f"'{model}', please try again or contact support.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )
            case status.HTTP_429_TOO_MANY_REQUESTS:
                return error_type(
                    error_code=ErrorCode.TOO_MANY_REQUESTS,
                    message=f"Google API usage limit reached for model '{model}'. "
                    f"Please increase the limit or switch to an available model.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )
            case _ if (
                status.HTTP_400_BAD_REQUEST <= status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
            ):
                # Other client errors
                return error_type(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=f"Something went wrong while sending the request to Google model "
                    f"'{model}', please try again or contact support.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )
            case _ if status.HTTP_500_INTERNAL_SERVER_ERROR <= status_code < 600:  # noqa: PLR2004
                # Server errors
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Something went wrong while sending the request to Google model "
                    f"'{model}', please try again or contact support.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )
            case _:
                # Unknown status code
                return error_type(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Something went wrong while sending the request to Google model "
                    f"'{model}', please try again or contact support.",
                    data={
                        "model": model,
                        "status_code": status_code,
                        "status": error_status,
                        "error_message": error_message,
                    },
                )

    async def generate_response(
        self,
        prompt: GooglePrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a response from the Google platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

        Returns:
            The response message.
        """
        request = prompt.as_platform_request(model)
        logger.info(f"Sending request to Google model: {model}")

        try:
            response = await self._google_client.aio.models.generate_content(
                model=cast(str, request["model"]),
                contents=cast(ContentListUnion, request["contents"]),
                config=cast(GenerateContentConfig, request["config"]),
            )
        except Exception as e:
            raise self._handle_google_error(e, model, PlatformHTTPError) from e

        # Log token usage information if available
        if response.usage_metadata:
            usage_metadata = response.usage_metadata
            prompt_tokens = usage_metadata.prompt_token_count
            completion_tokens = usage_metadata.candidates_token_count

            # Safely compute total tokens, handling None values
            if usage_metadata.total_token_count is not None:
                total_tokens = usage_metadata.total_token_count
            else:
                # Ensure both values are not None before adding
                prompt_tokens = 0 if prompt_tokens is None else prompt_tokens
                completion_tokens = 0 if completion_tokens is None else completion_tokens
                total_tokens = prompt_tokens + completion_tokens

            logger.info(
                f"Token usage: prompt={prompt_tokens}, completion={completion_tokens}, "
                f"total={total_tokens}",
            )
            if usage_metadata.thoughts_token_count is not None:
                logger.info(
                    f"Internal thinking tokens: {usage_metadata.thoughts_token_count}",
                )

        # Parse the response
        parsed_response = self._parsers.parse_response(response)

        return parsed_response

    async def generate_stream_response(
        self,
        prompt: GooglePrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the Google platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        logger.info(f"Streaming with Google model: {model}")

        request = prompt.as_platform_request(model, stream=True)

        # Initialize state
        message_state = self._initialize_stream_state()
        token_counters = {"prompt": 0, "completion": 0, "total": 0, "thinking": 0}

        try:
            # Get stream response
            stream_response = await self._google_client.aio.models.generate_content_stream(
                model=cast(str, request["model"]),
                contents=cast(ContentListUnion, request["contents"]),
                config=cast(GenerateContentConfig, request["config"]),
            )

            async for chunk in stream_response:  # type: ignore
                try:
                    # Update token counters from chunk metadata
                    self._update_token_counters_from_chunk(chunk, token_counters)

                    # Process the chunk and yield deltas
                    async for delta in self._parsers.parse_stream_event(
                        chunk,
                        message_state["current"],
                        message_state["last"],
                    ):
                        yield delta

                    # Update last message state after processing
                    message_state["last"] = deepcopy(message_state["current"])

                except Exception as e:
                    logger.error(f"Error processing stream chunk: {e}")
                    self._log_chunk_debug_info(chunk)
                    self._add_error_to_message(message_state["current"], e)
                    break

        except Exception as e:
            # Add error information to message metadata for backward compatibility
            self._add_error_to_message(message_state["current"], e)
            # Handle any errors during streaming using the extracted error handler
            raise self._handle_google_error(e, model, StreamingError) from e

        # Add final metadata and generate deltas for any remaining changes
        self._add_final_metadata(message_state["current"], token_counters)

        # Generate final deltas
        for delta in compute_generic_deltas(
            message_state["last"],
            message_state["current"],
        ):
            yield delta

    def _initialize_stream_state(self) -> dict[str, Any]:
        """Initialize state for streaming.

        Returns:
            A dictionary with the initial message state.
        """
        message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }

        return {
            "current": message,
            "last": {},
        }

    def _update_token_counters_from_chunk(
        self,
        chunk: GenerateContentResponse,
        token_counters: dict[str, int],
    ) -> None:
        """Update token counters from chunk metadata.

        Args:
            chunk: The chunk from the stream.
            token_counters: The token counters to update.
        """
        if not chunk.usage_metadata:
            return

        usage_metadata = chunk.usage_metadata

        # Extract token counts from metadata
        chunk_prompt_tokens = usage_metadata.prompt_token_count
        chunk_completion_tokens = usage_metadata.candidates_token_count

        # Compute total if not provided
        if usage_metadata.total_token_count is not None:
            chunk_total_tokens = usage_metadata.total_token_count
        else:
            # Ensure values are not None before adding
            chunk_prompt = 0 if chunk_prompt_tokens is None else chunk_prompt_tokens
            chunk_completion = 0 if chunk_completion_tokens is None else chunk_completion_tokens
            chunk_total_tokens = chunk_prompt + chunk_completion

        chunk_thinking_tokens = usage_metadata.thoughts_token_count

        # Update counters with max values
        token_counters["prompt"] = max(
            token_counters["prompt"],
            0 if chunk_prompt_tokens is None else chunk_prompt_tokens,
        )
        token_counters["completion"] = max(
            token_counters["completion"],
            0 if chunk_completion_tokens is None else chunk_completion_tokens,
        )
        token_counters["total"] = max(
            token_counters["total"],
            0 if chunk_total_tokens is None else chunk_total_tokens,
        )
        token_counters["thinking"] = max(
            token_counters["thinking"],
            0 if chunk_thinking_tokens is None else chunk_thinking_tokens,
        )

    def _log_chunk_debug_info(self, chunk: GenerateContentResponse) -> None:
        """Log debug information about a chunk.

        Args:
            chunk: The chunk to log information about.
        """
        # Log more details about the chunk and the error
        logger.debug(f"Stream chunk attributes: {dir(chunk)}")

        if chunk.usage_metadata:
            logger.debug(
                f"Usage metadata attributes: {dir(chunk.usage_metadata)}",
            )

            # Log specific token count types for debugging
            metadata_attrs = [
                "prompt_token_count",
                "candidates_token_count",
                "total_token_count",
                "thoughts_token_count",
            ]

            for attr in metadata_attrs:
                if hasattr(chunk.usage_metadata, attr):
                    logger.debug(
                        f"{attr} type: {type(getattr(chunk.usage_metadata, attr))}",
                    )

    def _add_error_to_message(self, message: dict[str, Any], error: Exception) -> None:
        """Add error information to the message.

        Args:
            message: The message to add error information to.
            error: The error that occurred.
        """
        message.setdefault("metadata", {})

        message["metadata"]["error"] = str(error)
        message["metadata"]["error_type"] = type(error).__name__

    def _add_final_metadata(
        self,
        message: dict[str, Any],
        token_counters: dict[str, int],
    ) -> None:
        """Add final metadata to the message.

        Args:
            message: The message to add metadata to.
            token_counters: The token counters with usage information.
        """
        # Log token usage information
        logger.info(
            "Final token usage: "
            f"prompt={token_counters['prompt']}, "
            f"completion={token_counters['completion']}, "
            f"total={token_counters['total']}",
        )

        if token_counters["thinking"] > 0:
            logger.info(f"Internal thinking tokens: {token_counters['thinking']}")

        # Add platform metadata
        if "metadata" not in message:
            message["metadata"] = {}

        message["metadata"].update(self._generate_platform_metadata())

        # Add token usage to the message
        if "usage" not in message:
            message["usage"] = {}

        message["usage"].update(
            {
                "input_tokens": token_counters["prompt"],
                "output_tokens": token_counters["completion"],
                "total_tokens": token_counters["total"],
            },
        )

        # Add thinking tokens to metadata if available
        if token_counters["thinking"] > 0:
            if "token_metrics" not in message["metadata"]:
                message["metadata"]["token_metrics"] = {}

            message["metadata"]["token_metrics"]["thinking_tokens"] = token_counters["thinking"]

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings using a Google embedding model.

        Args:
            texts: The texts to create embeddings for.
            model: The model to use to create embeddings.

        Returns:
            A dictionary containing the embeddings and usage information.
        """
        model_id = cast(str, GoogleModelMap.model_aliases[model])
        logger.info(
            f"Creating embeddings with Google model: {model} (model_id: {model_id})",
        )

        if not texts:
            return {
                "embeddings": [],
                "model": model,
                "usage": {"total_tokens": 0},
            }

        embeddings = []
        total_tokens = 0

        for i, text in enumerate(texts):
            # Note: Gemini does not provide a token count for embeddings.
            # Generate the embedding
            logger.info(f"Generating embedding for text #{i + 1}")
            try:
                embedding_result = await self._google_client.aio.models.embed_content(
                    model=model_id,
                    contents=text,
                )
            except Exception as e:
                raise self._handle_google_error(e, model, PlatformHTTPError) from e

            embedding_values = []

            if embedding_result:
                logger.info(
                    f"Embedding result for model {model_id}: ",
                    embedding_result,
                )
                embedding = embedding_result.embeddings
                if embedding:
                    logger.info(f"Embedding found: {embedding}")
                    logger.info(f"{embedding[0].values}")
                    embedding_values = embedding[0].values
                    if embedding_values:
                        logger.debug(
                            f"Generated embedding with {len(embedding_values)} dimensions",
                        )
                        embeddings.append(embedding_values)
                    else:
                        logger.warning("No embedding values found")

        logger.info(f"Generated {len(embeddings)} embeddings")

        return {
            "embeddings": embeddings,
            "model": model,
            "usage": {"total_tokens": total_tokens},
        }

    async def count_tokens(
        self,
        prompt: GooglePrompt,
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
        raise NotImplementedError("count_tokens is not yet implemented for Google")


PlatformClient.register_platform_client("google", GoogleClient)
