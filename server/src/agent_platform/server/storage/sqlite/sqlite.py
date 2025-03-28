from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from aiosqlite import Cursor, Row, connect
from structlog import get_logger

from agent_platform.server.storage.sqlite.migrations import SQLiteMigrations
from agent_platform.server.storage.sqlite.storage_agents import (
    SQLiteStorageAgentsMixin,
)
from agent_platform.server.storage.sqlite.storage_artifacts import (
    SQLiteStorageArtifactsMixin,
)
from agent_platform.server.storage.sqlite.storage_files import (
    SQLiteStorageFilesMixin,
)
from agent_platform.server.storage.sqlite.storage_memory import (
    SQLiteStorageMemoriesMixin,
)
from agent_platform.server.storage.sqlite.storage_messages import (
    SQLiteStorageMessagesMixin,
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
    SQLiteStorageScopedStorageMixin,
    SQLiteStorageFilesMixin,
):
    """
    SQLite-based storage that mirrors the Postgres-based semantics, including
    a 'v2_check_user_access' custom function used in the SQL statements.
    """

    def __init__(self, db_path: str | None = None):
        self._logger = get_logger(__name__)
        self._db_path = db_path or self._get_db_path()
        self._migrations = SQLiteMigrations(self._db_path)
        self._is_setup = False
        _register_sqlite_adapters()

    async def setup(self) -> None:
        """Create and open the SQLite database connection, enable foreign keys,
        set up function, run migrations."""
        if self._is_setup:
            return  # Already setup

        self._db = await connect(self._db_path)
        await self._db.execute("PRAGMA foreign_keys = ON")
        self._db.row_factory = Row

        # ---------------------------------------------------------------------
        # Register the check_user_access function in SQLite
        # ---------------------------------------------------------------------
        def check_user_access(record_user_id: str, requesting_user_id: str) -> int:
            """
            Return 1 if requesting_user_id can access record_user_id's resource, else 0.
            - If record_user_id == requesting_user_id, OK
            - If requesting_user_id is 'system user', OK
            - Else no access
            Because SQLite UDFs must be synchronous, we use the synchronous connection.
            """
            # If either of the inputs is empty, return 0
            if not record_user_id or not requesting_user_id:
                return 0

            # Quick check: if same user, yes
            if record_user_id == requesting_user_id:
                return 1

            # Otherwise, see if requesting_user_id is a system user
            # i.e. sub like 'tenant:%:system:system_user'
            # Use the underlying sync connection from aiosqlite
            cur = self._db._conn.execute(  # Access the synchronous sqlite3.Connection
                """
                SELECT 1
                FROM v2_user
                WHERE user_id = ?
                  AND sub LIKE 'tenant:%:system:system_user'
                """,
                (requesting_user_id,),
            )
            result = cur.fetchone()
            cur.close()  # Important to close the cursor
            return 1 if result else 0

        # Create the function in the current DB connection
        await self._db.create_function("v2_check_user_access", 2, check_user_access)

        # Run migrations
        await self._run_migrations()
        self._is_setup = True

    async def teardown(self) -> None:
        """Close the SQLite database connection."""
        if self._is_setup and self._db is not None:
            await self._db.close()
            self._db = None
        self._is_setup = False

    def _get_db_path(self) -> str:
        """Get the SQLite database path, defaulting to
        ./agentserver.db if env var not set."""
        from os import getenv
        base_dir = getenv("SEMA4AI_STUDIO_HOME")
        if not base_dir:
            base_dir = Path(".")  # Default to a current working directory

        db_path = Path(base_dir) / "agentserver.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._logger.info("Using SQLite database path", path=str(db_path.absolute()))
        return str(db_path.absolute())

    async def _run_migrations(self):
        await self._migrations.run_migrations()

    @asynccontextmanager
    async def _cursor(self, cursor: Cursor|None=None) -> AsyncGenerator[Cursor, None]:
        """Yield an async SQLite cursor and then commit on exit."""
        if not self._db:
            raise RuntimeError("Database not initialized; call setup_v2() first.")
        if cursor is None:
            cursor = await self._db.cursor()
        yield cursor
        await self._db.commit()

