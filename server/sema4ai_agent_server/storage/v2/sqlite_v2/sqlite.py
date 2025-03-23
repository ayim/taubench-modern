from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from aiosqlite import Cursor, Row, connect
from structlog import get_logger

from sema4ai_agent_server.storage.v2.sqlite_v2.migrations import SQLiteMigrationsV2
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_agents import (
    SQLiteStorageAgentsMixin,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_artifacts import (
    SQLiteStorageArtifactsMixin,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_files import (
    SQLiteStorageFilesMixin,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_memory import (
    SQLiteStorageMemoriesMixin,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_messages import (
    SQLiteStorageMessagesMixin,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_runs import (
    SQLiteStorageRunsMixin,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_scoped_storage import (
    SQLiteStorageScopedStorageMixin,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_threads import (
    SQLiteStorageThreadsMixin,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.storage_users import (
    SQLiteStorageUsersMixin,
)


class SQLiteStorageV2(
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
        self._migrations = SQLiteMigrationsV2(self._db_path)
        self._is_setup = False

    async def setup_v2(self) -> None:
        """Create and open the SQLite database connection, enable foreign keys, set up function, run migrations."""
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

    async def teardown_v2(self) -> None:
        """Close the SQLite database connection."""
        if self._is_setup and self._db is not None:
            await self._db.close()
            self._db = None
        self._is_setup = False

    def _get_db_path(self) -> str:
        """Get the SQLite database path, defaulting to ./agentserver.db if env var not set."""
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

