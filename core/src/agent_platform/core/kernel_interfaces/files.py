from abc import ABC, abstractmethod

from agent_platform.core.files import UploadedFile


class FilesInterface(ABC):
    """Handles interaction with files uploaded during agent chat sessions."""

    @abstractmethod
    async def get_file_by_id(self, file_id: str) -> UploadedFile | None:
        """Get the path to a file by its ID."""
        pass
