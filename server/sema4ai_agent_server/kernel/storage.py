from agent_server_types_v2.kernel import StorageInterface
from agent_server_types_v2.kernel_interfaces.otel import OTelArtifact
from agent_server_types_v2.storage import ScopedStorage
from agent_server_types_v2.thread import ThreadMessage
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin
from sema4ai_agent_server.storage.v2 import get_storage_v2


class AgentServerStorageInterface(StorageInterface, UsesKernelMixin):
    """Handles persistent storage operations for CA data across agents and runs."""

    def __init__(self):
        self._internal_storage = get_storage_v2()

    async def put_message(self, message: ThreadMessage) -> None:
        """Puts a message into the storage."""
        await self._internal_storage.add_message_to_thread_v2(
            user_id=self.kernel.user.user_id,
            thread_id=self.kernel.thread_state.thread_id,
            message=message,
        )

    async def create_scoped_storage(self, scoped_storage: ScopedStorage) -> None:
        """Creates a new scoped storage record."""
        await self._internal_storage.create_scoped_storage_v2(scoped_storage)

    async def get_scoped_storage(self, storage_id: str) -> ScopedStorage:
        """Gets a scoped storage record by its ID."""
        return await self._internal_storage.get_scoped_storage_v2(storage_id)

    async def update_scoped_storage(self, scoped_storage: ScopedStorage) -> None:
        """Updates a scoped storage record."""
        await self._internal_storage.upsert_scoped_storage_v2(scoped_storage)

    async def delete_scoped_storage(self, storage_id: str) -> None:
        """Deletes a scoped storage record by its ID."""
        await self._internal_storage.delete_scoped_storage_v2(storage_id)

    async def get_otel_artifact(self, artifact_id: str) -> OTelArtifact:
        """Gets an OTel artifact by its ID."""
        return await self._internal_storage.get_otel_artifact_v2(artifact_id)

    async def create_otel_artifact(self, artifact: OTelArtifact) -> None:
        """Creates a new OTel artifact."""
        await self._internal_storage.create_otel_artifact_v2(artifact)
