from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection, AsyncCursor
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool
from structlog import get_logger

from agent_platform.server.storage.postgres.migrations import PostgresMigrations
from agent_platform.server.storage.postgres.storage_agents import (
    PostgresStorageAgentsMixin,
)
from agent_platform.server.storage.postgres.storage_artifacts import (
    PostgresStorageArtifactsMixin,
)
from agent_platform.server.storage.postgres.storage_files import (
    PostgresStorageFilesMixin,
)
from agent_platform.server.storage.postgres.storage_memory import (
    PostgresStorageMemoriesMixin,
)
from agent_platform.server.storage.postgres.storage_messages import (
    PostgresStorageMessagesMixin,
)
from agent_platform.server.storage.postgres.storage_runs import (
    PostgresStorageRunsMixin,
)
from agent_platform.server.storage.postgres.storage_scoped_storage import (
    PostgresStorageScopedStorageMixin,
)
from agent_platform.server.storage.postgres.storage_threads import (
    PostgresStorageThreadsMixin,
)
from agent_platform.server.storage.postgres.storage_users import (
    PostgresStorageUsersMixin,
)


class PostgresStorage(
    # Careful: order matters!
    PostgresStorageArtifactsMixin,
    PostgresStorageAgentsMixin,
    PostgresStorageThreadsMixin,
    PostgresStorageMessagesMixin,
    PostgresStorageUsersMixin,
    PostgresStorageMemoriesMixin,
    PostgresStorageRunsMixin,
    PostgresStorageScopedStorageMixin,
    PostgresStorageFilesMixin,
):
    def __init__(self, pool: AsyncConnectionPool | None = None):
        self._pool = pool
        self._logger = get_logger(__name__)
        self._migrations = PostgresMigrations(self._cursor)
        self._is_setup = False

    async def setup(self) -> None:
        """Create and open the async connection pool."""
        if self._is_setup:
            return  # Already setup

        dsn = self._get_dsn()
        self._pool = AsyncConnectionPool(
            conninfo=dsn, max_size=20, num_workers=3, open=False,
        ) if self._pool is None else self._pool
        await self._pool.open()
        await self._run_migrations()
        self._is_setup = True

    async def teardown(self) -> None:
        """Close the async connection pool."""
        if self._is_setup and self._pool is not None:
            await self._pool.close()
            self._pool = None
        self._is_setup = False

    async def get_connection(self) -> AsyncConnection:
        """Get a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Pool not initialized; call setup() first.")
        return await self._pool.getconn()

    def _get_dsn(self) -> str:
        from os import getenv

        db = getenv("POSTGRES_DB")
        user = getenv("POSTGRES_USER")
        password = getenv("POSTGRES_PASSWORD")
        host = getenv("POSTGRES_HOST")
        port = getenv("POSTGRES_PORT")
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    async def _run_migrations(self):
        await self._migrations.run_migrations()

    @asynccontextmanager
    async def _cursor(
        self, cursor: AsyncCursor[DictRow] | None = None,
    ) -> AsyncGenerator[AsyncCursor[DictRow], None]:
        """Yield an async psycopg cursor from the pool (or uses the provided cursor)."""
        if not self._pool:
            raise RuntimeError("Pool not initialized; call setup() first.")
        if cursor is None:
            async with self._pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    yield cur
        else:
            yield cursor
