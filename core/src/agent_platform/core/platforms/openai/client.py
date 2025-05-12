import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, Optional

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import (
    PlatformClient,
    PlatformConfigs,
    PlatformModelMap,
)
from agent_platform.core.platforms.openai.configs import (
    OpenAIModelMap,
    OpenAIPlatformConfigs,
)
from agent_platform.core.platforms.openai.converters import OpenAIConverters
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.platforms.openai.parsers import OpenAIParsers
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from agent_platform.core.context import AgentServerContext
    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)


class OpenAIClient(
    PlatformClient[
        OpenAIConverters,
        OpenAIParsers,
        OpenAIPlatformParameters,
        OpenAIPrompt,
    ],
):
    """A client for the OpenAI platform."""

    NAME: ClassVar[str] = "openai"
    configs: ClassVar[type[PlatformConfigs]] = OpenAIPlatformConfigs
    model_map: ClassVar[type[PlatformModelMap]] = OpenAIModelMap

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: OpenAIPlatformParameters | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            kernel=kernel,
            parameters=parameters,
            **kwargs,
        )
        self._openai_client = self._init_client(self._parameters)

    def _init_client(self, parameters: OpenAIPlatformParameters) -> "AsyncOpenAI":
        from openai import AsyncOpenAI

        if parameters.openai_api_key is None:
            raise ValueError("OpenAI API key is required")

        return AsyncOpenAI(api_key=parameters.openai_api_key.get_secret_value())

    def _init_converters(self, kernel: "Kernel | None" = None) -> OpenAIConverters:
        converters = OpenAIConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: OpenAIPlatformParameters | None = None,
        **kwargs: Any,
    ) -> OpenAIPlatformParameters:
        if parameters is None:
            raise ValueError("Parameters are required for OpenAI client")
        return parameters

    def _init_parsers(self) -> OpenAIParsers:
        return OpenAIParsers()

    async def generate_response(
        self,
        prompt: OpenAIPrompt,
        model: str,
        ctx: Optional["AgentServerContext"] = None,
    ) -> ResponseMessage:
        """Generate a response from the OpenAI platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use for the generation.
            ctx: Optional AgentServerContext for telemetry.

        Returns:
            A ResponseMessage with the model's response.
        """
        request = prompt.as_platform_request(model)
        try:
            ctx = self.kernel.ctx
        except RuntimeError:
            ctx = None

        if ctx:
            # First create a standard span with AgentServerContext
            with ctx.start_span("openai_generate_response") as span:
                span.set_attribute("model", model)
                span.set_attribute("model_provider", "openai")

                try:
                    # Prepare inputs and metadata for LangSmith
                    messages = request.get("messages", [])
                    inputs = {"messages": messages}

                    # Extract model and provider info for metadata
                    metadata = {
                        "model": model,
                        "provider": "openai",
                        "trace_name": "OpenAI Chat Completion",
                    }

                    # Use LangSmith tracing with a with block
                    async with ctx.langsmith.trace_llm(
                        name="llm_completion",
                        inputs=inputs,
                        user_context=ctx.user_context,
                        metadata=metadata,
                    ) as langsmith_span:
                        # Make the API call
                        response = await self._openai_client.chat.completions.create(
                            **request
                        )

                        # Record the response in the LangSmith span if it's a dict
                        if isinstance(langsmith_span, dict):
                            content = response.choices[0].message.content

                            langsmith_span["output"] = {
                                "content": content,
                                "role": "assistant",
                            }

                            # Add usage information
                            if response.usage:
                                langsmith_span["usage"] = {
                                    "input_tokens": response.usage.prompt_tokens,
                                    "output_tokens": response.usage.completion_tokens,
                                    "total_tokens": response.usage.total_tokens,
                                }

                    # Add usage information to regular span if available
                    if hasattr(response, "usage") and response.usage:
                        span.set_attribute(
                            "completion_tokens", response.usage.completion_tokens
                        )
                        span.set_attribute("total_tokens", response.usage.total_tokens)

                    # Parse and return the response
                    result = self._parsers.parse_response(response)
                    return result
                except Exception as e:
                    span.set_attribute("error", str(e))
                    span.set_attribute("error_type", type(e).__name__)
                    raise
        else:
            # Fall back to non-traced execution
            response = await self._openai_client.chat.completions.create(**request)
            return self._parsers.parse_response(response)

    async def generate_stream_response(  # noqa: C901, PLR0912, PLR0915
        self,
        prompt: OpenAIPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the OpenAI platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.
            ctx: Optional AgentServerContext for telemetry.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        logger.info(f"Streaming with OpenAI model: {model}")
        request = prompt.as_platform_request(model, stream=True)

        # Initialize message state
        message: dict[str, Any] = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message: dict[str, Any] = {}

        # Add stream=True to ensure streaming is enabled
        request["stream"] = True
        try:
            ctx = self.kernel.ctx
        except RuntimeError:
            ctx = None
        # Start span if context is provided
        if ctx:
            span = None
            try:
                # Create a span for the entire streaming operation
                with ctx.start_span("openai_stream_response") as span:
                    span.set_attribute("model", model)
                    span.set_attribute("model_provider", "openai")
                    span.set_attribute("streaming", True)

                    # Use LangSmith tracing if available
                    langsmith_span = None

                    # Start streaming request
                    response = await self._openai_client.chat.completions.create(
                        **request
                    )

                    # Process streaming chunks -
                    # different approach based on whether LangSmith is available
                    # Extract messages for LangSmith
                    messages = request.get("messages", [])
                    inputs = {"messages": messages}

                    # Set up metadata
                    metadata = {
                        "model": model,
                        "provider": "openai",
                        "trace_name": "OpenAI Streaming Chat Completion",
                        "streaming": True,
                    }

                    # Process the full stream with LangSmith tracing
                    # First collect all the chunks and build the response
                    all_chunks = []
                    assembled_content = ""

                    async for event in response:
                        all_chunks.append(event)
                        # Process chunk for content
                        if (
                            hasattr(event.choices[0].delta, "content")
                            and event.choices[0].delta.content
                        ):
                            assembled_content += event.choices[0].delta.content

                        # Process the event for deltas
                        async for delta in self._parsers.parse_stream_event(
                            event,
                            message,
                            last_message,
                        ):
                            yield delta

                        # Update last message state
                        last_message = deepcopy(message)

                    # Now send both the inputs and full response to LangSmith in one go
                    try:
                        # Use the with block properly to trace the operation
                        async with ctx.langsmith.trace_llm(
                            name="llm_stream_completion",
                            inputs=inputs,
                            user_context=ctx.user_context,
                            metadata=metadata,
                        ) as langsmith_span:
                            if isinstance(langsmith_span, dict):
                                # Add the final response
                                langsmith_span["output"] = {
                                    "content": assembled_content,
                                    "role": "assistant",
                                }

                                # Add usage information if available in the last event
                                if (
                                    hasattr(all_chunks[-1], "usage")
                                    and all_chunks[-1].usage
                                ):
                                    usage = all_chunks[-1].usage
                                    langsmith_span["usage"] = {
                                        "input_tokens": usage.prompt_tokens,
                                        "output_tokens": usage.completion_tokens,
                                        "total_tokens": usage.total_tokens,
                                    }
                    except Exception as e:
                        logger.warning(f"Failed to trace with LangSmith: {e}")

                    # Update last message state after processing each event
                    last_message = deepcopy(message)

                    # Add final metadata and platform info
                    final_event = self._generate_platform_metadata()
                    if "metadata" not in message:
                        message["metadata"] = {}
                    message["metadata"].update(final_event)

                    # Put request ID (if any) into raw_response
                    request_id = message.get("additional_response_fields", {}).get(
                        "id", "unknown"
                    )
                    message["raw_response"] = {
                        "ResponseMetadata": {
                            "RequestId": request_id,
                            "HTTPStatusCode": 200,
                            "RetryAttempts": 0,
                        },
                        "stream": None,
                    }

                    # Add usage information to LangSmith span if available
                    if langsmith_span and "usage" in message.get("metadata", {}):
                        usage = message["metadata"]["usage"]
                        if isinstance(usage, dict):
                            # When langsmith_span is a dict,
                            # we should update it directly
                            if "usage" not in langsmith_span:
                                langsmith_span["usage"] = {}

                            langsmith_span["usage"]["input_tokens"] = usage.get(
                                "prompt_tokens", 0
                            )
                            langsmith_span["usage"]["output_tokens"] = usage.get(
                                "completion_tokens", 0
                            )
                            langsmith_span["usage"]["total_tokens"] = usage.get(
                                "total_tokens", 0
                            )

                    # Generate final deltas
                    for delta in compute_generic_deltas(last_message, message):
                        yield delta
            except Exception as e:
                if span:
                    span.set_attribute("error", str(e))
                    span.set_attribute("error_type", type(e).__name__)
                raise
        else:
            # Fall back to non-traced execution
            response = await self._openai_client.chat.completions.create(**request)
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
            if "metadata" not in message:
                message["metadata"] = {}
            message["metadata"].update(final_event)

            # Put request ID (if any) into raw_response
            request_id = message.get("additional_response_fields", {}).get(
                "id", "unknown"
            )
            message["raw_response"] = {
                "ResponseMetadata": {
                    "RequestId": request_id,
                    "HTTPStatusCode": 200,
                    "RetryAttempts": 0,
                },
                "stream": None,
            }

            # Generate final deltas
            for delta in compute_generic_deltas(last_message, message):
                yield delta

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings using a OpenAI embedding model.

        Args:
            texts: The texts to embed.
            model: The model to use for embeddings.
            ctx: Optional AgentServerContext for telemetry.

        Returns:
            A dictionary containing the embeddings and usage information.
        """
        model_id = OpenAIModelMap.model_aliases[model]
        logger.info(
            f"Creating embeddings with OpenAI model: {model} (model_id: {model_id})",
        )

        if not texts:
            return {
                "embeddings": [],
                "model": model,
                "usage": {"total_tokens": 0},
            }
        try:
            ctx = self.kernel.ctx
        except RuntimeError:
            ctx = None
        if ctx:
            with ctx.start_span("create_embeddings") as span:
                span.set_attribute("model", model)
                span.set_attribute("model_id", model_id)
                span.set_attribute("text_count", len(texts))
                span.set_attribute("model_provider", "openai")

                # Check if we should use LangSmith for embeddings
                has_langsmith_tracer = (
                    hasattr(ctx, "langsmith")
                    and ctx.langsmith is not None
                    and hasattr(ctx.langsmith, "trace_llm")
                )

                try:
                    embeddings = []
                    total_tokens = 0

                    # Process embeddings with or without LangSmith tracing
                    if has_langsmith_tracer:
                        # Set up LangSmith tracing for embeddings
                        inputs = {
                            "texts": texts,
                        }
                        metadata = {
                            "model": model_id,
                            "provider": "openai",
                            "trace_name": "OpenAI Embeddings",
                            "count": len(texts),
                        }

                        # Use with block for tracing
                        async with ctx.langsmith.trace_llm(
                            name="embedding_operation",
                            inputs=inputs,
                            user_context=ctx.user_context,
                            metadata=metadata,
                        ) as langsmith_span:
                            # Process each text and create embeddings
                            for text in texts:
                                response = await self._openai_client.embeddings.create(
                                    model=model_id,
                                    input=text,
                                )
                                embedding = response.data[0].embedding
                                total_tokens += response.usage.total_tokens
                                embeddings.append(embedding)

                            # Add usage information to span dictionary
                            if isinstance(langsmith_span, dict):
                                langsmith_span["usage"] = {"total_tokens": total_tokens}
                    else:
                        # Process embeddings without LangSmith
                        for text in texts:
                            response = await self._openai_client.embeddings.create(
                                model=model_id,
                                input=text,
                            )
                            embedding = response.data[0].embedding
                            total_tokens += response.usage.total_tokens
                            embeddings.append(embedding)

                    # Add total tokens to regular span
                    span.set_attribute("total_tokens", total_tokens)

                    return {
                        "embeddings": embeddings,
                        "model": model,
                        "usage": {"total_tokens": total_tokens},
                    }
                except Exception as e:
                    span.set_attribute("error", str(e))
                    span.set_attribute("error_type", type(e).__name__)
                    raise
        else:
            # Fall back to non-traced execution
            embeddings = []
            total_tokens = 0
            for text in texts:
                response = await self._openai_client.embeddings.create(
                    model=model_id,
                    input=text,
                )
                embedding = response.data[0].embedding
                total_tokens += response.usage.total_tokens
                embeddings.append(embedding)
            return {
                "embeddings": embeddings,
                "model": model,
                "usage": {"total_tokens": total_tokens},
            }


PlatformClient.register_platform_client("openai", OpenAIClient)
