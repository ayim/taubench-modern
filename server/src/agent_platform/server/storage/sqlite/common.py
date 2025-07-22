from abc import abstractmethod
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from aiosqlite.cursor import Cursor

from agent_platform.server.secret_manager.option import SecretService
from agent_platform.server.storage.base import BaseStorage
from agent_platform.server.storage.errors import InvalidUUIDError


class CommonMixin(BaseStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize secret manager once and reuse it
        self._secret_manager = SecretService.get_instance()

    @abstractmethod
    def _cursor(
        self,
        cursor: Cursor | None = None,
    ) -> AbstractAsyncContextManager[Cursor]:
        """Get a cursor for the database (or uses the provided cursor)."""
        pass

    def _validate_uuid(self, uuid: str) -> None:
        """Validate a UUID string."""
        try:
            UUID(uuid)
        except ValueError as e:
            raise InvalidUUIDError(f"Invalid UUID: {uuid}") from e
