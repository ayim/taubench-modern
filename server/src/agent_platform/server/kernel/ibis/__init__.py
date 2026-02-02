"""Async ibis connection wrappers with per-backend typed cursors.

This module provides async wrappers around ibis database connections.
Each backend has its own connection class that returns properly typed
cursors from raw_sql().

Usage:
    from agent_platform.server.kernel.ibis import create_async_connection

    # In ibis_utils.py:
    conn = await create_async_connection(raw_conn, engine="sqlite")
    cursor = await conn.raw_sql("SELECT * FROM users")  # Returns sqlite3.Cursor
"""

from __future__ import annotations

import typing

from agent_platform.server.kernel.ibis.base import (
    AsyncIbisColumn,
    AsyncIbisConnection,
    AsyncIbisTable,
)
from agent_platform.server.kernel.ibis.connections import (
    AsyncDatabricksConnection,
    AsyncDuckDBConnection,
    AsyncMySQLConnection,
    AsyncPostgresConnection,
    AsyncRedshiftConnection,
    AsyncSnowflakeConnection,
    AsyncSqliteConnection,
)

if typing.TYPE_CHECKING:
    from ibis.backends.sql import SQLBackend


def create_async_connection(connection: SQLBackend, engine: str) -> AsyncIbisConnection:
    """Factory to create the appropriate typed async connection.

    Args:
        connection: Raw ibis backend connection
        engine: Database engine name ('sqlite', 'postgres', 'mysql', etc.)

    Returns:
        Appropriate AsyncIbisConnection subclass for the engine

    Raises:
        ValueError: If engine is not supported
    """
    match engine:
        case "sqlite":
            return AsyncSqliteConnection(connection)
        case "postgres":
            return AsyncPostgresConnection(connection)
        case "mysql":
            return AsyncMySQLConnection(connection)
        case "redshift":
            return AsyncRedshiftConnection(connection)
        case "snowflake":
            return AsyncSnowflakeConnection(connection)
        case "databricks":
            return AsyncDatabricksConnection(connection)
        case "duckdb":
            return AsyncDuckDBConnection(connection)
        case _:
            raise ValueError(
                f"Unsupported database engine: {engine}. "
                f"Supported engines: sqlite, postgres, mysql, redshift, snowflake, databricks, duckdb"
            )


__all__ = [
    # Per-backend connections
    "AsyncDatabricksConnection",
    "AsyncDuckDBConnection",
    # Base classes
    "AsyncIbisColumn",
    "AsyncIbisConnection",
    "AsyncIbisTable",
    # Per-backend connections
    "AsyncMySQLConnection",
    "AsyncPostgresConnection",
    "AsyncRedshiftConnection",
    "AsyncSnowflakeConnection",
    "AsyncSqliteConnection",
    # Factory
    "create_async_connection",
]
