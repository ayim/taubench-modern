from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, Literal

from structlog.stdlib import get_logger

from agent_platform.core.files.mime_types import DOCUMENT_MIME_TYPES
from agent_platform.core.kernel import DocumentsInterface
from agent_platform.core.semantic_data_model.types import SemanticDataModel
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

if TYPE_CHECKING:
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.kernel_interfaces.documents import DocumentArchState
    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)

# Constants for file size formatting
_BYTES_PER_KB = 1024
_KB_PER_MB = 1024


def _format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human-readable KB or MB.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted string like "1.5 MB" or "234 KB"
    """
    size_kb = size_bytes / _BYTES_PER_KB
    if size_kb < _KB_PER_MB:
        return f"{size_kb:.1f} KB"
    size_mb = size_kb / _KB_PER_MB
    return f"{size_mb:.1f} MB"


@dataclass(frozen=True)
class ResolvedSchema:
    """A schema resolved and ready for use by document tools.

    Unifies SDM-sourced schemas and dynamically generated schemas
    into a single representation that extract_document can consume
    without needing to know where the schema came from.
    """

    name: str
    json_schema: dict[str, Any]
    system_prompt: str = field(default="")
    extraction_config: dict[str, Any] = field(default_factory=dict)
    source: Literal["sdm", "generated"] = field(default="generated")
    extraction_enabled: bool = field(default=True)


class SchemaRegistry(ABC):
    """Interface for schema lookup and registration."""

    @abstractmethod
    def get(self, name: str) -> ResolvedSchema:
        """Look up a schema by name (case-insensitive). Raises KeyError if not found."""

    @abstractmethod
    def list_names(self) -> list[str]:
        """List all available schema names (original casing)."""

    @abstractmethod
    def add(self, name: str, schema: ResolvedSchema) -> None:
        """Register a new schema (e.g. from generate_schema)."""


class AgentServerDocumentsInterface(DocumentsInterface, UsesKernelMixin, SchemaRegistry):
    """Handles interaction with documents.

    This interface provides document management capabilities to the agent platform,
    following the same pattern as AgentServerDataFramesInterface.
    """

    def __init__(self) -> None:
        super().__init__()

        self._documents: list[UploadedFile] = []
        self._document_tools: tuple[ToolDefinition, ...] = ()
        # Not thread-safe
        self._schemas: dict[str, ResolvedSchema] = {}

    # -- SchemaRegistry implementation --

    def get(self, name: str) -> ResolvedSchema:
        """Look up a schema by name. Raises KeyError if not found."""
        return self._schemas[name]

    def list_names(self) -> list[str]:
        """List all available schema names."""
        return [s.name for s in self._schemas.values()]

    def add(self, name: str, schema: ResolvedSchema) -> None:
        """Register a new schema."""
        self._schemas[name] = schema

    async def _has_reducto(self) -> bool:
        from agent_platform.server.storage.errors import IntegrationNotFoundError

        logger.info("Checking for Reducto integration")
        try:
            integration = await self.kernel.storage.get_integration_by_kind(kind="reducto")
            logger.info("Reducto integration found", integration_id=integration.id)
            return True
        except IntegrationNotFoundError as e:
            logger.warning("Reducto integration NOT found", error=str(e))
            return False
        except Exception as e:
            logger.error(
                "Unexpected error checking for Reducto",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def is_enabled(self) -> bool:
        """Returns True if we have the ability to use Documents. This is foundational;
        do we have the ability to use Documents rather than the choice to add
        Document tools?
        """
        doc_int_agent_setting = self.kernel.agent.extra.get("document_intelligence", "v2.1")

        if doc_int_agent_setting != "v2.1":
            logger.warning(
                "Agent is already using document intelligence",
                current_value=doc_int_agent_setting,
            )
            return False

        # We are enabled only if we have config to talk to Reducto.
        has_reducto = await self._has_reducto()
        logger.info("Documents enabled check result", has_reducto=has_reducto)
        return has_reducto

    @staticmethod
    def _resolve_sdm_schemas(sdms: Sequence[SemanticDataModel]) -> dict[str, ResolvedSchema]:
        """Convert SDM schema info into a dict of ResolvedSchema keyed by lowercased name."""
        from agent_platform.core.semantic_data_model.schemas import Schema

        result: dict[str, ResolvedSchema] = {}
        for sdm in sdms:
            if not sdm.schemas:
                continue
            schema: Schema
            for schema in sdm.schemas:
                doc_ext = schema.document_extraction
                resolved = ResolvedSchema(
                    name=schema.name,
                    json_schema=schema.json_schema,
                    system_prompt=(doc_ext.system_prompt if doc_ext and doc_ext.system_prompt else ""),
                    extraction_config=(doc_ext.configuration if doc_ext and doc_ext.configuration else {}),
                    source="sdm",
                    extraction_enabled=doc_ext is not None,
                )
                result[schema.name] = resolved
        return result

    async def _collect_sdm_schemas(self, storage: BaseStorage) -> None:
        """Re-fetch SDM schemas and merge with existing generated schemas.

        SDM schemas are fetched fresh each step. Previously generated schemas
        (source="generated") are preserved and take priority on name collisions.
        """
        sdm_infos = await storage.list_semantic_data_models(
            agent_id=self.kernel.agent.agent_id,
            thread_id=self.kernel.thread_state.thread_id,
        )

        # Rebuild: SDM schemas first, then overlay generated (there should be no conflicts)
        sdm_schemas = self._resolve_sdm_schemas([sdm_info["semantic_data_model"] for sdm_info in sdm_infos])
        generated = {k: v for k, v in self._schemas.items() if v.source == "generated"}
        sdm_schemas.update(generated)

        # Save the updated dict of Schemas (not threadsafe but we're not getting called concurrently)
        self._schemas = sdm_schemas

    async def step_initialize(self, *, state: DocumentArchState, storage: BaseStorage | None = None) -> None:
        """Initialize documents for the current step.

        Args:
            storage: Optional storage instance to use
            state: The architecture state containing documents configuration
        """
        from agent_platform.server.storage.option import StorageService

        # If documents are not enabled, do nothing.
        is_enabled = await self.is_enabled()
        logger.info(
            "Documents step_initialize",
            is_enabled=is_enabled,
            thread_id=self.kernel.thread_state.thread_id,
        )
        if not is_enabled:
            return

        storage = StorageService.get_instance() if storage is None else storage
        self._documents = await self._documents_in_context(storage)

        # Collect all schemas (SDM + previously generated)
        await self._collect_sdm_schemas(storage)

        logger.info(
            "Documents found in context",
            num_documents=len(self._documents),
            document_refs=[doc.file_ref for doc in self._documents] if self._documents else [],
        )

        # Create document tools instance
        document_tools = _DocumentTools(
            user=self.kernel.user,
            tid=self.kernel.thread_state.thread_id,
            storage=storage,
            kernel=self.kernel,
            schema_registry=self,
        )

        # Register tools only if we have documents
        if self._documents:
            self._document_tools = (
                ToolDefinition.from_callable(
                    document_tools.parse_document,
                    name="parse_document",
                ),
                ToolDefinition.from_callable(
                    document_tools.generate_schema,
                    name="generate_schema",
                ),
                ToolDefinition.from_callable(
                    document_tools.extract_document,
                    name="extract_document",
                ),
            )
            state.documents_tools_state = "enabled"
            logger.info("Document tools registered", num_tools=len(self._document_tools))
        else:
            self._document_tools = ()
            state.documents_tools_state = ""
            logger.info("No documents found, document tools not registered")

    def get_document_tools(self) -> tuple[ToolDefinition, ...]:
        """Get the list of document tools."""
        return self._document_tools

    @property
    def documents_summary(self) -> str:
        """Get a summary of the documents available in the current thread."""
        if not self._documents:
            return "You have no documents to work with."

        summary = ["Documents details:\n"]
        for doc in self._documents:
            doc_summary = [f"### Document: {doc.file_ref}"]
            doc_summary.append(f"MIME Type: {doc.mime_type}")
            if doc.file_size_raw:
                doc_summary.append(f"Size: {_format_file_size(doc.file_size_raw)}")
            summary.append("\n".join(doc_summary))

        return "\n\n".join(summary)

    @property
    def documents_system_prompt(self) -> str:
        """Get a prompt to be added to the system prompt for documents."""
        if not self._documents:
            return ""

        from textwrap import dedent

        prompt = dedent("""
        ## Documents Available
        The following documents have been uploaded and are available for parsing and analysis.
        Use the `parse_document` tool to create a textual representation of a document.
        Use the `generate_schema` tool to create a schema based on a document.
        Use the `extract_document` tool to extract structured data from a document using a schema.

        """)
        prompt += self.documents_summary
        prompt += "\n\n"
        prompt += dedent("""
        **Tips for working with documents:**
        - Use `parse_document(file_name="filename.pdf")` to summarize a document or answer
          general questions about a document. If force_reload is False, the result will pulled from cache.
          After *each* `parse_document` call, you must respond with:
          - A short summary of what the document contains.
          - For each table found give it a title if it doesn't have one, highlight it, then describe it in one sentence.
          Make sure tables that extend to multiple pages are counted as one table.
        - Use `generate_schema(file_name="filename.pdf")` to automatically generate
          a JSON schema describing the document's structure that can be used with `extract_document`.
          If force_reload is False, the result will pulled from cache.
        - Use `extract_document(schema_name="My Schema", file_name="filename.pdf")` to
          extract structured JSON data from the file using the Schema with the provided name.
          The returned data will conform to the shape of the given Schema.
          If force_reload is False and input parameters are the same, the result
          will pulled from cache.
        - The content includes text, tables, figures, and document structure.
        - After extracting, you can create data frames from the content using
          `create_data_frame_from_json`.
        """)

        return prompt

    async def _documents_in_context(self, storage: BaseStorage | None) -> list[UploadedFile]:
        from agent_platform.server.storage.option import StorageService

        storage = StorageService.get_instance() if storage is None else storage
        documents: list[UploadedFile] = []
        try:
            # Fetch all files.
            files = await storage.get_thread_files(
                thread_id=self.kernel.thread_state.thread_id, user_id=self.kernel.user.user_id
            )
            logger.info(
                "Files in thread",
                num_files=len(files),
                file_mime_types=[f.mime_type for f in files],
            )

            files = [file for file in files if file.mime_type in DOCUMENT_MIME_TYPES]

            logger.info(
                "Documents after filtering",
                num_documents=len(files),
                supported_mime_types=list(DOCUMENT_MIME_TYPES),
            )

            return files
        except Exception as e:
            logger.exception("Error getting documents", error=e)
            return documents


class _DocumentTools:
    """Helper class for document tool implementations."""

    def __init__(
        self,
        user: AuthedUser,
        tid: str,
        storage: BaseStorage,
        kernel: Kernel,
        schema_registry: SchemaRegistry,
    ):
        self._user = user
        self._tid = tid
        self._storage = storage
        self._kernel = kernel
        self._schema_registry = schema_registry

    async def _generate_schema_name(self, file_name: str) -> str:
        """Generate a unique schema name using an LLM call + timestamp suffix.

        The LLM produces a short 5-15 char descriptive name from the filename,
        and a timestamp is appended for uniqueness.
        """
        import re
        from datetime import datetime

        from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
        from agent_platform.core.responses.content import ResponseTextContent

        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

        try:
            platform, model = await self._kernel.get_platform_and_model(model_type="llm")
            prompt = Prompt(
                system_instruction=(
                    "Generate a single short name (5-15 characters) for a document schema. "
                    "Use only lowercase letters, numbers, and underscores. "
                    "The name should describe the document type. "
                    "Output only the name, nothing else."
                ),
                messages=[
                    PromptUserMessage(
                        content=[
                            PromptTextContent(text=f"Filename: {file_name}"),
                        ]
                    ),
                ],
                temperature=0.2,
                max_output_tokens=200,
            )
            response = await platform.generate_response(prompt, model)
            text_parts = [
                content.text.strip() for content in response.content if isinstance(content, ResponseTextContent)
            ]
            raw_name = "".join(text_parts).strip()
            # Sanitize: keep only lowercase alphanumeric + underscores, truncate to 15 chars
            clean_name = re.sub(r"[^a-z0-9_]", "", raw_name.lower())[:15]
            if len(clean_name) < 3:
                raise ValueError("LLM returned too short a name")
            return f"{clean_name}_{timestamp}"
        except Exception:
            # Fallback: use filename stem
            from pathlib import Path

            stem = re.sub(r"[^a-z0-9_]", "", Path(file_name).stem.lower())[:15] or "schema"
            return f"{stem}_{timestamp}"

    async def parse_document(
        self,
        file_name: Annotated[
            str,
            "The name of the file to parse (e.g., 'invoice.pdf' or 'document.docx').",
        ],
        force_reload: Annotated[
            bool,
            "If True, bypass cache and force re-parsing of the document.",
        ] = False,
    ) -> dict[str, Any]:
        """Parse a document into a structured format using Reducto.

        This tool extracts structured content from documents (PDF, DOCX, etc.) including:
        - Text content organized by sections and hierarchy
        - Tables with preserved structure
        - Figures and images with descriptions
        - Metadata about the document

        The parsed result is automatically cached in thread storage. Subsequent calls
        with the same file_name will return the cached result unless force_reload is True.

        Args:
            file_ref: The filename of the document to parse
            force_reload: If True, bypass cache and re-parse the document

        Returns:
            A dictionary containing the parsed document content and metadata
        """
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.server.kernel.kernel import AgentServerKernel
        from agent_platform.server.storage.errors import IntegrationNotFoundError

        try:
            # Verify we have an AgentServerKernel
            kernel = self._kernel
            if not isinstance(kernel, AgentServerKernel):
                return {
                    "error_code": "invalid_kernel",
                    "message": "Kernel must be an AgentServerKernel instance",
                }

            # Get Reducto integration configuration to extract API key
            try:
                reducto_integration = await self._storage.get_integration_by_kind("reducto")
            except IntegrationNotFoundError:
                return {
                    "error_code": "reducto_not_configured",
                    "message": ("Reducto integration is not configured. Please configure it first."),
                }

            from agent_platform.core.integrations.settings.reducto import ReductoSettings

            if not isinstance(reducto_integration.settings, ReductoSettings):
                return {
                    "error_code": "invalid_reducto_config",
                    "message": "Reducto integration has invalid settings",
                }

            reducto_settings = reducto_integration.settings

            from agent_platform.core.utils import SecretString

            # Extract API key
            api_key = (
                reducto_settings.api_key.get_secret_value()
                if isinstance(reducto_settings.api_key, SecretString)
                else str(reducto_settings.api_key)
            )

            from agent_platform.server.document_intelligence import DirectKernelTransport
            from agent_platform.server.file_manager import FileManagerService

            file_manager = FileManagerService.get_instance(self._storage)
            transport = DirectKernelTransport(
                storage=self._storage,
                file_manager=file_manager,
                thread_id=kernel.thread.thread_id,
                agent_id=kernel.agent.agent_id,
                user_id=self._user.user_id,
                server_context=kernel.ctx,
            )

            # Build DIService with file-based persistence (same as UI endpoint)
            from sema4ai_docint import build_di_service
            from sema4ai_docint.services.persistence import ChatFilePersistenceService
            from sema4ai_docint.services.persistence.file import AgentServerChatFileAccessor

            async with build_di_service(
                datasource=None,
                sema4_api_key=api_key,
                agent_server_transport=transport,
                persistence_service=ChatFilePersistenceService(
                    chat_file_accessor=AgentServerChatFileAccessor(self._tid, transport),
                ),
            ) as di_service:
                # Parse using DIService with automatic caching
                doc = await di_service.document_v2.new_document(file_name)
                parse_response = await di_service.document_v2.parse(doc, force_reload=force_reload)

                return parse_response.model_dump()

        except PlatformHTTPError as e:
            return {
                "error_code": str(e.response.code),
                "message": e.response.message,
            }
        except Exception as e:
            logger.exception("Error parsing document", error=e, file_name=file_name)
            return {
                "error_code": "parse_error",
                "message": f"Failed to parse document: {e!s}",
            }

    async def generate_schema(
        self,
        file_name: Annotated[
            str,
            "The name of the file to generate a schema from (e.g., 'invoice.pdf' or 'document.docx').",
        ],
        start_page: Annotated[
            int | None,
            "Optional starting page number (1-indexed) for page range extraction.",
        ] = None,
        end_page: Annotated[
            int | None,
            "Optional ending page number (1-indexed) for page range extraction.",
        ] = None,
        user_prompt: Annotated[
            str | None,
            "Optional additional instructions to guide the schema generation process.",
        ] = None,
        force_reload: Annotated[
            bool,
            "If True, bypass cache and force re-generation of the schema.",
        ] = False,
    ) -> dict[str, Any]:
        """Generate a JSON Schema from a document by analyzing its structure and content.

        This tool analyzes a document (PDF, DOCX, Excel, images, etc.) and generates a JSON Schema
        that describes the document's data structure.

        The generated schema is automatically cached in thread storage. Subsequent calls
        with the same file_ref will return the cached result unless force_reload is True.

        Returns:
            The generated JSON Schema as a dict.
        """
        from agent_platform.server.storage.errors import IntegrationNotFoundError

        try:
            kernel = self._kernel
            # Get Reducto integration configuration to extract API key
            try:
                reducto_integration = await self._storage.get_integration_by_kind("reducto")
            except IntegrationNotFoundError:
                raise Exception("Reducto integration is not configured. Please configure it first.") from None

            from agent_platform.core.integrations.settings.reducto import ReductoSettings

            if not isinstance(reducto_integration.settings, ReductoSettings):
                raise Exception("Reducto integration has invalid settings")

            reducto_settings = reducto_integration.settings

            from agent_platform.core.utils import SecretString

            # Extract API key
            api_key = (
                reducto_settings.api_key.get_secret_value()
                if isinstance(reducto_settings.api_key, SecretString)
                else str(reducto_settings.api_key)
            )

            from agent_platform.server.document_intelligence import DirectKernelTransport
            from agent_platform.server.file_manager import FileManagerService

            file_manager = FileManagerService.get_instance(self._storage)
            transport = DirectKernelTransport(
                storage=self._storage,
                file_manager=file_manager,
                thread_id=kernel.thread.thread_id,
                agent_id=kernel.agent.agent_id,
                user_id=self._user.user_id,
                server_context=kernel.ctx,
            )

            # Build DIService with file-based persistence (same as parse_document)
            from sema4ai_docint import build_di_service
            from sema4ai_docint.services.persistence import ChatFilePersistenceService
            from sema4ai_docint.services.persistence.file import AgentServerChatFileAccessor

            async with build_di_service(
                datasource=None,
                sema4_api_key=api_key,
                agent_server_transport=transport,
                persistence_service=ChatFilePersistenceService(
                    chat_file_accessor=AgentServerChatFileAccessor(self._tid, transport),
                ),
            ) as di_service:
                import asyncio

                doc = await di_service.document_v2.new_document(file_name)

                # Run schema generation and name generation in parallel
                raw_schema, schema_name = await asyncio.gather(
                    di_service.document_v2.generate_schema(
                        doc,
                        force_reload=force_reload,
                        start_page=start_page,
                        end_page=end_page,
                        user_prompt=user_prompt,
                    ),
                    self._generate_schema_name(file_name),
                )

                self._schema_registry.add(
                    schema_name,
                    ResolvedSchema(name=schema_name, json_schema=raw_schema, source="generated"),
                )
                return {"schema_name": schema_name}
        except Exception as e:
            logger.exception("Error generating schema", error=e, file_name=file_name)
            raise e

    async def extract_document(
        self,
        schema_name: Annotated[
            str,
            """The name of the schema to use for extraction.

            The schema name is either:
            1. The schema_name returned by a previous generate_schema call
            2. The name of a Schema in a Semantic Data Model

            Do NOT pass a raw JSON schema. Use generate_schema first to get a named schema.
            """,
        ],
        file_name: Annotated[
            str,
            "The name of the file to extract (e.g., 'invoice.pdf' or 'document.docx').",
        ],
        start_page: Annotated[
            int | None,
            "Optional starting page number (1-indexed) for page range extraction.",
        ] = None,
        end_page: Annotated[
            int | None,
            "Optional ending page number (1-indexed) for page range extraction.",
        ] = None,
        system_prompt: Annotated[
            str | None,
            "Optional system prompt to help guide extraction.",
        ] = None,
        force_reload: Annotated[
            bool,
            "If True, bypass cache and force re-extraction of the document.",
        ] = False,
    ) -> dict[str, Any]:
        """Extract structured data from a document using a JSON Schema.

        This tool extracts data from a document (PDF, DOCX, etc.) using a schema referenced
        by name from an SDM or from a previous generate_schema tool result.

        The extracted result is automatically cached in thread storage. Subsequent calls
        with the same parameters will return the cached result unless force_reload is True or the
        parameters are different.

        Returns:
            A dictionary containing the extracted data matching the provided schema
        """
        from sema4ai_docint import build_di_service
        from sema4ai_docint.services.persistence import ChatFilePersistenceService
        from sema4ai_docint.services.persistence.file import AgentServerChatFileAccessor

        from agent_platform.core.integrations.settings.reducto import ReductoSettings
        from agent_platform.core.utils import SecretString
        from agent_platform.server.document_intelligence import DirectKernelTransport
        from agent_platform.server.file_manager import FileManagerService
        from agent_platform.server.storage.errors import IntegrationNotFoundError

        if not schema_name:
            raise ValueError("schema_name is required")

        extraction_config: dict[str, Any] | None = None

        try:
            resolved = self._schema_registry.get(schema_name)
        except KeyError:
            available_names = self._schema_registry.list_names()
            available_str = ", ".join(f"'{n}'" for n in available_names) if available_names else "none"
            raise ValueError(
                f"No schema named '{schema_name}' was found. "
                f"Available schemas: {available_str}. "
                "You can use the generate_schema tool to create a new schema from a document."
            ) from None

        if not resolved.extraction_enabled:
            raise ValueError(
                f"Schema '{resolved.name}' was found but it is not enabled for use "
                "with Document Intelligence. Please enable document extraction on this "
                "schema in the Semantic Data Model configuration."
            )

        schema = resolved.json_schema
        if resolved.system_prompt:
            system_prompt = resolved.system_prompt
        if resolved.extraction_config:
            extraction_config = resolved.extraction_config

        # Sanity check -- Reducto requires a top-level object or array
        if schema.get("type") not in ("object", "array"):
            raise ValueError("The top-level element of the JSON schema must be of type 'object' or 'array'.")

        kernel = self._kernel

        # Load the Reducto configuration
        try:
            reducto_integration = await self._storage.get_integration_by_kind("reducto")
        except IntegrationNotFoundError:
            raise ValueError("Reducto integration is not configured. Please configure it first.") from None

        if not isinstance(reducto_integration.settings, ReductoSettings):
            raise ValueError("Reducto integration has invalid settings")

        reducto_settings = reducto_integration.settings

        api_key = (
            reducto_settings.api_key.get_secret_value()
            if isinstance(reducto_settings.api_key, SecretString)
            else str(reducto_settings.api_key)
        )

        file_manager = FileManagerService.get_instance(self._storage)
        transport = DirectKernelTransport(
            storage=self._storage,
            file_manager=file_manager,
            thread_id=kernel.thread.thread_id,
            agent_id=kernel.agent.agent_id,
            user_id=self._user.user_id,
            server_context=kernel.ctx,
        )

        async with build_di_service(
            datasource=None,
            sema4_api_key=api_key,
            agent_server_transport=transport,
            persistence_service=ChatFilePersistenceService(
                chat_file_accessor=AgentServerChatFileAccessor(self._tid, transport),
            ),
        ) as di_service:
            doc = await di_service.document_v2.new_document(file_name)
            result = await di_service.document_v2.extract_document(
                doc,
                schema,
                force_reload=force_reload,
                extraction_config=extraction_config,
                start_page=start_page,
                end_page=end_page,
                prompt=system_prompt,
            )

            # Do not return the citations from this tool. We include them in the caching layer of
            # DIService, but they are bloat in the context of the agent.
            if result.citations is not None:
                result.citations = None

            return result.model_dump()
