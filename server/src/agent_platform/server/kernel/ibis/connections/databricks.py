"""Databricks async connection implementation."""

from __future__ import annotations

import asyncio
import typing

from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

if typing.TYPE_CHECKING:
    from databricks.sql.client import Cursor as DatabricksCursor
    from ibis.backends.sql import SQLBackend


class AsyncDatabricksConnection(AsyncIbisConnection):
    """Async wrapper for Databricks ibis connections.

    Returns Databricks cursor from raw_sql() for proper typing.
    Databricks always auto-commits, so no explicit commit is needed.

    Note: Databricks cursor does NOT have a rowcount attribute. If you need
    row counts from mutations, use a different approach (e.g., RETURNING clause
    or SELECT COUNT after the operation).
    """

    def __init__(self, connection: SQLBackend, engine: str = "databricks"):
        super().__init__(connection, engine)

    def _is_autocommit(self) -> bool:
        """Check if Databricks connection is in autocommit mode.

        Databricks defaults to autocommit=true For now, assume autocommit
        is always enabled.
        """
        return True

    async def raw_sql(self, query: str, *, auto_commit: bool = True) -> DatabricksCursor:
        """Execute raw SQL and return a Databricks cursor.

        Args:
            query: SQL query string
            auto_commit: If True (default), commit after execution. Databricks
                auto-commits, so this is effectively a no-op.

        Returns:
            Databricks cursor with query results
        """
        from typing import cast

        from ibis.backends.databricks import Backend

        def _execute() -> DatabricksCursor:
            databricks = cast(Backend, self._connection)
            cursor: DatabricksCursor = databricks.raw_sql(query)
            # Databricks auto-commits - no explicit commit needed
            return cursor

        return await asyncio.to_thread(_execute)
