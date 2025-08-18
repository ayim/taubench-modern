from structlog import get_logger

from agent_platform.core.files import UploadedFile
from agent_platform.core.kernel import FilesInterface
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

logger = get_logger(__name__)


class AgentServerFilesInterface(FilesInterface, UsesKernelMixin):
    """Handles interaction with files uploaded during agent chat sessions."""

    async def get_file_by_id(self, file_id: str) -> UploadedFile | None:
        """Get the path to a file by its ID."""
        try:
            return await self.kernel.storage.get_file_by_id(file_id)
        except Exception:
            logger.exception(f"Error getting file by ID: {file_id}")
            return None
