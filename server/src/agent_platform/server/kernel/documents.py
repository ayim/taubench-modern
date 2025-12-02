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
        logger.info("Checking if documents are enabled")

        # Check agent settings first
        agent_settings = self.kernel.agent.extra.get("agent_settings", {})
        doc_int_agent_setting = agent_settings.get("document_intelligence", "")

        logger.info(
            "Agent settings check",
            document_intelligence_setting=doc_int_agent_setting,
            all_agent_settings=agent_settings,
        )

        # Require explicit opt-in.
        if doc_int_agent_setting != "internal":
            logger.warning(
                "Documents disabled: agent setting not 'internal'",
                current_value=doc_int_agent_setting,
            )
            return False

        # We are enabled only if we have config to talk to Reducto.
        has_reducto = await self._has_reducto()
        logger.info("Documents enabled check result", has_reducto=has_reducto)
        return has_reducto

    async def step_initialize(
        self, *, state: DocumentArchState, storage: BaseStorage | None = None
    ) -> None:
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
        Use the `parse_document` tool to get the content from these documents.

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
    ) -> dict[str, Any]:
        """Parse a document into a structured format using Reducto.

        This tool extracts structured content from documents (PDF, DOCX, etc.) including:
        - Text content organized by sections and hierarchy
        - Tables with preserved structure
        - Figures and images with descriptions
        - Metadata about the document

        Args:
            file_ref: The filename of the document to parse

        Returns:
            A dictionary containing the parsed document content and metadata
        """
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.platforms.reducto.client import ReductoClient
        from agent_platform.core.platforms.reducto.parameters import (
            ReductoPlatformParameters,
        )
        from agent_platform.core.platforms.reducto.prompts import ReductoPrompt
        from agent_platform.core.utils import SecretString
        from agent_platform.server.data_frames.data_reader import (
            _get_file_contents,
            get_file_metadata,
        )
        from agent_platform.server.storage.errors import IntegrationNotFoundError

        try:
            # Get the file metadata and contents
            file_metadata = await get_file_metadata(
                user_id=self._user.user_id,
                thread_id=self._tid,
                storage=self._storage,
                file_ref=file_ref,
            )

            file_contents = await _get_file_contents(
                user_id=self._user.user_id,
                thread_id=self._tid,
                storage=self._storage,
                file_metadata=file_metadata,
            )

            # Get Reducto integration configuration
            try:
                reducto_integration = await self._storage.get_integration_by_kind("reducto")
            except IntegrationNotFoundError:
                return {
                    "error_code": "reducto_not_configured",
                    "message": (
                        "Reducto integration is not configured. Please configure it first."
                    ),
                }

            # Extract settings
            from agent_platform.core.integrations.settings.reducto import ReductoSettings

            if not isinstance(reducto_integration.settings, ReductoSettings):
                return {
                    "error_code": "invalid_reducto_config",
                    "message": "Reducto integration has invalid settings",
                }

            reducto_settings = reducto_integration.settings

            # Extract API key
            api_key = (
                reducto_settings.api_key.get_secret_value()
                if isinstance(reducto_settings.api_key, SecretString)
                else str(reducto_settings.api_key)
            )

            # Initialize Reducto client with kernel for telemetry
            reducto_client = ReductoClient(
                parameters=ReductoPlatformParameters(
                    reducto_api_url=reducto_settings.endpoint,
                    reducto_api_key=SecretString(api_key),
                ),
            )
            # Attach the kernel after initialization
            reducto_client.attach_kernel(self._kernel)

            # Create prompt for parsing
            prompt = ReductoPrompt(
                operation="parse",
                document_name=file_metadata.file_ref,
                document_bytes=file_contents,
            )

            # Generate response using Reducto
            response = await reducto_client.generate_response(
                prompt=prompt,
                model="default",  # Reducto doesn't use model selection
            )

            # Convert response to dictionary
            return response.model_dump()

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
