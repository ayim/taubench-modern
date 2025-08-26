import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, ClassVar, Optional

from agent_platform.core.delta import GenericDelta
from agent_platform.core.platforms.base import (
    PlatformClient,
    PlatformConfigs,
    PlatformModelMap,
)
from agent_platform.core.platforms.openai.client import OpenAIClient
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.platforms.reducto.configs import (
    ReductoModelMap,
    ReductoPlatformConfigs,
)
from agent_platform.core.platforms.reducto.converters import ReductoConverters
from agent_platform.core.platforms.reducto.parameters import ReductoPlatformParameters
from agent_platform.core.platforms.reducto.parsers import ReductoParsers
from agent_platform.core.platforms.reducto.prompts import ReductoPrompt
from agent_platform.core.platforms.reducto.reducto import PollingReductoClient
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from agent_platform.core.context import AgentServerContext
    from agent_platform.core.kernel import Kernel

logger = logging.getLogger(__name__)


class ReductoClient(
    PlatformClient[
        ReductoConverters,
        ReductoParsers,
        ReductoPlatformParameters,
        ReductoPrompt,
    ],
):
    """A client for the Reducto platform."""

    NAME: ClassVar[str] = "reducto"
    configs: ClassVar[type[PlatformConfigs]] = ReductoPlatformConfigs
    model_map: ClassVar[type[PlatformModelMap]] = ReductoModelMap

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: ReductoPlatformParameters | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            kernel=kernel,
            parameters=parameters,
            **kwargs,
        )
        if parameters is None or self._parameters.reducto_api_key is None:
            raise ValueError("Reducto API key is required")

        self._reducto_client = PollingReductoClient(
            self._parameters.reducto_api_url,
            self._parameters.reducto_api_key.get_secret_value(),
        )

        # Optionally initialize a delegate client
        if self._parameters.delegate_kind:
            match self._parameters.delegate_kind:
                case "openai":
                    self._delegate = OpenAIClient(
                        kernel=kernel,
                        parameters=OpenAIPlatformParameters(
                            openai_api_key=self._parameters.delegate_api_key,
                        ),
                    )
                case _:
                    raise ValueError(
                        "Only 'openai' is supported as a delegate " + "platform client"
                    )
        else:
            logger.warning("No delegate configured for Reducto platform client")
            self._delegate = None

    def _init_converters(self, kernel: "Kernel | None" = None) -> ReductoConverters:
        converters = ReductoConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parameters(
        self,
        parameters: ReductoPlatformParameters | None = None,
        **kwargs: Any,
    ) -> ReductoPlatformParameters:
        if parameters is None:
            raise ValueError("Parameters are required for Reducto client")
        return parameters

    def _init_parsers(self) -> ReductoParsers:
        return ReductoParsers()

    async def generate_response(
        self,
        prompt: ReductoPrompt,
        model: str,
        ctx: Optional["AgentServerContext"] = None,
    ) -> ResponseMessage:
        """Generate a response from the Reducto platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use for the generation.
            ctx: Optional AgentServerContext for telemetry.

        Returns:
            A ResponseMessage with the model's response.
        """

        processed_prompt = prompt.as_platform_request(model)

        # Create a standard span with AgentServerContext
        with self.kernel.ctx.start_span("reducto_generate_response") as span:
            span.set_attribute("model", model)
            span.set_attribute("model_provider", "reducto")

            try:
                # Upload the document to Reducto
                uploaded_document = await self._reducto_client.upload(
                    file=(
                        processed_prompt.document_name,
                        processed_prompt.document_bytes,
                    ),
                )

                # Then, do some processing over it.
                match prompt.operation:
                    case "classify":
                        return await self._classify(
                            prompt=processed_prompt,
                            uploaded_document=uploaded_document,
                        )
                        pass
                    case "parse":
                        parse_response = await self._reducto_client.parse(
                            prompt=processed_prompt,
                            uploaded_document=uploaded_document,
                        )

                        return self.parsers.parse_response(parse_response)
                    case "extract":
                        extract_response = await self._reducto_client.extract(
                            prompt=processed_prompt,
                            uploaded_document=uploaded_document,
                        )
                        return self.parsers.parse_response(extract_response)
                    case _:
                        raise ValueError(f"Unsupported operation: {prompt.operation}")

            except Exception as e:
                span.set_attribute("error", str(e))
                span.set_attribute("error_type", type(e).__name__)
                raise

    async def generate_stream_response(
        self,
        prompt: ReductoPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Stream a response from the Reducto platform.

        NOTE: Reducto does not support streaming at this time.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use to generate the response.
            ctx: Optional AgentServerContext for telemetry.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        response = await self.generate_response(prompt, model)
        as_dict = response.model_dump()
        for key, value in as_dict.items():
            yield GenericDelta(path=f"/{key}", value=value, op="add")

    async def create_embeddings(self, texts: list[str], model: str) -> dict[str, Any]:
        raise NotImplementedError("Reducto does not support embeddings at this time")

    async def _classify(
        self,
        prompt: ReductoPrompt,
        uploaded_document,
    ) -> ResponseMessage:
        from openai.types.chat import (
            ChatCompletionAssistantMessageParam,
            ChatCompletionMessageParam,
            ChatCompletionUserMessageParam,
        )
        from reducto.types.shared.parse_response import (
            ResultURLResult,
        )

        if self._delegate is None:
            raise ValueError("Delegate client is required for classify operation")
        if prompt.system_prompt is None:
            raise ValueError("System prompt is required for classify operation")

        parse_resp = await self._reducto_client.parse(
            prompt=prompt,
            uploaded_document=uploaded_document,
        )
        if isinstance(parse_resp.result, ResultURLResult):
            raise ValueError("Parse response is a URL result, cannot classify")

        # Trim to first 5 chunks
        chunks = parse_resp.result.chunks[:5]
        parsed_prompt_input = "\n".join([chunk.model_dump_json() for chunk in chunks])

        llm_messages: list[ChatCompletionMessageParam] = []
        llm_messages.append(
            ChatCompletionUserMessageParam(
                role="user",
                content=prompt.system_prompt,
            )
        )
        llm_messages.append(
            ChatCompletionAssistantMessageParam(
                role="assistant",
                content="Understood, I will assist the user with their request.",
            )
        )
        llm_messages.append(
            ChatCompletionUserMessageParam(
                role="user",
                content="Reply with the answer only, nothing else." + parsed_prompt_input,
            )
        )

        import pprint

        logger.debug(
            "Classifying with OpenAI LLM: system prompt: %s, prompt messages: %s",
            prompt.system_prompt,
            pprint.pformat(llm_messages),
        )

        # make an openai call
        return await self._delegate.generate_response(
            model="gpt-4.1",
            prompt=OpenAIPrompt(
                messages=llm_messages,
                tools=[],
                temperature=0.0,
                max_tokens=512,
            ),
        )


PlatformClient.register_platform_client("reducto", ReductoClient)
