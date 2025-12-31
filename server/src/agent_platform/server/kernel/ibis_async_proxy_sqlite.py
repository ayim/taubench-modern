"""SQLite-specific extensions for Ibis async proxy.

This module provides SQLite-specific functionality that extends the base
AsyncIbisConnection with operations that only work with SQLite databases.
"""

from __future__ import annotations

import asyncio
import typing
from typing import Any, cast

from agent_platform.server.kernel.ibis_async_proxy import AsyncIbisConnection

if typing.TYPE_CHECKING:
    import pandas
    from ibis.backends import BaseBackend


class SqliteAsyncConnectionMixin:
    """Mixin providing SQLite-specific connection operations.

    This mixin adds methods that only work with SQLite connections,
    such as raw SQL execution via the underlying sqlite3.Connection object.

    Requires:
        - self._connection: The underlying Ibis backend connection
    """

    _connection: BaseBackend

    async def raw_sql(self, query: str) -> pandas.DataFrame:
        """Execute raw SQL directly on the underlying SQLite connection.

        This method bypasses Ibis's SQL parsing and executes the query directly
        on the raw sqlite3.Connection object. Useful for SQLite-specific commands
        like PRAGMA that aren't standard SQL.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Args:
            query: Raw SQL query string

        Returns:
            Pandas DataFrame with query results

        Raises:
            AttributeError: If the backend doesn't support the .con attribute
        """
        import pandas

        def _execute_raw_sql() -> pandas.DataFrame:
            # Access the raw SQLite connection (sqlite3.Connection)
            # For SQLite, Ibis stores it as connection.con
            raw_conn = cast(Any, self._connection).con
            return pandas.read_sql_query(query, raw_conn)

        return await asyncio.to_thread(_execute_raw_sql)


class SqliteAsyncIbisConnection(SqliteAsyncConnectionMixin, AsyncIbisConnection):
    """SQLite-specific async Ibis connection.

    This class extends AsyncIbisConnection with SQLite-specific operations
    provided by SqliteAsyncConnectionMixin.

    Use this class when you need SQLite-specific functionality like raw_sql
    execution via the underlying sqlite3.Connection object.
    """

    # All methods are inherited:
    # - AsyncIbisConnection provides the base async connection interface
    # - SqliteAsyncConnectionMixin adds the raw_sql method
