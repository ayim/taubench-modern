import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar

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

    async def count_tokens(
        self,
        prompt: OpenAIPrompt,
        model: str,
    ) -> int:
        """Count the tokens in a prompt.

        Args:
            prompt: The prompt to count the tokens of.
            model: The model to use to count the tokens.

        Returns:
            The number of tokens in the prompt.
        """
        # TODO: Should we import in a try block and use a fallback algorithm
        # if it's not installed?
        import tiktoken

        model_id = OpenAIModelMap.model_aliases[model]
        encoding = tiktoken.encoding_for_model(model_id)

        # Get the request dictionary
        request = prompt.as_platform_request(model)

        # Format messages into a string representation
        messages_str = ""
        for msg in request.get("messages", []):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                # Handle multimodal content
                content = " ".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in content
                )
            messages_str += f"{role}: {content}\n"

        # Add tools if present
        if "tools" in request:
            tools_str = "tools:\n"
            for tool in request["tools"]:
                if "function" in tool:
                    func = tool["function"]
                    tools_str += f"function: {func.get('name', '')}\n"
                    tools_str += f"description: {func.get('description', '')}\n"
                    if "parameters" in func:
                        tools_str += f"parameters: {func['parameters']}\n"
            messages_str += tools_str

        # Encode the formatted string
        encoded_prompt = encoding.encode(messages_str)
        return len(encoded_prompt)

    async def generate_response(
        self,
        prompt: OpenAIPrompt,
        model: str,
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
        response = await self._openai_client.chat.completions.create(**request)
        return self._parsers.parse_response(response)

    async def generate_stream_response(
        self,
        prompt: OpenAIPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the OpenAI platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.

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
        logger.info(f"Token usage: {message['usage']}")

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
