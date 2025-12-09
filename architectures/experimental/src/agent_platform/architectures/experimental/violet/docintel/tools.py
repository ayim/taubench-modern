from __future__ import annotations

import logging
from typing import Annotated, Any

from agent_platform.architectures.experimental.violet.docintel.schema import (
    SchemaGenerator,
)
from agent_platform.architectures.experimental.violet.reducto import VioletReductoClient
from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.core import Kernel
from agent_platform.core.files.mime_types import DOCUMENT_MIME_TYPES
from agent_platform.core.integrations.settings.reducto import ReductoSettings
from agent_platform.core.kernel_interfaces.thread_state import (
    ThreadMessageWithThreadState,
)
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.utils import SecretString
from agent_platform.server.data_frames.data_reader import (
    _get_file_contents,
    get_file_metadata,
)
from agent_platform.server.storage.errors import IntegrationNotFoundError
from agent_platform.server.storage.option import StorageService

logger = logging.getLogger(__name__)


class VioletDocumentsInterface:
    """
    Exposes document tools (parse, extract, infer) to the Agent.
    """

    def __init__(
        self, kernel: Kernel, state: VioletState, message: ThreadMessageWithThreadState
    ) -> None:
        self.kernel = kernel
        self.state = state
        self.message = message
        self._enabled = False
        self._impl: _DocumentToolImplementations | None = None

    async def initialize(self) -> None:
        """
        Checks settings and file availability to decide if tools should be enabled.
        """
        storage = StorageService.get_instance()

        # 1. Check Agent Settings
        agent_settings = self.kernel.agent.extra.get("agent_settings", {})
        if agent_settings.get("document_intelligence") != "internal":
            self._enabled = False
            return

        # 2. Check Reducto Integration
        try:
            await storage.get_integration_by_kind("reducto")
        except IntegrationNotFoundError:
            self._enabled = False
            return

        # 3. Check for relevant files
        files = await storage.get_thread_files(
            thread_id=self.kernel.thread_state.thread_id,
            user_id=self.kernel.user.user_id,
        )
        has_docs = any(f.mime_type in DOCUMENT_MIME_TYPES for f in files)

        if has_docs:
            self._enabled = True
            self._impl = _DocumentToolImplementations(
                self.kernel, self.state, storage, self.message
            )

    @property
    def documents_system_prompt(self) -> str:
        """
        Generates a dynamic system prompt listing available documents and their states.
        """
        if not self._enabled:
            return ""

        cards = self.state.doc_int.cards
        if not cards:
            return ""

        summary = ["## Documents Available\n"]
        summary.append("The following documents are available for analysis:\n")

        for card in cards:
            status_str = card.status
            schema_status = "Schema Ready" if card.json_schema else "No Schema"

            # Formating size
            size_str = "Unknown size"
            if card.size_bytes:
                kb = card.size_bytes / 1024
                if kb < 1024:  # noqa: PLR2004
                    size_str = f"{kb:.1f} KB"
                else:
                    size_str = f"{kb / 1024:.1f} MB"

            summary.append(f"- **{card.file_ref}** ({card.mime_type}, {size_str})")
            summary.append(f"  Status: {status_str} | {schema_status}")

            # Hint to the LLM about available data
            if card.json_schema:
                summary.append("  (Structured data extraction is available for this file)")

        summary.append("\n**Tools Guidance:**")
        summary.append("- Use `extract_document_with_schema` for files with 'Schema Ready'.")
        summary.append("- Use `parse_document` for raw text access if extraction fails.")
        summary.append(
            "- If a schema is missing or poor, you can use `infer_schema` to generate one."
        )

        return "\n".join(summary) + "\n\n"

    def get_tools(self) -> tuple[ToolDefinition, ...]:
        if not self._enabled or not self._impl:
            return ()

        return (
            ToolDefinition.from_callable(self._impl.parse_document, name="parse_document"),
            ToolDefinition.from_callable(
                self._impl.extract_document_with_schema,
                name="extract_document_with_schema",
            ),
            ToolDefinition.from_callable(self._impl.infer_schema, name="infer_schema"),
        )


