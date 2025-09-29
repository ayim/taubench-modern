import asyncio
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import sqlalchemy as sa
from aiosqlite import Connection, Cursor, Row, connect
from sqlalchemy.ext.asyncio import create_async_engine
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
from agent_platform.server.storage.sqlite.storage_document_intelligence import (
    SQLiteStorageDocumentIntelligenceMixin,
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
    SQLiteStorageDocumentIntelligenceMixin,
    BaseStorage,
):
    """
    SQLite-based storage that mirrors the Postgres-based semantics, including
    a 'v2_check_user_access' custom function used in the SQL statements.
    """

    V2_PREFIX = "v2_"

    _read_conn: Connection | None = None
    _write_conn: Connection | None = None

    def __init__(self, db_path: str | None = None):
        # Initialize all parent mixins (including CommonMixin for secret manager)
        super().__init__()

        self._logger = get_logger(__name__)
        self._db_path = db_path or self._get_db_path()
        self._migrations = SQLiteMigrations(self._db_path)
        self._is_setup = False
        self._write_lock = asyncio.Lock()
        _register_sqlite_adapters()

    async def setup(self) -> None:
        """Create and open the SQLite database connection, enable foreign keys,
        set up function, run migrations."""
        if self._is_setup:
            return  # Already setup

        # Initialize dedicated read and write connections
        # Some imprecise benchmarking shows a 2-3x slowdown creating a new connection
        # for every read operation.
        self._write_conn = await self._conn_factory()
        self._read_conn = await self._conn_factory()

        # Initialize SQLAlchemy engine
        sqlite_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._engine = create_async_engine(
            sqlite_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # Run migrations in setup
        await self._run_migrations()

        # Run database reflection for SQLAlchemy
        await self._reflect_database()

        self._is_setup = True

    async def _conn_factory(self) -> Connection:
        """
        Create and configure a new SQLite connection.
        """
        # Increase timeout to 10 seconds (from 5seconds) to avoid "Database is locked" errors
        # TODO allow this value to be configurable.
        conn = await connect(self._db_path, timeout=10)

        await conn.execute("PRAGMA foreign_keys = ON")
        # Keep turn on WAL mode, avoids reads and writes from blocking each other
        await conn.execute("PRAGMA journal_mode = WAL")
        # Fsync less often, but still "enough".
        await conn.execute("PRAGMA synchronous = NORMAL")
        conn.row_factory = Row

        # ---------------------------------------------------------------------
        # Register the check_user_access function in SQLite
        # ---------------------------------------------------------------------
        def check_user_access(record_user_id: str, requesting_user_id: str) -> int:
            """
            Return 1 if requesting_user_id can access record_user_id's resource, else 0.
            - If record_user_id is 'system user', OK
            - If requesting_user_id is 'system user', OK
            - If record_user_id <= requesting_user_id, OK
            - Else no access
            Because SQLite UDFs must be synchronous, we use the synchronous connection.
            """
            if not self._is_setup:
                raise RuntimeError("Database not initialized; call setup() first.")

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
            finally:
                if cursor1 is not None:
                    cursor1.close()

            if record_user is None or requesting_user is None:
                return 0

            # record user is a system user (worker agents)
            # any resources created by this user are accessible to all users of Workroom
            record_sub_value = record_user["sub"]
            sys_user_pattern = r"^tenant:.*:system:system_user$"
            if record_sub_value and bool(re.match(sys_user_pattern, record_sub_value)):
                return 1

            # system users can access all resources
            req_sub_value = requesting_user["sub"]
            if req_sub_value and bool(re.match(sys_user_pattern, req_sub_value)):
                return 1

            # an user can access resources whose owner's sub is a prefix of their sub
            if record_sub_value in req_sub_value:
                return 1

            return 0

        # Create the function in the current DB connection
        await conn.create_function("v2_check_user_access", 2, check_user_access)

        return conn

    async def teardown(self) -> None:
        """Close the SQLite database connection."""
        # Close SQLAlchemy engine
        if hasattr(self, "_engine") and self._engine is not None:
            await self._engine.dispose()
            self._engine = None  # type: ignore

        if self._is_setup:
            if self._write_conn is not None:
                await self._write_conn.close()
                self._write_conn = None
            if self._read_conn is not None:
                await self._read_conn.close()
                self._read_conn = None

            self._is_setup = False

    def _get_db_path(self) -> str:
        """Get the SQLite database path."""

        db_path = get_sqlite_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._logger.info("Using SQLite database path: %s", db_path)
        return str(db_path)

    async def _run_migrations(self):
        await self._migrations.run_migrations()

    @asynccontextmanager
    async def _cursor(
        self,
    ) -> AsyncGenerator[Cursor, None]:
        """Yield an async SQLite cursor"""
        if not self._read_conn:
            raise RuntimeError("Database not initialized; call setup() first.")
        yield await self._read_conn.cursor()

    @asynccontextmanager
    async def _transaction(
        self,
    ) -> AsyncGenerator[Cursor, None]:
        """Yield an async SQLite cursor and then commit on exit."""
        # TODO handle reeentrant transactions
        if not self._write_conn:
            raise RuntimeError("Database not initialized; call setup() first.")

        # Because we have all callers sharing the same write connection, we need
        # to explicitly lock it to avoid concurrent commits on this one connection.
        # Like read connection latency, we don't want to open a new connection every
        # time. We need to figure come back and rework how we inject database connections.
        await self._write_lock.acquire()

        try:
            yield await self._write_conn.cursor()

            await self._write_conn.commit()
        except Exception as e:
            await self._write_conn.rollback()
            raise e
        finally:
            self._write_lock.release()

    def _clean_up_stale_threads__get_threshold(
        self,
        now: datetime,
        config_column: sa.Column,
    ):
        """Get Interval for cleaning up stale threads"""
        return sa.text(
            f"datetime('{now.isoformat()}', '-' "
            f"|| CAST(json_extract({config_column.name}, '$') AS integer) || ' days')"
        )
