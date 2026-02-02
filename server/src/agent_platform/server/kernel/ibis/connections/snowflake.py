"""Snowflake async connection implementation."""

from __future__ import annotations

import asyncio
import typing
from typing import cast

from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

if typing.TYPE_CHECKING:
    from ibis.backends.snowflake import Backend as SnowflakeBackend
    from ibis.backends.sql import SQLBackend
    from snowflake.connector.cursor import SnowflakeCursor


class AsyncSnowflakeConnection(AsyncIbisConnection):
    """Async wrapper for Snowflake ibis connections.

    Returns SnowflakeCursor from raw_sql() for proper typing.
    """

    def __init__(self, connection: SQLBackend, engine: str = "snowflake"):
        super().__init__(connection, engine)

    def _get_backend(self) -> SnowflakeBackend:
        """Get the typed Snowflake backend."""
        from ibis.backends.snowflake import Backend as SnowflakeBackend

        return cast(SnowflakeBackend, self._connection)

    def _is_autocommit(self) -> bool:
        """Check if Snowflake connection is in autocommit mode.

        snowflake-connector-python defaults to autocommit=true
        """
        return True

    async def raw_sql(self, query: str, *, auto_commit: bool = True) -> SnowflakeCursor:
        """Execute raw SQL and return a Snowflake cursor.

        Args:
            query: SQL query string
            auto_commit: If True (default), commit after execution. Snowflake
                auto-commits DML, so this is effectively a no-op.

        Returns:
            SnowflakeCursor with query results
        """

        def _execute() -> SnowflakeCursor:
            backend = self._get_backend()
            cursor: SnowflakeCursor = backend.raw_sql(query)
            return cursor

        return await asyncio.to_thread(_execute)