class _DocumentToolImplementations:
    """
    Actual implementation of the tools.
    """

    def __init__(
        self,
        kernel: Kernel,
        state: VioletState,
        storage: Any,
        message: ThreadMessageWithThreadState,
    ):
        self.kernel = kernel
        self.state = state
        self.storage = storage
        self.user_id = kernel.user.user_id
        self.thread_id = kernel.thread_state.thread_id
        self.message = message

    async def parse_document(
        self,
        file_ref: Annotated[str, "The filename to parse (e.g., 'invoice.pdf')."],
    ) -> dict[str, Any]:
        """
        Parse a document into unstructured text/markdown.
        """
        try:
            client, uploaded_doc = await self._upload_to_reducto(file_ref)

            # Runtime import for types
            from reducto.types import ParseRunParams

            # Basic parse
            response = await client.parse(
                parse_options=ParseRunParams(document_url="unset"),
                uploaded_document=uploaded_doc,
            )
            return response.model_dump()

        except Exception as exc:
            logger.exception(
                f"Tool execution failed: parse_document file_ref={file_ref} error={exc!s}"
            )
            return {"error": f"Parse failed: {exc!s}"}

    async def extract_document_with_schema(
        self,
        file_ref: Annotated[str, "The filename to extract data from."],
        generate_citations: Annotated[bool, "Generate citations?"] = True,
    ) -> dict[str, Any]:
        """
        Extract structured data using the schema attached to the document card.
        """
        try:
            # 1. Locate Schema (Single Source of Truth: state.doc_int)
            card = next((c for c in self.state.doc_int.cards if c.file_ref == file_ref), None)
            if not card or not card.json_schema:
                return {
                    "error": (
                        f"No schema found for {file_ref}. "
                        "Please use `infer_schema` or wait for markup to complete."
                    )
                }

            # 2. Upload
            client, uploaded_doc = await self._upload_to_reducto(file_ref)

            # 3. Extract
            extract_opts = self._build_extract_options(
                schema=card.json_schema, citations=generate_citations
            )

            raw_response = await client.extract(
                extract_options=extract_opts,
                uploaded_document=uploaded_doc,
            )

            response_data = raw_response.model_dump()
            result_payload = self._pick_first_payload(response_data.get("result"))
            citations_payload = self._pick_first_payload(response_data.get("citations"))

            # 4. Auto-create DataFrames
            data_frames_created = await self._create_data_frames_from_arrays(
                result_payload if isinstance(result_payload, dict) else {},
                file_ref=file_ref,
            )

            return {
                "result": result_payload,
                "citations": citations_payload,
                "data_frames_created": data_frames_created,
                "schema_used": card.json_schema,
                "job_id": response_data.get("job_id"),
            }

        except Exception as exc:
            logger.exception(
                "Tool execution failed: extract_document_with_schema"
                f" file_ref={file_ref} error={exc!s}"
            )
            return {"error": f"Extraction failed: {exc!s}"}

    async def infer_schema(
        self,
        file_ref: Annotated[str, "The filename to infer a schema for."],
        instructions: Annotated[str, "Optional guidance."] = "",
    ) -> dict[str, Any]:
        """
        Manually trigger schema inference via tool.
        """
        # 1. Validate existence
        card = next((c for c in self.state.doc_int.cards if c.file_ref == file_ref), None)
        if not card:
            return {"error": f"File {file_ref} not found in document cards."}

        # 2. Delegate to the Generator we built earlier
        generator = SchemaGenerator(self.kernel, self.state)

        return await generator.infer_and_apply(
            card, message=self.message, instructions=instructions
        )

    # --- Helpers ---

    async def _upload_to_reducto(self, file_ref: str):
        # Fetch Metadata
        meta = await get_file_metadata(
            user_id=self.user_id,
            thread_id=self.thread_id,
            storage=self.storage,
            file_ref=file_ref,
        )
        # Fetch Content
        content = await _get_file_contents(self.user_id, self.thread_id, self.storage, meta)

        # Get Client
        integration = await self.storage.get_integration_by_kind("reducto")
        settings = integration.settings
        if not isinstance(settings, ReductoSettings):
            raise ValueError("Invalid Reducto configuration")

        api_key = (
            settings.api_key.get_secret_value()
            if isinstance(settings.api_key, SecretString)
            else str(settings.api_key)
        )

        client = VioletReductoClient(api_url=settings.endpoint, api_key=api_key)
        uploaded = await client.upload((meta.file_ref, content))

        return client, uploaded

    def _build_extract_options(self, schema: dict, citations: bool):
        from reducto.types import ExtractRunParams
        from reducto.types.shared_params.base_processing_options import (
            BaseProcessingOptions,
            Chunking,
        )

        # Simplified options construction
        return ExtractRunParams(
            document_url="unset",
            schema=schema,
            options=BaseProcessingOptions(chunking=Chunking(chunk_mode="disabled")),
            generate_citations=citations,
        )

    def _pick_first_payload(self, payload: Any) -> Any:
        """Normalize extraction payloads to a single dict when possible."""
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                return first
        return payload

    async def _create_data_frames_from_arrays(  # noqa: C901
        self,
        extraction_result: dict[str, Any],
        *,
        file_ref: str,
    ) -> list[dict[str, Any]]:
        """Create data frames for top-level array-of-object properties."""
        created: list[dict[str, Any]] = []
        if not extraction_result or not isinstance(extraction_result, dict):
            return created

        try:
            from agent_platform.server.kernel.data_frames import (
                create_data_frame_from_columns_and_rows,
            )
            from sema4ai.common.text import slugify

            for key, value in extraction_result.items():
                if not isinstance(value, list) or not value:
                    continue
                if not all(isinstance(item, dict) for item in value):
                    continue

                all_keys: set[str] = set()
                for item in value:
                    all_keys.update(item.keys())
                columns = sorted(all_keys)
                rows: list[list[Any]] = []
                for item in value:
                    row = []
                    for col in columns:
                        row.append(item.get(col))
                    rows.append(row)

                base_name = slugify(f"{file_ref}_{key}").replace("-", "_")
                if not base_name:
                    base_name = f"{slugify(key) or 'extracted'}"
                candidate = base_name
                suffix = 1
                storage = self.storage
                existing_names = {
                    df.name for df in await storage.list_data_frames(thread_id=self.thread_id)
                }
                while candidate in existing_names:
                    candidate = f"{base_name}_{suffix:02d}"
                    suffix += 1

                df = await create_data_frame_from_columns_and_rows(
                    columns=columns,
                    rows=rows,
                    name=candidate,
                    user_id=self.user_id,
                    agent_id=self.kernel.thread.agent_id,
                    thread_id=self.thread_id,
                    storage=storage,
                    description=f"Auto-created from extracted array '{key}' in {file_ref}",
                    input_id_type="in_memory",
                )
                created.append({"name": df.name, "data_frame_id": df.data_frame_id})
        except Exception:
            logger.exception(f"Auto data frame creation failed file_ref={file_ref}")

        return created
