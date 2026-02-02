"""MySQL async connection implementation."""

from __future__ import annotations

import asyncio
import typing
from typing import cast

from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

if typing.TYPE_CHECKING:
    from ibis.backends.mysql import Backend as MySQLBackend
    from ibis.backends.sql import SQLBackend
    from MySQLdb.cursors import Cursor as MySQLCursor


class AsyncMySQLConnection(AsyncIbisConnection):
    """Async wrapper for MySQL ibis connections.

    Returns MySQLdb cursor from raw_sql() for proper typing.
    MySQL's ibis raw_sql() commits internally after DML, so we skip explicit commit
    to avoid double-commit issues.
    """

    def __init__(self, connection: SQLBackend, engine: str = "mysql"):
        super().__init__(connection, engine)

    def _get_backend(self) -> MySQLBackend:
        """Get the typed MySQL backend."""
        return cast(MySQLBackend, self._connection)

    def _is_autocommit(self) -> bool:
        """Check if MySQL connection is in autocommit mode.

        MySQL ibis backend's raw_sql() commits internally, so we treat it as autocommit.
        """
        # MySQL's raw_sql() handles commit internally
        return True

    async def raw_sql(self, query: str, *, auto_commit: bool = True) -> MySQLCursor:
        """Execute raw SQL and return a MySQL cursor.

        Args:
            query: SQL query string
            auto_commit: If True (default), commit after execution. MySQL's ibis
                backend commits internally, so this is effectively a no-op.

        Returns:
            MySQLdb cursor with query results
        """

        def _execute() -> MySQLCursor:
            backend = self._get_backend()
            cursor: MySQLCursor = backend.raw_sql(query)
            # MySQL ibis raw_sql() commits internally - skip to avoid double-commit
            return cursor

        return await asyncio.to_thread(_execute)
