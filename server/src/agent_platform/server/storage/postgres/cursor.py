from abc import abstractmethod
from contextlib import AbstractAsyncContextManager

from psycopg import AsyncCursor
from psycopg.rows import DictRow

from agent_platform.server.storage.abstract import AbstractStorage


class CursorMixin(AbstractStorage):
    @abstractmethod
    def _cursor(
        self,
        cursor: AsyncCursor[DictRow] | None = None,
    ) -> AbstractAsyncContextManager[AsyncCursor[DictRow]]:
        """Get a cursor for the database (or uses the provided cursor)."""
