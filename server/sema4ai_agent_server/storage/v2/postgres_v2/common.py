from abc import abstractmethod
from collections.abc import AsyncGenerator
from uuid import UUID

from psycopg import AsyncCursor

from sema4ai_agent_server.storage.v2.base_v2 import BaseStorageV2
from sema4ai_agent_server.storage.v2.errors_v2 import InvalidUUIDError


class CommonMixin(BaseStorageV2):
    @abstractmethod
    async def _cursor(self, cursor: AsyncCursor|None=None) -> AsyncGenerator[AsyncCursor, None]:
        """Get a cursor for the database (or uses the provided cursor)."""
        pass
    
    def _validate_uuid(self, uuid: str) -> None:
        """Validate a UUID string."""
        try:
            UUID(uuid)
        except ValueError as e:
            raise InvalidUUIDError(f"Invalid UUID: {uuid}") from e