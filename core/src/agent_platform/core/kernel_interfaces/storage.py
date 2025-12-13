from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from agent_platform.core.files import UploadedFile
from agent_platform.core.integrations import Integration
from agent_platform.core.kernel_interfaces.otel import OTelArtifact
from agent_platform.core.storage import ScopedStorage
from agent_platform.core.thread import ThreadMessage

if TYPE_CHECKING:
    # Import for type checking only to avoid circular imports at runtime
    from agent_platform.core.agent import Agent


class StorageInterface(ABC):
    """Handles persistent storage operations for CA data across agents and runs."""

    @abstractmethod
    async def put_message(self, message: ThreadMessage) -> None:
        """Puts a message into the storage."""

    @abstractmethod
    async def create_scoped_storage(self, scoped_storage: ScopedStorage) -> None:
        """Creates a new scoped storage record."""

    @abstractmethod
    async def get_scoped_storage(self, storage_id: str) -> ScopedStorage:
        """Gets a scoped storage record by its ID."""

    @abstractmethod
    async def update_scoped_storage(self, scoped_storage: ScopedStorage) -> None:
        """Updates a scoped storage record."""

    @abstractmethod
    async def delete_scoped_storage(self, storage_id: str) -> None:
        """Deletes a scoped storage record by its ID."""

    @abstractmethod
    async def get_otel_artifact(self, artifact_id: str) -> OTelArtifact:
        """Gets an OTel artifact by its ID."""

    @abstractmethod
    async def create_otel_artifact(self, artifact: OTelArtifact) -> None:
        """Creates a new OTel artifact."""

    @abstractmethod
    async def get_file_by_id(self, file_id: str) -> UploadedFile | None:
        """Gets a file by its ID."""

    @abstractmethod
    async def get_integration_by_kind(self, kind: str) -> "Integration":
        """Get integration by kind."""

    @abstractmethod
    async def upsert_agent(self, user_id: str, agent: "Agent") -> None:
        """Create or update an agent definition for a user."""
