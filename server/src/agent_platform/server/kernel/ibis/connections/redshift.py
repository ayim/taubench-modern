"""Redshift async connection implementation."""

from __future__ import annotations

import typing

from agent_platform.server.kernel.ibis.connections.postgres import (
    AsyncPostgresConnection,
)

if typing.TYPE_CHECKING:
    from ibis.backends.sql import SQLBackend


class AsyncRedshiftConnection(AsyncPostgresConnection):
    """Async wrapper for Redshift ibis connections.

    Redshift uses the PostgreSQL driver (psycopg), so it inherits
    all behavior from AsyncPostgresConnection.
    """

    def __init__(self, connection: SQLBackend, engine: str = "redshift"):
        super().__init__(connection, engine)
