import asyncio
import functools
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

import sqlalchemy as sa
from aiosqlite import Connection, Cursor, Row
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from structlog import get_logger

from agent_platform.core.configurations.base import Configuration, FieldMetadata
from agent_platform.server.constants import SystemPaths
from agent_platform.server.storage.base import BaseStorage
from agent_platform.server.storage.sqlite.migrations import SQLiteMigrations
from agent_platform.server.storage.sqlite.storage_agents import (
    SQLiteStorageAgentsMixin,
)
from agent_platform.server.storage.sqlite.storage_artifacts import (
    SQLiteStorageArtifactsMixin,
)
from agent_platform.server.storage.sqlite.storage_config import (
    SQLiteStorageConfigMixin,
)
from agent_platform.server.storage.sqlite.storage_files import (
    SQLiteStorageFilesMixin,
)
from agent_platform.server.storage.sqlite.storage_mcp_servers import (
    SQLiteStorageMCPServersMixin,
)
from agent_platform.server.storage.sqlite.storage_memory import (
    SQLiteStorageMemoriesMixin,
)
from agent_platform.server.storage.sqlite.storage_messages import (
    SQLiteStorageMessagesMixin,
)
from agent_platform.server.storage.sqlite.storage_platform_configs import (
    SQLiteStoragePlatformConfigsMixin,
)
from agent_platform.server.storage.sqlite.storage_runs import (
    SQLiteStorageRunsMixin,
)
from agent_platform.server.storage.sqlite.storage_scoped_storage import (
    SQLiteStorageScopedStorageMixin,
)
from agent_platform.server.storage.sqlite.storage_threads import (
    SQLiteStorageThreadsMixin,
)
from agent_platform.server.storage.sqlite.storage_users import (
    SQLiteStorageUsersMixin,
)
from agent_platform.server.storage.sqlite.storage_work_items import (
    SQLiteStorageWorkItemsMixin,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class SQLiteConfig(Configuration):
    """Configuration for the SQLite database."""

    depends_on: ClassVar[list[type[Configuration]]] = [SystemPaths]

    db_path: Path = field(
        default=Path("agentserver.db"),
        metadata=FieldMetadata(
            description=(
                "The path to the SQLite database file. If a relative path is given, "
                "it will be interpreted relative to the server's data directory."
            ),
            env_vars=["SEMA4AI_AGENT_SERVER_SQLITE_DB_PATH"],
        ),
    )

    def __post_init__(self) -> None:
        """Initialize derived paths after the main paths are set."""
        # We need to use object.__setattr__ because the dataclass is frozen
        if not self.db_path.is_absolute():
            object.__setattr__(self, "db_path", SystemPaths.data_dir / self.db_path)


# Note by fabioz: this was done because the __post_init__ method above was called before
# the SystemPaths configuration was fully done (it was called in `_load_registered_configurations`
# whereas the command line overrides were applied in `_apply_overrides` done after that)
# Debugged a bit and found the config system is way to complex to try to fix (and we should
# at some point stop using it altogether as it requires a bunch of classes to be preloaded)
# So, this is a hack to make the sqlite config have the proper path for me (note: I can't reproduce
# this reliably, but at some point when running
#  `test_generate_semantic_data_model_generation_integration`
# it was using the wrong path consistently).
def get_sqlite_db_path() -> Path:
    db_path = SQLiteConfig.db_path
    if not db_path.is_absolute():
        return SystemPaths.data_dir / db_path
    return db_path


def _register_sqlite_adapters():
    """
    Register adapters and converters for the SQLite database.
    In Python 3.12, the default datetime adapter has been
    deprecated.
    """
    from sqlite3 import register_adapter, register_converter

    def _adapt_datetime_iso(date_time: datetime) -> str:
        """
        Convert a Python datetime.datetime into a timezone-naive
        ISO 8601 date string.
        """
        return date_time.isoformat()

    def _convert_timestamp(time_stamp: bytes) -> datetime:
        """
        Convert an ISO 8601 formatted bytestring
        to a datetime.datetime object.
        """
        return datetime.strptime(time_stamp.decode("utf-8"), "%Y-%m-%dT%H:%M:%S.%f")

    register_adapter(datetime, _adapt_datetime_iso)
    register_converter("timestamp", _convert_timestamp)


class ReentrantAsyncLock:
    """
    An asyncio-compatible lock that is reentrant.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._owner: asyncio.Task | None = None
        self._count: int = 0

    async def _acquire(self) -> bool:
        current = asyncio.current_task()
        if current is None:
            raise RuntimeError("ReentrantAsyncLock must be used within an asyncio task")

        if self._lock.locked() and self._owner is current:
            self._count += 1
            return True

        await self._lock.acquire()
        self._count += 1
        self._owner = current
        return True

    def _release(self) -> None:
        current = asyncio.current_task()
        if current is None:
            raise RuntimeError("ReentrantAsyncLock.release() must be called within an asyncio task")

        if not self._lock.locked():
            raise RuntimeError("Release called on an unlocked ReentrantAsyncLock")

        if self._owner is not current:
            raise RuntimeError("Only the owning task can release this lock")

        if self._count == 1:
            self._count -= 1
            # Keep on going to release the lock
        elif self._count > 1:
            self._count -= 1
            return
        else:  # self._count == 0:
            raise RuntimeError("Release called without acquiring the lock")

        self._owner = None
        self._lock.release()

    async def __aenter__(self) -> Self:
        await self._acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self._release()


# ---------------------------------------------------------------------
# Register the check_user_access function in SQLite
# ---------------------------------------------------------------------
def check_user_access(dbapi_conn, record_user_id: str, requesting_user_id: str) -> int:
    """
    Return 1 if requesting_user_id can access record_user_id's resource, else 0.
    - If record_user_id is 'system user', OK
    - If requesting_user_id is 'system user', OK
    - If record_user_id <= requesting_user_id, OK
    - Else no access
    Because SQLite UDFs must be synchronous, we use the synchronous connection.

    TODO: Remove this altogeter, doing additional checks this way is not efficient and doing additional queries in
    a registered function is not recommended (creating a helper function which actually does things asynchronously
    and use that to check access would be better)
    """
    import re

    conn = dbapi_conn._connection

    cursor0 = None
    cursor1 = None
    try:
        cursor0 = conn._conn.execute(
            """
            SELECT sub
            FROM v2_user
            WHERE user_id = ?
            """,
            (record_user_id,),
        )
        record_user = cursor0.fetchone()
    except Exception:
        logger.exception("Error fetching record user")
        return 0  # We cannot access it: return 0
    finally:
        if cursor0 is not None:
            cursor0.close()

    try:
        cursor1 = conn._conn.execute(
            """
            SELECT sub
            FROM v2_user
            WHERE user_id = ?
            """,
            (requesting_user_id,),
        )
        requesting_user = cursor1.fetchone()
    except Exception:
        logger.exception("Error fetching requesting user")
        return 0  # We cannot access it: return 0
    finally:
        if cursor1 is not None:
            cursor1.close()

    if record_user is None or requesting_user is None:
        return 0

    # record user is a system user (worker agents)
    # any resources created by this user are accessible to all users of Workroom
    record_sub_value = record_user["sub"]
    sys_user_pattern = r"^tenant:.*:.*:system_user$"
    if record_sub_value and bool(re.match(sys_user_pattern, record_sub_value)):
        return 1

    # system users can access all resources
    req_sub_value = requesting_user["sub"]
    if req_sub_value and bool(re.match(sys_user_pattern, req_sub_value)):
        return 1

    # a user can access resources whose owner's sub is a prefix of their sub
    if req_sub_value.startswith(record_sub_value):
        return 1

    return 0


class SQLiteStorage(
    # Careful: order matters!
    SQLiteStorageArtifactsMixin,
    SQLiteStorageAgentsMixin,
    SQLiteStorageThreadsMixin,
    SQLiteStorageMessagesMixin,
    SQLiteStorageUsersMixin,
    SQLiteStorageMemoriesMixin,
    SQLiteStorageRunsMixin,
    SQLiteStorageWorkItemsMixin,
    SQLiteStorageScopedStorageMixin,
    SQLiteStorageFilesMixin,
    SQLiteStorageMCPServersMixin,
    SQLiteStoragePlatformConfigsMixin,
    SQLiteStorageConfigMixin,
    BaseStorage,
):
    """
    SQLite-based storage that mirrors the Postgres-based semantics, including
    a 'v2_check_user_access' custom function used in the SQL statements.
    """

    V2_PREFIX = "v2_"

    def __init__(self, db_path: str | None = None):
        # Initialize all parent mixins (including CommonMixin for secret manager)
        super().__init__()

        self._logger = get_logger(__name__)
        self._db_path = db_path or self._get_db_path()
        self._is_setup = False
        self._write_lock = ReentrantAsyncLock()

    async def setup(self, migrate: bool = True) -> None:
        """Create and open the SQLite database connection, enable foreign keys,
        set up function, run migrations."""
        if self._is_setup:
            return  # Already setup

        _register_sqlite_adapters()

        # Initialize SQLAlchemy engine
        sqlite_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._sa_engine = create_async_engine(
            sqlite_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # Override the SQLite dialect's DateTime type descriptor to use ISO8601 format
        #
        # Background:
        # - SQLAlchemy's default DateTime handling for SQLite uses space separator
        #   (e.g., '2024-12-10 17:09:32.500537')
        # - We want to store datetimes in ISO8601 format with 'T' separator
        #   (e.g., '2024-12-10T17:09:32.500537')
        #
        # Solution:
        # - Override the dialect's type_descriptor method to inject a custom
        #   bind_processor for all DateTime types
        # - This ensures datetime.isoformat() is used for ALL datetime bind parameters,
        # - This works with reflected tables (our current pattern)
        from sqlalchemy.types import DateTime as SQLAlchemyDateTime

        original_type_descriptor = self._sa_engine.sync_engine.dialect.type_descriptor

        def custom_type_descriptor(typeobj):
            """Override type descriptor to customize DateTime for SQLite."""
            result = original_type_descriptor(typeobj)
            if isinstance(result, SQLAlchemyDateTime):
                # Inject a custom bind processor that uses ISO8601 format
                def iso_bind_processor(value):
                    if value is not None:
                        return value.isoformat()
                    return value

                # Replace bind_processor method for this DateTime type instance
                result.bind_processor = lambda dialect: iso_bind_processor
            return result

        # Monkey-patch the dialect's type_descriptor method
        self._sa_engine.sync_engine.dialect.type_descriptor = custom_type_descriptor  # type: ignore[method-assign]

        # Enable foreign keys for all SQLAlchemy connections
        from sqlalchemy import event

        @event.listens_for(self._sa_engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # Keep turn on WAL mode, avoids reads and writes from blocking each other
            cursor.execute("PRAGMA journal_mode = WAL")
            # Fsync less often, but still "enough".
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.close()

            func = functools.partial(check_user_access, dbapi_conn)
            dbapi_conn.create_function("v2_check_user_access", 2, func)

        # Run migrations in setup
        if migrate:
            await self._run_migrations()

        # Run database reflection for SQLAlchemy
        await self._reflect_database()

        self._is_setup = True

    async def teardown(self) -> None:
        """Close the SQLite database connection."""
        # Close SQLAlchemy engine
        await super().teardown()

        if self._is_setup:
            self._is_setup = False

    def _get_db_path(self) -> str:
        """Get the SQLite database path."""

        db_path = get_sqlite_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._logger.info("Using SQLite database path: %s", db_path)
        return str(db_path)

    async def _run_migrations(self):
        await SQLiteMigrations(self).run_migrations()

    @asynccontextmanager
    async def _cursor(
        self,
    ) -> AsyncGenerator[Cursor, None]:
        """Yield an async SQLite cursor"""
        async with self._read_connection() as conn:
            raw_conn = await conn.get_raw_connection()
            assert raw_conn.driver_connection is not None

            raw_conn.driver_connection._connection.row_factory = Row
            cursor = await raw_conn.driver_connection.cursor()
            yield cursor

    @asynccontextmanager
    async def _transaction(
        self,
    ) -> AsyncGenerator[Cursor, None]:
        """Yield an async SQLite cursor and then commit on exit or rollback on error."""
        async with self._transaction_connection() as conn:
            yield await conn.cursor()

    async def _is_in_native_transaction(self, conn: AsyncConnection) -> bool:
        """Determine if the connection is in a native transaction (not managed by sqlalchemy)."""
        native_connection = (await conn.get_raw_connection()).driver_connection
        return native_connection is not None and native_connection.in_transaction

    @asynccontextmanager
    async def _transaction_connection(
        self,
    ) -> AsyncGenerator[Connection, None]:
        """Yield an async SQLite cursor and then commit on exit or rollback on error."""
        async with self._write_connection() as conn:
            raw_conn = await conn.get_raw_connection()
            assert raw_conn.driver_connection is not None
            raw_conn.driver_connection._connection.row_factory = Row

            if not (await self._is_in_native_transaction(conn)):
                # Force the transaction to be started.
                await conn.exec_driver_sql("BEGIN")
                assert await self._is_in_native_transaction(conn)

            yield raw_conn.driver_connection

    def _clean_up_stale_threads__get_threshold(
        self,
        now: datetime,
        config_column: sa.Column,
    ):
        """Get Interval for cleaning up stale threads"""
        return sa.text(
            f"datetime('{now.isoformat()}', '-' || CAST(json_extract({config_column.name}, '$') AS integer) || ' days')"
        )

    async def apply_pool_size(self, new_max: int) -> None:
        # No-op on SQLite since we don't support this function on SQLite
        pass
