from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.core.files.files import UploadedFile
from agent_platform.core.kernel import StorageInterface
from agent_platform.core.kernel_interfaces.otel import OTelArtifact
from agent_platform.core.storage import ScopedStorage
from agent_platform.core.thread import ThreadMessage
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin
from agent_platform.server.storage import StorageService


class AgentServerStorageInterface(StorageInterface, UsesKernelMixin):
    """Handles persistent storage operations for CA data across agents and runs."""

    def __init__(self):
        self._internal_storage = StorageService.get_instance()

    async def put_message(self, message: ThreadMessage) -> None:
        """Puts a message into the storage."""
        await self._internal_storage.add_message_to_thread(
            user_id=self.kernel.user.user_id,
            thread_id=self.kernel.thread_state.thread_id,
            message=message,
        )

    async def create_scoped_storage(self, scoped_storage: ScopedStorage) -> None:
        """Creates a new scoped storage record."""
        await self._internal_storage.create_scoped_storage(scoped_storage)

    async def get_scoped_storage(self, storage_id: str) -> ScopedStorage:
        """Gets a scoped storage record by its ID."""
        return await self._internal_storage.get_scoped_storage(storage_id)

    async def update_scoped_storage(self, scoped_storage: ScopedStorage) -> None:
        """Updates a scoped storage record."""
        await self._internal_storage.upsert_scoped_storage(scoped_storage)

    async def delete_scoped_storage(self, storage_id: str) -> None:
        """Deletes a scoped storage record by its ID."""
        await self._internal_storage.delete_scoped_storage(storage_id)

    async def get_otel_artifact(self, artifact_id: str) -> OTelArtifact:
        """Gets an OTel artifact by its ID."""
        return await self._internal_storage.get_otel_artifact(artifact_id)

    async def create_otel_artifact(self, artifact: OTelArtifact) -> None:
        """Creates a new OTel artifact."""
        await self._internal_storage.create_otel_artifact(artifact)

    async def get_file_by_id(self, file_id: str) -> UploadedFile | None:
        """Gets a file by its ID."""
        return await self._internal_storage.get_file_by_id(file_id, self.kernel.user.user_id)

    async def get_dids_connection_details(self) -> DataServerDetails:
        """Get the DIDS connection details from storage."""
        return await self._internal_storage.get_dids_connection_details()
