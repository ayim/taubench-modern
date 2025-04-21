"""FastAPI dependencies used for injection."""

from typing import Annotated

from fastapi import Depends

from agent_platform.server.file_manager import BaseFileManager, FileManagerService
from agent_platform.server.storage import BaseStorage, StorageService

StorageDependency = Annotated[BaseStorage, Depends(StorageService.get_instance)]


def get_file_manager(storage: StorageDependency) -> BaseFileManager:
    """FastAPI dependency to provide the file manager service.

    This dependency explicitly depends on the storage dependency to ensure
    proper initialization order.

    Args:
        storage: The storage service instance (automatically injected).

    Returns:
        The file manager service instance.
    """
    return FileManagerService.get_instance(storage)


FileManagerDependency = Annotated[BaseFileManager, Depends(get_file_manager)]
