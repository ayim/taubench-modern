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
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from sema4ai_docint.agent_server_client.transport.base import TransportBase
    from sema4ai_docint.extraction.reducto import AsyncExtractionClient
    from sema4ai_docint.services.persistence.base import ParsedDocumentPersistence

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
        parameters: ReductoPlatformParameters,
        **kwargs: Any,
    ):
        super().__init__(
            kernel=kernel,
            parameters=parameters,
            **kwargs,
        )
        self._extraction_service: AsyncExtractionClient | None = None
        # Optionally initialize a delegate client for classify operations
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

    @property
    def extraction_service(self) -> "AsyncExtractionClient":
        """Get the async extraction service for Reducto operations."""
        from sema4ai_docint.extraction.reducto import AsyncExtractionClient

        if not self._parameters.reducto_api_key:
            raise ValueError("Reducto API key is required")

        if self._extraction_service is None:
            # Create extraction service directly - no transport needed
            self._extraction_service = AsyncExtractionClient(
                api_key=self._parameters.reducto_api_key.get_secret_value(),
                disable_ssl_verification=False,
                base_url=self._parameters.reducto_api_url,
            )
        return self._extraction_service

    async def generate_response(
        self,
        prompt: ReductoPrompt,
        model: str,
        ctx: Optional["AgentServerContext"] = None,
        *,
        transport: Optional["TransportBase"] = None,
        persistence: Optional["ParsedDocumentPersistence"] = None,
    ) -> ResponseMessage:
        """Generate a response from the Reducto platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use for the generation.
            ctx: Optional AgentServerContext for telemetry.
            transport: Optional transport for file access (required for parse/extract).
            persistence: Optional persistence for caching parse results.

        Returns:
            A ResponseMessage with the model's response.
        """
        processed_prompt = prompt.as_platform_request(model)
        # Create a standard span with AgentServerContext
        with self.kernel.ctx.start_span("reducto_generate_response") as span:
            span.set_attribute("model", model)
            span.set_attribute("model_provider", "reducto")

            try:
                match prompt.operation:
                    case "parse":
                        return await self._parse(prompt=processed_prompt)
                    case "classify":
                        return await self._classify(prompt=processed_prompt)
                    case "extract":
                        return await self._extract(prompt)
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

    def _get_api_key(self) -> str:
        """Get the Reducto API key, raising if not configured."""
        if self._parameters.reducto_api_key is None:
            raise ValueError("Reducto API key is required")
        return self._parameters.reducto_api_key.get_secret_value()

    async def _parse(self, prompt: ReductoPrompt) -> ResponseMessage:
        """Parse a document using sema4ai-docint extraction service directly."""
        from pathlib import Path

        from agent_platform.server.data_frames.data_reader import get_file_metadata
        from agent_platform.server.file_manager.utils import url_to_fs_path
        from agent_platform.server.storage.option import StorageService

        # Get the file metadata using file_ref
        storage = StorageService.get_instance()
        file_metadata = await get_file_metadata(
            user_id=self.kernel.user.user_id,
            thread_id=self.kernel.thread.thread_id,
            storage=storage,
            file_ref=prompt.file_name,
        )

        # Convert the file URL to a local filesystem path
        if not file_metadata.file_path:
            raise ValueError(f"File path not available for: {prompt.file_name}")

        local_file_path = Path(url_to_fs_path(file_metadata.file_path))

        # Extract parse options
        full_output = False
        if prompt.parse_options:
            full_output = prompt.parse_options.full_output

        # Upload and parse the document using the extraction service
        reducto_id = await self.extraction_service.upload(local_file_path)
        parse_response = await self.extraction_service.parse(reducto_id)

        return self.parsers.parse_response(parse_response, full_output)

    async def _extract(self, prompt: ReductoPrompt) -> ResponseMessage:
        """Extract data from a document using build_extraction_service.extract_with_schema."""
        import json
        from pathlib import Path

        from agent_platform.server.data_frames.data_reader import get_file_metadata
        from agent_platform.server.file_manager.utils import url_to_fs_path
        from agent_platform.server.storage.option import StorageService

        extract_options = prompt.extract_options
        if extract_options is None:
            raise ValueError("Extract options are required for extract operation")

        # Get the file metadata using file_ref
        storage = StorageService.get_instance()
        file_metadata = await get_file_metadata(
            user_id=self.kernel.user.user_id,
            thread_id=self.kernel.thread.thread_id,
            storage=storage,
            file_ref=prompt.file_name,
        )

        if not file_metadata.file_path:
            raise ValueError(f"File path not available for: {prompt.file_name}")

        local_file_path = Path(url_to_fs_path(file_metadata.file_path))

        if isinstance(extract_options.extraction_schema, str):
            extraction_schema = json.loads(extract_options.extraction_schema)
        else:
            extraction_schema = extract_options.extraction_schema

        extract_resp = await self.extraction_service.extract_with_schema(
            local_file_path,
            extraction_schema,
            prompt=prompt.system_prompt,
            extraction_config=extract_options.extraction_config,
            start_page=extract_options.start_page,
            end_page=extract_options.end_page,
        )

        return self.parsers.parse_response(extract_resp)

    async def _classify(self, prompt: ReductoPrompt) -> ResponseMessage:
        """Classify a document by parsing it first, then using LLM delegation."""
        from pathlib import Path

        from openai.types.responses import (
            ResponseInputItemParam,
            ResponseInputTextParam,
        )
        from reducto.types.shared.parse_response import (
            ResultURLResult,
        )

        from agent_platform.server.data_frames.data_reader import get_file_metadata
        from agent_platform.server.file_manager.utils import url_to_fs_path
        from agent_platform.server.storage.option import StorageService

        if self._delegate is None:
            raise ValueError("Delegate client is required for classify operation")
        if prompt.system_prompt is None:
            raise ValueError("System prompt is required for classify operation")

        # Get the file metadata and local path
        storage = StorageService.get_instance()
        file_metadata = await get_file_metadata(
            user_id=self.kernel.user.user_id,
            thread_id=self.kernel.thread.thread_id,
            storage=storage,
            file_ref=prompt.file_name,
        )

        if not file_metadata.file_path:
            raise ValueError(f"File path not available for: {prompt.file_name}")

        local_file_path = Path(url_to_fs_path(file_metadata.file_path))

        # Upload and parse the document
        reducto_id = await self.extraction_service.upload(local_file_path)
        parse_resp = await self.extraction_service.parse(reducto_id)

        if isinstance(parse_resp.result, ResultURLResult):
            raise ValueError("Parse response is a URL result, cannot classify")

        # Trim to first 5 chunks
        chunks = parse_resp.result.chunks[:5]
        parsed_prompt_input = "\n".join([chunk.model_dump_json() for chunk in chunks])

        llm_messages: list[ResponseInputItemParam] = []
        llm_messages.append(
            {
                "type": "message",
                "role": "developer",
                "content": [ResponseInputTextParam(type="input_text", text=prompt.system_prompt)],
            }
        )
        llm_messages.append(
            {
                "type": "message",
                "role": "user",
                "content": [
                    ResponseInputTextParam(
                        type="input_text",
                        text="Reply with the answer only, nothing else." + parsed_prompt_input,
                    )
                ],
            }
        )

        import pprint

        logger.debug(
            "Classifying with OpenAI LLM: system prompt: %s, prompt messages: %s",
            prompt.system_prompt,
            pprint.pformat(llm_messages),
        )

        # make an openai call via Responses API
        return await self._delegate.generate_response(
            model="gpt-5-low",  # TODO: what is the "right" model for this? TBD would need testing
            prompt=OpenAIPrompt(
                input=llm_messages,
                tools=[],
                temperature=0.0,
                max_output_tokens=512,
            ),
        )


PlatformClient.register_platform_client("reducto", ReductoClient)
