"""SQLite async connection implementation."""

from __future__ import annotations

import asyncio
import sqlite3
import typing
from typing import cast

from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

if typing.TYPE_CHECKING:
    from ibis.backends.sql import SQLBackend
    from ibis.backends.sqlite import Backend as SqliteBackend


class AsyncSqliteConnection(AsyncIbisConnection):
    """Async wrapper for SQLite ibis connections.

    Returns sqlite3.Cursor from raw_sql() for proper typing.
    Handles commit based on isolation_level setting.
    """

    def __init__(self, connection: SQLBackend, engine: str = "sqlite"):
        super().__init__(connection, engine)

    def _get_backend(self) -> SqliteBackend:
        """Get the typed SQLite backend."""
        return cast("SqliteBackend", self._connection)

    def _is_autocommit(self) -> bool:
        """Check if SQLite connection is in autocommit mode.

        SQLite is in autocommit mode when isolation_level is None.
        """
        backend = self._get_backend()
        return backend.con.isolation_level is None

    async def raw_sql(self, query: str, *, auto_commit: bool = True) -> sqlite3.Cursor:
        """Execute raw SQL and return a sqlite3 cursor.

        Args:
            query: SQL query string
            auto_commit: If True (default), commit after execution unless
                in autocommit mode (isolation_level=None).

        Returns:
            sqlite3.Cursor with query results
        """

        def _execute() -> sqlite3.Cursor:
            backend = self._get_backend()
            cursor: sqlite3.Cursor = backend.raw_sql(query)

            if auto_commit and not self._is_autocommit():
                backend.con.commit()

            return cursor

        return await asyncio.to_thread(_execute)

    async def execute_dml(self, query: str, *, auto_commit: bool = True) -> int:
        """Execute a DML statement and return the affected row count.

        Args:
            query: DML statement (INSERT, UPDATE, or DELETE)
            auto_commit: If True (default), commit after execution.

        Returns:
            Number of rows affected. Returns -1 if the count is unavailable.
        """
        cursor = await self.raw_sql(query, auto_commit=auto_commit)
        try:
            row_count = cursor.rowcount
            return row_count if row_count is not None else -1
        finally:
            cursor.close()
