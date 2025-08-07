from abc import abstractmethod
from contextlib import AbstractAsyncContextManager

from aiosqlite.cursor import Cursor

from agent_platform.server.storage.abstract import AbstractStorage


class CursorMixin(AbstractStorage):
    @abstractmethod
    def _cursor(
        self,
        cursor: Cursor | None = None,
    ) -> AbstractAsyncContextManager[Cursor]:
        """Get a cursor for the database (or uses the provided cursor)."""
        pass
