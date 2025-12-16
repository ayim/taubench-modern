from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from structlog.stdlib import get_logger

from agent_platform.core.files.mime_types import DOCUMENT_MIME_TYPES
from agent_platform.core.kernel import DocumentsInterface
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


class AgentServerDocumentsInterface(DocumentsInterface, UsesKernelMixin):
    """Handles interaction with documents.

    This interface provides document management capabilities to the agent platform,
    following the same pattern as AgentServerDataFramesInterface.
    """

    def __init__(self) -> None:
        super().__init__()

        self._documents: list[UploadedFile] = []
        self._document_tools: tuple[ToolDefinition, ...] = ()

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
        doc_int_agent_setting = self.kernel.agent.extra.get("document_intelligence", "")

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
        self._documents = await self.documents_in_context(storage)

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
        Use the `parse_document` tool to get the content from a document.
        Use the `generate_schema` tool to create a JSON schema from a document.

        """)
        prompt += self.documents_summary
        prompt += "\n\n"
        prompt += dedent("""
        **Tips for working with documents:**
        - Use `parse_document(file_ref="filename.pdf")` to get the content from
          a document
        - After parsing, you can create data frames from the content using
          `create_data_frame_from_json`.
        - The content includes text, tables, figures, and document structure
        """)

        return prompt

    async def documents_in_context(self, storage: BaseStorage | None) -> list[UploadedFile]:
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
    ):
        self._user = user
        self._tid = tid
        self._storage = storage
        self._kernel = kernel

    async def parse_document(
        self,
        file_ref: Annotated[
            str,
            (
                "The file reference to parse. This should be the filename only "
                "(e.g., 'invoice.pdf' or 'document.docx'), not a file ID or path."
            ),
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
        with the same file_ref will return the cached result unless force_reload is True.

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

            di_service = build_di_service(
                datasource=None,
                sema4_api_key=api_key,
                agent_server_transport=transport,
                persistence_service=ChatFilePersistenceService(
                    chat_file_accessor=AgentServerChatFileAccessor(self._tid, transport),
                ),
            )

            # Parse using DIService with automatic caching
            doc = await di_service.document_v2.new_document(file_ref)
            parse_response = await di_service.document_v2.parse(doc, force_reload=force_reload)

            # Convert response to LLM-friendly dictionary
            return parse_response.model_dump()

        except PlatformHTTPError as e:
            return {
                "error_code": str(e.response.code),
                "message": e.response.message,
            }
        except Exception as e:
            logger.exception("Error parsing document", error=e, file_ref=file_ref)
            return {
                "error_code": "parse_error",
                "message": f"Failed to parse document: {e!s}",
            }

    async def generate_schema(
        self,
        file_ref: Annotated[
            str,
            (
                "The file reference to generate a schema from. This should be the filename only "
                "(e.g., 'invoice.pdf' or 'document.docx')."
            ),
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

        Args:
            file_ref: The filename of the document to analyze
            model_schema: Optional reference schema to guide the structure (JSON string)
            start_page: Optional starting page for analysis (1-indexed, PDF/TIFF only)
            end_page: Optional ending page for analysis (1-indexed, PDF/TIFF only)
            user_prompt: Optional additional instructions for schema generation
            force_reload: If True, bypass cache and re-generate the schema

        Returns:
            The generated JSON Schema.
        """
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.server.storage.errors import IntegrationNotFoundError

        try:
            kernel = self._kernel
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

            # Build DIService with file-based persistence (same as parse_document)
            from sema4ai_docint import build_di_service
            from sema4ai_docint.services.persistence import ChatFilePersistenceService
            from sema4ai_docint.services.persistence.file import AgentServerChatFileAccessor

            di_service = build_di_service(
                datasource=None,
                sema4_api_key=api_key,
                agent_server_transport=transport,
                persistence_service=ChatFilePersistenceService(
                    chat_file_accessor=AgentServerChatFileAccessor(self._tid, transport),
                ),
            )

            # Generate schema using DIService with automatic caching
            doc = await di_service.document_v2.new_document(file_ref)
            schema = await di_service.document_v2.generate_schema(
                doc,
                force_reload=force_reload,
                start_page=start_page,
                end_page=end_page,
                user_prompt=user_prompt,
            )

            return schema

        except PlatformHTTPError as e:
            return {
                "error_code": str(e.response.code),
                "message": e.response.message,
            }
        except Exception as e:
            logger.exception("Error generating schema", error=e, file_ref=file_ref)
            return {
                "error_code": "schema_generation_error",
                "message": f"Failed to generate schema: {e!s}",
            }
