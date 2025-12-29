import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType
from typing import Self

import sqlalchemy as sa
from psycopg import AsyncCursor
from psycopg.rows import DictRow, dict_row
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from structlog import get_logger

from agent_platform.core.configurations.base import Configuration, FieldMetadata
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.server.storage.base import BaseStorage
from agent_platform.server.storage.postgres.migrations import PostgresMigrations
from agent_platform.server.storage.postgres.storage_agents import (
    PostgresStorageAgentsMixin,
)
from agent_platform.server.storage.postgres.storage_artifacts import (
    PostgresStorageArtifactsMixin,
)
from agent_platform.server.storage.postgres.storage_config import (
    PostgresStorageConfigMixin,
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
from agent_platform.server.storage.postgres.storage_platform_configs import (
    PostgresStoragePlatformConfigsMixin,
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

logger = get_logger(__name__)


class NullAsyncLock:
    """A no-op asyncio-like lock."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False  # don't suppress exceptions


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

    pool_max_size: int = field(
        default=50,
        metadata=FieldMetadata(
            description="The maximum size of the connection pool.",
            env_vars=["SEMA4AI_AGENT_SERVER_POSTGRES_POOL_MAX_SIZE", "POSTGRES_POOL_MAX_SIZE"],
        ),
    )

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
    PostgresStoragePlatformConfigsMixin,
    PostgresStorageConfigMixin,
    BaseStorage,
):
    V2_PREFIX = "v2."

    def __init__(self, dsn: str | None = None):
        from typing import Any

        # Initialize all parent mixins (including CommonMixin for secret manager)
        super().__init__()

        self._logger = get_logger(__name__)
        self._migrations = PostgresMigrations(self._transaction)
        self._is_setup = False
        self._dns = dsn
        self._write_lock = NullAsyncLock()
        self._tasks: set[asyncio.Task[Any]] = set()

    @classmethod
    def _compute_pool_base_and_overflow(cls, pool_size: int) -> tuple[int, int]:
        # Note: perhaps we should actually received both base_pool_size and max_overflow as inputs?

        # Compute pool_size (base) and max_overflow from the total maximum connections.
        # The input pool_size represents the maximum total connections allowed.
        # Heuristic: split between base pool and overflow based on size.
        if pool_size <= 2:
            # For really tiny pools: keep all as base, no overflow
            base_pool_size = pool_size
            max_overflow = 0
        elif pool_size <= 5:
            # For very small pools: keep most as base, minimal overflow
            base_pool_size = max(1, pool_size - 1)
            max_overflow = pool_size - base_pool_size
        elif pool_size <= 20:
            # For small pools: use ~75% as base, ~25% as overflow
            base_pool_size = max(1, int(pool_size * 0.75))
            max_overflow = pool_size - base_pool_size
        elif pool_size <= 50:
            # For medium pools: use ~70% as base, ~30% as overflow
            base_pool_size = int(pool_size * 0.7)
            max_overflow = pool_size - base_pool_size
        else:
            # For large pools: use ~65% as base, ~35% as overflow
            base_pool_size = int(pool_size * 0.65)
            max_overflow = pool_size - base_pool_size
        return base_pool_size, max_overflow

    def _create_async_engine(self, dsn: str, pool_size: int) -> AsyncEngine:
        assert dsn.startswith("postgresql://"), "DSN must start with postgresql://"

        base_pool_size, max_overflow = self._compute_pool_base_and_overflow(pool_size)
        # See: https://docs.sqlalchemy.org/en/20/core/pooling.html for more details.
        return create_async_engine(
            dsn.replace("postgresql://", "postgresql+psycopg://"),
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=base_pool_size,  # number of persistent connections kept
            max_overflow=max_overflow,  # additional connections allowed above pool_size
        )

    async def setup(self) -> None:
        """Create and open the async connection pool."""
        if self._is_setup:
            return  # Already setup

        dsn = self._get_dsn()

        # Initialize SQLAlchemy engine
        # We assert the dsn starts with postgresql:// in _create_async_engine;
        # if that fails, the logic below needs to be updated

        # Same as with Psycopg, we create the engine
        # with the default pool size from PostgresConfig.
        self._sa_engine = self._create_async_engine(dsn=dsn, pool_size=PostgresConfig.pool_max_size)
        await self._run_migrations()

        # Run database reflection for SQLAlchemy
        await self._reflect_database(schema=self.V2_PREFIX.removesuffix("."))
        self._is_setup = True

    async def teardown(self) -> None:
        """Close the async connection pool."""
        # Close SQLAlchemy engine
        await super().teardown()
        self._is_setup = False

    async def apply_pool_size(self, new_max: int) -> None:
        """Resize psycopg pool to the new pool size.

        Validates against current psycopg min_size. On invalid values, raises
        PlatformHTTPError with BAD_REQUEST.
        """
        # Resize pool if available
        current_min = 1
        if new_max < current_min:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=(f"Invalid value for POSTGRES_POOL_MAX_SIZE: must be >= current min_size {current_min}"),
                data={
                    "new_value": new_max,
                    "current_min": current_min,
                },
            )

        # SQLAlchemy pool resizing
        dsn = self._get_dsn()
        new_engine = self._create_async_engine(
            dsn=dsn,
            pool_size=new_max,
        )

        old_engine: AsyncEngine | None = self._sa_engine
        self._sa_engine = new_engine
        self._logger.info("Resized/hot-swapped SQLAlchemy pool", new_max=new_max)
        # Note: the old engine could still be in use by other coroutines,
        # so, we don't dispose right away, rather we do it in a background task
        # waiting that no one is using it anymore.
        if old_engine is not None:
            task = asyncio.create_task(self._dispose_engine_when_no_connections_are_checked_out(old_engine))
            self._tasks.add(task)
            # Remove from tasks set when the task is done
            task.add_done_callback(lambda _: self._tasks.discard(task))

    def _get_dsn(self) -> str:
        return self._dns or PostgresConfig.dsn

    async def _run_migrations(self):
        await self._migrations.run_migrations()

    async def _dispose_engine_when_no_connections_are_checked_out(self, engine: AsyncEngine) -> None:
        try:
            import time

            timeout = 30
            start_time = time.time()
            pool = engine.sync_engine.pool
            checked_out = getattr(pool, "checkedout", None)
            assert checked_out is not None, "pool.checkedout() is not available"
            while checked_out() > 0:
                if time.time() - start_time > timeout:
                    logger.warning(
                        f"Timed out waiting for old engine to not have any checked out connections: {timeout} seconds. "
                        "Proceeding with disposal anyway."
                    )
                    break
                await asyncio.sleep(0.1)
            await engine.dispose()
        except Exception:
            # This is done in a background task, so, there's no point in raising the exception,
            # just log it.
            logger.exception("Error disposing engine", engine=engine)

    @asynccontextmanager
    async def _cursor(
        self,
    ) -> AsyncGenerator[AsyncCursor[DictRow], None]:
        """Yield an async SQLite cursor"""
        if not hasattr(self, "_sa_engine"):
            raise RuntimeError("Database not initialized; call setup() first.")

        async with self._read_connection() as conn:
            raw_conn = await conn.get_raw_connection()
            assert raw_conn.driver_connection is not None
            yield raw_conn.driver_connection.cursor(row_factory=dict_row)

    @asynccontextmanager
    async def _transaction(
        self,
    ) -> AsyncGenerator[AsyncCursor[DictRow], None]:
        """Yield an async SQLite cursor and then commit on exit or rollback on error."""
        if not hasattr(self, "_sa_engine"):
            raise RuntimeError("Database not initialized; call setup() first.")

        async with self._write_connection() as conn:
            raw_conn = await conn.get_raw_connection()
            assert raw_conn.driver_connection is not None
            yield raw_conn.driver_connection.cursor(row_factory=dict_row)

    def _clean_up_stale_threads__get_threshold(
        self,
        now: datetime,
        config_column: sa.Column,
    ) -> sa.sql.ClauseElement:
        return sa.literal(now) - (
            # Strange way of converting JSONB to text
            sa.cast(config_column.op("#>>")(sa.literal_column("'{}'::text[]")), sa.Integer)
            * sa.text("interval '1 day'")
        )
