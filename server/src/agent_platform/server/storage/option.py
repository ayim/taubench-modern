from agent_platform.server.constants import SystemConfig
from agent_platform.server.storage.base import BaseStorage
from agent_platform.server.storage.postgres import PostgresStorage
from agent_platform.server.storage.sqlite import SQLiteStorage


class StorageService:
    """Service for storage using a singleton pattern."""

    _instance: BaseStorage | None = None

    @classmethod
    def get_instance(cls) -> BaseStorage:
        """Get the singleton instance of the storage service.

        Returns:
            The storage service instance.
        """
        if cls._instance is None:
            cls._instance = cls._initialize_storage()
        return cls._instance

    @classmethod
    def _initialize_storage(cls) -> BaseStorage:
        """Initialize the appropriate storage implementation based on configuration.

        Returns:
            The initialized storage service.
        """
        if SystemConfig.db_type == "postgres":
            return PostgresStorage()
        elif SystemConfig.db_type == "sqlite":
            return SQLiteStorage()
        else:
            raise ValueError(f"Unsupported DB type: {SystemConfig.db_type}")

    @classmethod
    def reset(cls) -> None:
        """Reset the storage instance (for testing)."""
        cls._instance = None

    @classmethod
    def set_for_testing(cls, storage: BaseStorage) -> None:
        """Set a custom storage implementation (for testing).

        Args:
            storage: The storage implementation to use.
        """
        cls._instance = storage
