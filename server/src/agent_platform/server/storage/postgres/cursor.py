from abc import abstractmethod
from contextlib import AbstractAsyncContextManager

from psycopg import AsyncCursor
from psycopg.rows import DictRow

from agent_platform.server.storage.abstract import AbstractStorage


class CursorMixin(AbstractStorage):
    @abstractmethod
    def _cursor(
        self,
    ) -> AbstractAsyncContextManager[AsyncCursor[DictRow]]:
        """Get a cursor for reading from the database."""

    @abstractmethod
    def _transaction(
        self,
    ) -> AbstractAsyncContextManager[AsyncCursor[DictRow]]:
        """Get a cursor for writing to the database, implementations will ensure
        auto-rollback on error."""
