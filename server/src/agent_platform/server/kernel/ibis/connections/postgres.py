"""PostgreSQL async connection implementation."""

from __future__ import annotations

import asyncio
import typing
from typing import cast

from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

if typing.TYPE_CHECKING:
    from ibis.backends.postgres import Backend as PostgresBackend
    from ibis.backends.sql import SQLBackend
    from psycopg import Cursor as PsycopgCursor


class AsyncPostgresConnection(AsyncIbisConnection):
    """Async wrapper for PostgreSQL ibis connections.

    Returns psycopg.Cursor from raw_sql() for proper typing.
    Handles commit based on connection autocommit setting.
    """

    def __init__(self, connection: SQLBackend, engine: str = "postgres"):
        super().__init__(connection, engine)

    def _get_backend(self) -> PostgresBackend:
        """Get the typed PostgreSQL backend."""
        from ibis.backends.postgres import Backend as PostgresBackend

        return cast(PostgresBackend, self._connection)

    def _is_autocommit(self) -> bool:
        """Check if PostgreSQL connection is in autocommit mode."""
        backend = self._get_backend()
        return backend.con.autocommit is True

    async def raw_sql(self, query: str, *, auto_commit: bool = True) -> PsycopgCursor:
        """Execute raw SQL and return a psycopg cursor.

        Args:
            query: SQL query string
            auto_commit: If True (default), commit after execution unless
                autocommit is already enabled on the connection.

        Returns:
            psycopg.Cursor with query results
        """

        def _execute() -> PsycopgCursor:
            backend = self._get_backend()
            cursor: PsycopgCursor = backend.raw_sql(query)

            if auto_commit and not self._is_autocommit():
                backend.con.commit()

            return cursor

        return await asyncio.to_thread(_execute)
