from abc import ABC, abstractmethod

from agent_server_types_v2.storage import ScopedStorage
from agent_server_types_v2.thread import ThreadMessage


class StorageInterface(ABC):
    """Handles persistent storage operations for CA data across agents and runs."""

    @abstractmethod
    async def put_message(self, message: ThreadMessage) -> None:
        """Puts a message into the storage."""
        pass

    @abstractmethod
    async def create_scoped_storage(self, scoped_storage: ScopedStorage) -> None:
        """Creates a new scoped storage record."""
        pass

    @abstractmethod
    async def get_scoped_storage(self, storage_id: str) -> ScopedStorage:
        """Gets a scoped storage record by its ID."""
        pass

    @abstractmethod
    async def update_scoped_storage(self, scoped_storage: ScopedStorage) -> None:
        """Updates a scoped storage record."""
        pass

    @abstractmethod
    async def delete_scoped_storage(self, storage_id: str) -> None:
        """Deletes a scoped storage record by its ID."""
        pass
