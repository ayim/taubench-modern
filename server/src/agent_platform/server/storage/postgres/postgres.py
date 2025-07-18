from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from psycopg import AsyncConnection, AsyncCursor
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool
from structlog import get_logger

from agent_platform.core.configurations.base import Configuration, FieldMetadata
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
from agent_platform.server.storage.postgres.storage_mcp_servers import (
    PostgresStorageMCPServersMixin,
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
from agent_platform.server.storage.postgres.storage_work_items import (
    PostgresStorageWorkItemsMixin,
)


@dataclass(frozen=True)
class PostgresConfig(Configuration):
    """Configuration for the Postgres database."""

    host: str = field(
        default="localhost",
        metadata=FieldMetadata(
            description="The host of the database to connect to.",
            env_vars=["SEMA4AI_AGENT_SERVER_POSTGRES_HOST", "POSTGRES_HOST"],
        ),
    )
    port: int = field(
        default=5432,
        metadata=FieldMetadata(
            description="The port of the database to connect to.",
            env_vars=["SEMA4AI_AGENT_SERVER_POSTGRES_PORT", "POSTGRES_PORT"],
        ),
    )
    db: str = field(
        default="postgres",
        metadata=FieldMetadata(
            description="The name of the database to connect to.",
            env_vars=["SEMA4AI_AGENT_SERVER_POSTGRES_DB", "POSTGRES_DB"],
        ),
    )
    user: str = field(
        default="postgres",
        metadata=FieldMetadata(
            description="The username to connect to the database with.",
            env_vars=["SEMA4AI_AGENT_SERVER_POSTGRES_USER", "POSTGRES_USER"],
        ),
    )
    # TODO: @kylie-bee: This is printing in clear text to the configuration file...
    password: str = field(
        default="postgres",
        metadata=FieldMetadata(
            description="The password to connect to the database with.",
            env_vars=["SEMA4AI_AGENT_SERVER_POSTGRES_PASSWORD", "POSTGRES_PASSWORD"],
        ),
    )

    # derived field
    dsn: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dsn",
            f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}",
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
    PostgresStorageWorkItemsMixin,
    PostgresStorageScopedStorageMixin,
    PostgresStorageFilesMixin,
    PostgresStorageMCPServersMixin,
):
    def __init__(self, pool: AsyncConnectionPool | None = None):
        # If a pool is provided externally, PostgresStorage should not be
        # responsible for closing it: the caller owns its lifecycle. When we
        # create the pool ourselves we *do* want to close it in teardown().
        self._pool = pool
        self._owns_pool = pool is None
        self._logger = get_logger(__name__)
        self._migrations = PostgresMigrations(self._cursor)
        self._is_setup = False

    async def setup(self) -> None:
        """Create and open the async connection pool."""
        if self._is_setup:
            return  # Already setup

        dsn = self._get_dsn()
        self._pool = (
            AsyncConnectionPool(
                conninfo=dsn,
                max_size=20,
                num_workers=3,
                open=False,
            )
            if self._pool is None
            else self._pool
        )
        await self._pool.open()
        await self._run_migrations()
        self._is_setup = True

    async def teardown(self) -> None:
        """Close the async connection pool."""
        # Only close the pool if we created/own it. A caller-provided pool may
        # be shared across test cases or even the entire application, so we
        # must not close it here! Doing so would render the shared pool
        # unusable and lead to "PoolClosed" errors in subsequent operations.
        if self._is_setup and self._pool is not None and self._owns_pool:
            await self._pool.close()
            self._pool = None
        self._is_setup = False

    async def get_connection(self) -> AsyncConnection:
        """Get a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Pool not initialized; call setup() first.")
        return await self._pool.getconn()

    def _get_dsn(self) -> str:
        return PostgresConfig.dsn

    async def _run_migrations(self):
        await self._migrations.run_migrations()

    @asynccontextmanager
    async def _cursor(
        self,
        cursor: AsyncCursor[DictRow] | None = None,
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
