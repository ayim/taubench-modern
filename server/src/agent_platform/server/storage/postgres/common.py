from abc import abstractmethod
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from psycopg import AsyncCursor
from psycopg.rows import DictRow

from agent_platform.server.storage.base import BaseStorage
from agent_platform.server.storage.errors import InvalidUUIDError


class CommonMixin(BaseStorage):
    @abstractmethod
    def _cursor(
        self,
        cursor: AsyncCursor[DictRow] | None = None,
    ) -> AbstractAsyncContextManager[AsyncCursor[DictRow]]:
        """Get a cursor for the database (or uses the provided cursor)."""
        pass

    def _validate_uuid(self, uuid: str) -> None:
        """Validate a UUID string."""
        try:
            UUID(uuid)
        except ValueError as e:
            raise InvalidUUIDError(f"Invalid UUID: {uuid}") from e
