from abc import abstractmethod
from contextlib import AbstractAsyncContextManager

from aiosqlite.cursor import Cursor

from agent_platform.server.storage.abstract import AbstractStorage


class CursorMixin(AbstractStorage):
    @abstractmethod
    def _cursor(
        self,
    ) -> AbstractAsyncContextManager[Cursor]:
        """Get a cursor for reading from the database."""

    @abstractmethod
    def _transaction(
        self,
    ) -> AbstractAsyncContextManager[Cursor]:
        """Get a cursor for writing to the database, implementations will ensure
        auto-rollback on error and safe locking for concurrent writes."""
