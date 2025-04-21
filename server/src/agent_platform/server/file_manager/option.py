from typing import ClassVar

from agent_platform.server.constants import SystemConfig
from agent_platform.server.file_manager.base import BaseFileManager
from agent_platform.server.file_manager.cloud import CloudFileManager
from agent_platform.server.file_manager.local import LocalFileManager
from agent_platform.server.storage import BaseStorage


class FileManagerService:
    """Service for file manager using a singleton pattern."""

    _instances: ClassVar[dict[str, BaseFileManager]] = {}

    @classmethod
    def get_instance(
        cls,
        storage: BaseStorage,
        manager_type: str | None = None,
    ) -> BaseFileManager:
        """Get the singleton instance of the file manager service.

        Args:
            storage: The storage service instance.
            manager_type: The type of file manager to use. If None, the type is
                determined from configuration.

        Returns:
            The file manager service instance.
        """
        # Get the manager type from config if not specified
        if manager_type is None:
            manager_type = SystemConfig.file_manager_type

        # Create the instance if it doesn't exist
        if manager_type not in cls._instances:
            # Create the appropriate file manager
            if manager_type == "local":
                cls._instances[manager_type] = LocalFileManager(storage)
            elif manager_type == "cloud":
                cls._instances[manager_type] = CloudFileManager(storage)
            else:
                raise ValueError(f"Invalid file manager type: {manager_type}")

        return cls._instances[manager_type]

    @classmethod
    def reset(cls) -> None:
        """Reset all file manager instances (for testing)."""
        cls._instances = {}

    @classmethod
    def set_for_testing(cls, manager_type: str, manager: BaseFileManager) -> None:
        """Set a custom file manager implementation (for testing).

        Args:
            manager_type: The type of file manager to set.
            manager: The file manager implementation to use.
        """
        cls._instances[manager_type] = manager
