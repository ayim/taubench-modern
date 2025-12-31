from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .base import ResponseMessage


@runtime_checkable
class DirectTransport(Protocol):
    """Minimal protocol for direct communication with the agent server."""

    @property
    def thread_id(self) -> str | None:
        """The thread ID for contextual operations.

        Returns:
            str | None: Thread ID if available, None otherwise
        """
        ...

    @property
    def agent_id(self) -> str | None:
        """The agent ID for contextual operations.

        Returns:
            str | None: Agent ID if available, None otherwise
        """
        ...

    async def prompts_generate(self, payload: dict[str, Any]) -> "ResponseMessage":
        """Generate a prompt response using the agent server.

        This is the primary method used by AgentServerClient for all LLM
        interactions. It sends a prompt payload to the agent server and
        returns the generated response.

        Args:
            payload: The prompt payload containing:
                - prompt: The system/user prompt configuration
                - messages: Optional conversation history
                - model_config: Optional model configuration (temperature, etc.)

        Returns:
            ResponseMessage: The generated response with content, role, usage, etc.
        """
        ...

    def get_file(
        self, name: str, thread_id: str | None = None
    ) -> AbstractAsyncContextManager[Path]:
        """Get a file by reference as an async context manager.

        Retrieves a file from the agent server's storage. For remote files
        that are downloaded to temp locations, the file is automatically
        cleaned up when the context exits.

        Args:
            name: The file reference/name to retrieve
            thread_id: Optional thread ID override. If not provided,
                uses the transport's thread_id

        Yields:
            Path: Path to the file on the local filesystem
        """
        ...

    async def upload_file_bytes(
        self,
        *,
        thread_id: str,
        file_ref: str,
        content: bytes,
        mime_type: str = "text/plain",
    ) -> None:
        """Upload file bytes into a thread.

        Args:
            thread_id: The thread ID to upload to
            file_ref: The file reference/name
            content: The file content as bytes
            mime_type: The MIME type of the file
        """
        ...

    async def list_file_refs(self, *, thread_id: str) -> list[str]:
        """List file references for a thread.

        Args:
            thread_id: The thread ID

        Returns:
            List of file references
        """
        ...

    async def get_file_url(self, *, thread_id: str, file_ref: str) -> str | None:
        """Get file URL by reference.

        Args:
            thread_id: The thread ID
            file_ref: The file reference

        Returns:
            File URL/URI or None if not found
        """
        ...
