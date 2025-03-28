"""Module provides connection functions to the postgres server shared
between the various other postgres modules."""

from contextlib import asynccontextmanager, contextmanager
from typing import (
    AsyncGenerator,
    Generator,
)

import orjson
from psycopg import AsyncConnection, AsyncCursor, Connection, Cursor
from psycopg.rows import tuple_row
from psycopg.types.json import set_json_dumps
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from sema4ai_agent_server.env_vars import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)

set_json_dumps(orjson.dumps)


def get_dsn() -> str:
    """Get the DSN for the Postgres connection."""
    return (
        f"postgresql://"
        f"{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/"
        f"{POSTGRES_DB}"
    )


_sync_pool = None


@contextmanager
def get_sync_connection() -> Generator[Connection, None, None]:
    """Get the connection to the Postgres database."""
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = ConnectionPool(
            conninfo=get_dsn(),
            max_size=20,
            open=False,
        )
        _sync_pool.open()
    with _sync_pool.connection() as conn:
        yield conn


_async_pool = None


@asynccontextmanager
async def get_async_connection() -> AsyncGenerator[AsyncConnection, None]:
    """Get the connection to the Postgres database."""
    global _async_pool
    if _async_pool is None:
        print("Initializing async_connection")
        conn_info = get_dsn()
        _async_pool = AsyncConnectionPool(
            conninfo=conn_info,
            max_size=20,
            open=False,
        )
        await _async_pool.open()
    async with _async_pool.connection() as conn:
        yield conn


class PostgresConnectionManager:
    @contextmanager
    def get_sync_connection(self) -> Generator[Connection, None, None]:
        """Get the connection to the Postgres database."""
        with get_sync_connection() as connection:
            yield connection

    @contextmanager
    def sync_cursor(self, row_factory=tuple_row) -> Generator[Cursor, None, None]:
        """Get the cursor for the Postgres database.

        Args:
            row_factory: The row factory to use for the cursor, must be a callable
                that takes a cursor and returns a row maker, see `psycopg.rows`.
        """
        with self.get_sync_connection() as conn:
            with conn.cursor(row_factory=row_factory) as cur:
                yield cur

    @asynccontextmanager
    async def get_async_connection(
        self,
    ) -> AsyncGenerator[AsyncConnection, None]:
        """Get the connection to the Postgres database."""
        async with get_async_connection() as connection:
            yield connection

    @asynccontextmanager
    async def async_cursor(
        self, row_factory=tuple_row
    ) -> AsyncGenerator[AsyncCursor, None]:
        """Get the cursor for the Postgres database.

        Args:
            row_factory: The row factory to use for the cursor, must be a callable
                that takes a cursor and returns a row maker, see `psycopg.rows`.
        """
        async with self.get_async_connection() as conn:
            async with conn.cursor(row_factory=row_factory) as cur:
                yield cur
