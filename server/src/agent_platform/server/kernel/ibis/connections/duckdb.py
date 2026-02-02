"""DuckDB async connection implementation."""

from __future__ import annotations

import asyncio
import typing
from typing import cast

from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

if typing.TYPE_CHECKING:
    from duckdb import DuckDBPyConnection
    from ibis.backends.duckdb import Backend as DuckDBBackend
    from ibis.backends.sql import SQLBackend


class AsyncDuckDBConnection(AsyncIbisConnection):
    """Async wrapper for DuckDB ibis connections.

    Returns DuckDB cursor from raw_sql() for proper typing.
    DuckDB is used as an in-memory backend for SQL computations.
    DuckDB auto-commits by default.
    """

    def __init__(self, connection: SQLBackend, engine: str = "duckdb"):
        super().__init__(connection, engine)

    def _get_backend(self) -> DuckDBBackend:
        """Get the typed DuckDB backend."""
        from ibis.backends.duckdb import Backend as DuckDBBackend

        return cast(DuckDBBackend, self._connection)

    def _is_autocommit(self) -> bool:
        """Check if DuckDB connection is in autocommit mode.

        DuckDB auto-commits by default.
        """
        return True

    async def raw_sql(self, query: str, *, auto_commit: bool = True) -> DuckDBPyConnection:
        """Execute raw SQL and return a DuckDB connection/cursor.

        Args:
            query: SQL query string
            auto_commit: If True (default), commit after execution. DuckDB
                auto-commits by default, so this is effectively a no-op.

        Returns:
            DuckDB connection with query results
        """

        def _execute() -> DuckDBPyConnection:
            backend = self._get_backend()
            cursor: DuckDBPyConnection = backend.raw_sql(query)
            # DuckDB auto-commits by default - no explicit commit needed
            return cursor

        return await asyncio.to_thread(_execute)
