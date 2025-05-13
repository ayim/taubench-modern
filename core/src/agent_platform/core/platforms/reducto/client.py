import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, ClassVar, Optional

from agent_platform.core.delta import GenericDelta
from agent_platform.core.platforms.base import (
    PlatformClient,
    PlatformConfigs,
    PlatformModelMap,
)
from agent_platform.core.platforms.reducto.configs import (
    ReductoModelMap,
    ReductoPlatformConfigs,
)
from agent_platform.core.platforms.reducto.converters import ReductoConverters
from agent_platform.core.platforms.reducto.parameters import ReductoPlatformParameters
from agent_platform.core.platforms.reducto.parsers import ReductoParsers
from agent_platform.core.platforms.reducto.prompts import ReductoPrompt
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from reducto import AsyncReducto

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
        self._reducto_client = self._init_client(self._parameters)

    def _init_client(self, parameters: ReductoPlatformParameters) -> "AsyncReducto":
        from reducto import AsyncReducto

        if parameters.reducto_api_key is None:
            raise ValueError("Reducto API key is required")

        client = AsyncReducto(
            # We have to set one, but we put our key in the headers
            api_key="unused",
            base_url=parameters.reducto_api_url,
        )
        # Set the API key in the client headers directly
        client._client.headers["X-API-Key"] = (
            parameters.reducto_api_key.get_secret_value()
        )
        return client

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

    async def count_tokens(self, prompt: ReductoPrompt, model: str) -> int:
        return 0

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
        from reducto import NOT_GIVEN

        processed_prompt = prompt.as_platform_request(model)

        # Create a standard span with AgentServerContext
        with self.kernel.ctx.start_span("reducto_generate_response") as span:
            span.set_attribute("model", model)
            span.set_attribute("model_provider", "reducto")

            try:
                uploaded_document = await self._reducto_client.upload(
                    file=(
                        processed_prompt.document_name,
                        processed_prompt.document_bytes,
                    ),
                )

                if prompt.operation == "parse":
                    parse_options = processed_prompt.parse_options
                    if parse_options is None:
                        raise ValueError(
                            "Parse options are required for parse operation"
                        )
                    parse_options["document_url"] = uploaded_document.file_id
                    response = await self._reducto_client.parse.run(
                        document_url=uploaded_document.file_id,
                        options=(
                            parse_options["options"]
                            if parse_options and "options" in parse_options
                            else NOT_GIVEN
                        ),
                        advanced_options=(
                            parse_options["advanced_options"]
                            if parse_options and "advanced_options" in parse_options
                            else NOT_GIVEN
                        ),
                        experimental_options=(
                            parse_options["experimental_options"]
                            if parse_options and "experimental_options" in parse_options
                            else NOT_GIVEN
                        ),
                    )

                    return self.parsers.parse_response(response)
                else:
                    extract_options = processed_prompt.extract_options
                    if extract_options is None:
                        raise ValueError(
                            "Extract options are required for extract operation"
                        )
                    extract_options["document_url"] = uploaded_document.file_id
                    response = await self._reducto_client.extract.run(
                        document_url=uploaded_document.file_id,
                        schema=(
                            extract_options["schema"]
                            if extract_options and "schema" in extract_options
                            else NOT_GIVEN
                        ),
                        options=(
                            extract_options["options"]
                            if extract_options and "options" in extract_options
                            else NOT_GIVEN
                        ),
                        advanced_options=(
                            extract_options["advanced_options"]
                            if extract_options and "advanced_options" in extract_options
                            else NOT_GIVEN
                        ),
                        experimental_options=(
                            extract_options["experimental_options"]
                            if extract_options
                            and "experimental_options" in extract_options
                            else NOT_GIVEN
                        ),
                    )

                return self.parsers.parse_response(response)

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


PlatformClient.register_platform_client("reducto", ReductoClient)
