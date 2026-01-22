from hashlib import sha256
from os import listdir, path
from pathlib import Path
from typing import TYPE_CHECKING

from psycopg.errors import QueryCanceled
from psycopg.sql import SQL
from structlog import get_logger

from agent_platform.server.storage.migrations import (
    InvalidMigrationFilenameError,
    MigrationError,
    MigrationsProvider,
    MigrationTimeoutError,
)

if TYPE_CHECKING:
    from agent_platform.server.storage.postgres.postgres import PostgresStorage

logger = get_logger(__name__)


class PostgresMigrations(MigrationsProvider):
    """
    Provides Postgres-based migration functionality
    with safety and reliability features.

    Key points:
      1) Each migration is tracked as a row in v2.migrations
         (version, dirty, checksum, applied_at).
      2) Locking is performed via a v2.migration_locks table,
         with locked_by using pg_backend_pid().
      3) We detect 'dirty' (partially applied) migrations and
         'checksum drift' (when a previously applied migration's
         SQL changes).
      4) Each migration is applied in its own set of transactions:
         - Insert row dirty=TRUE
         - Actually run the SQL
         - Mark dirty=FALSE
      5) Timeout is enforced using Postgres' statement_timeout
         setting, which will cancel long-running queries
         server-side.
    """

    def __init__(
        self,
        storage: "PostgresStorage",
        timeout: float = 300.0,
        migrations_path: Path | None = None,
    ):
        """
        Initializes a Migrations Provider for Postgres.

        Arguments:
            storage: PostgresStorage instance to use for database operations.
            timeout: Timeout (in seconds) for each migration statement.
            migrations_path: Path to the directory containing .up.sql files (optional).
        """
        import weakref

        self.__storage = weakref.ref(storage)
        self._logger = get_logger(__name__)
        self._timeout = timeout
        self._migrations_path = migrations_path if migrations_path is not None else self._get_migrations_path()

    @property
    def _storage(self) -> "PostgresStorage":
        ret = self.__storage()
        assert ret is not None, "Storage is not initialized or is already garbage collected"
        return ret

    def _get_migrations_path(self) -> Path:
        current_dir = path.dirname(path.abspath(__file__))
        return Path(current_dir).parent.parent / "migrations" / "postgres"

    async def run_migrations(self) -> None:
        """
        Main entrypoint for running migrations:
          1) Acquire migration lock
          2) Ensure v2_migrations table
          3) Check for any 'dirty' migrations => if found, raise error
          4) Gather and sort the .up.sql files by version
          5) For each file, check if it's already in DB:
             - If yes, verify same checksum => drift check
             - If dirty => raise
             - Else skip
             - If not in DB => apply:
               (a) Insert row with dirty=TRUE
               (b) Run the migration
               (c) Mark dirty=FALSE
          6) Release lock
        """
        locked_acquired_by = None
        try:
            locked_acquired_by = await self._acquire_migration_lock()
            if not locked_acquired_by:
                logger.warning("Skipping migrations because another migration is running.")
                return

            await self._ensure_migrations_table()

            # Get existing migration states from DB
            applied: dict[int, dict] = {}
            async with self._storage._cursor() as cur:
                await cur.execute(
                    """
                    SELECT version, checksum, dirty FROM v2.migrations
                    ORDER BY version
                    """,
                )
                rows = await cur.fetchall()
                for row in rows:
                    applied[row["version"]] = {
                        "checksum": row["checksum"],
                        "dirty": row["dirty"],
                    }

            # Gather .up.sql files
            migration_files = []
            for fname in listdir(self._migrations_path):
                if fname.endswith(".down.sql"):
                    continue
                try:
                    version, desc = self._validate_migration_filename(fname)
                    migration_files.append((version, desc, fname))
                except InvalidMigrationFilenameError as e:
                    self._logger.warning(str(e))
                    continue

            # Sort by version ascending
            migration_files.sort(key=lambda x: x[0])

            # For each migration file
            for version, _, filename in migration_files:
                # Read the file contents -> compute new checksum
                fpath = path.join(self._migrations_path, filename)
                with open(fpath) as f:
                    raw_sql = f.read().strip()
                new_checksum = sha256(raw_sql.encode()).hexdigest()

                # Validate the migration file has no transaction commands
                self._validate_migration_has_no_transaction_commands(raw_sql)

                if version in applied:
                    # Already known in DB -> check dirty, check drift
                    old = applied[version]
                    if old["dirty"]:
                        raise MigrationError(
                            f"Migration {version} is dirty. No migrations will be applied. Please fix it manually.",
                        )

                    # Fail loudly if there's a migration that already exists with the wrong SHA
                    if old["checksum"] != new_checksum:
                        raise MigrationError(
                            f"Checksum drift detected for migration {version}. "
                            f"Existing: {old['checksum']}, New: {new_checksum}.",
                        )

                    # Otherwise it's already applied => skip
                    continue
                else:
                    # This version is new -> actually apply it
                    await self._apply_migration(
                        version,
                        filename,
                        new_checksum,
                    )
        finally:
            if locked_acquired_by:
                # Release the lock with a *fresh* transaction so we aren't stuck
                # if the above transaction ended in error/timeout.
                await self._release_migration_lock(locked_acquired_by)

    # -------------------------------------------------------------------------
    # Locking
    # -------------------------------------------------------------------------
    async def _acquire_migration_lock(self) -> str | None:
        """
        Lock logic to ensure only one migrator runs at a time.

        !!! IMPORTANT !!!
        Postgres has multiple worker processes,
        so the process that releases the lock
        might be different from the process that acquires it.
        """
        async with self._storage._transaction() as cur:
            await cur.execute("CREATE SCHEMA IF NOT EXISTS v2;")
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2.migration_locks (
                    id INTEGER PRIMARY KEY,
                    locked_at TIMESTAMP WITH TIME ZONE,
                    locked_by TEXT
                );
                """,
            )
            await cur.execute(
                """
                INSERT INTO v2.migration_locks (id, locked_at, locked_by)
                VALUES (1, CURRENT_TIMESTAMP, pg_backend_pid()::text)
                ON CONFLICT (id) DO UPDATE
                    SET locked_at = EXCLUDED.locked_at,
                        locked_by = EXCLUDED.locked_by
                    WHERE
                      migration_locks.locked_at < CURRENT_TIMESTAMP - INTERVAL '10 minutes'
                RETURNING locked_by;
                """,
            )
            row = await cur.fetchone()

            if row:
                return row["locked_by"]
            else:
                logger.error(
                    f"Could not acquire migration lock. Another migration might be in progress. {row!r}",
                )
                return None

    async def _release_migration_lock(self, locked_by: str) -> None:
        """
        Releases the migration lock if we hold it.
        """
        async with self._storage._transaction() as cur:
            # Check if table exists
            await cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'migration_locks' AND table_schema = 'v2'
                );
                """,
            )
            result = await cur.fetchone()
            table_exists = result["exists"] if result else False
            if table_exists:
                # Release only if locked_by matches
                await cur.execute(
                    """
                    DELETE FROM v2.migration_locks
                    WHERE locked_by = %s
                    """,
                    [locked_by],
                )

    # -------------------------------------------------------------------------
    # Migrations Table
    # -------------------------------------------------------------------------
    async def _ensure_migrations_table(self) -> None:
        """Ensures the v2.migrations table exists (1 row per version)."""
        async with self._storage._transaction() as cur:
            await cur.execute("CREATE SCHEMA IF NOT EXISTS v2;")
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2.migrations (
                    version BIGINT PRIMARY KEY,
                    dirty BOOLEAN NOT NULL DEFAULT FALSE,
                    checksum VARCHAR(64) NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """,
            )

    # -------------------------------------------------------------------------
    # Applying Migrations
    # -------------------------------------------------------------------------
    async def _apply_migration(
        self,
        version: int,
        filename: str,
        checksum: str,
    ) -> None:
        """
        Apply a single migration:
         1) Insert row with dirty=TRUE
         2) Run the migration in its own transaction (with statement_timeout)
         3) Mark dirty=FALSE
        """
        self._logger.info(f"Applying migration {filename}")

        # Step 1: Insert row with dirty=TRUE
        try:
            async with self._storage._transaction() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2.migrations (version, dirty, checksum)
                    VALUES (%s, TRUE, %s)
                    """,
                    (version, checksum),
                )
        except Exception as e:
            self._logger.error(f"Failed to insert row for migration {filename}: {e}")
            raise MigrationError(f"Could not mark version={version} as dirty") from e

        # Step 2: Actually run the migration in its own transaction
        migration_sql_path = path.join(self._migrations_path, filename)
        with open(migration_sql_path) as f:
            migration_sql = f.read().strip()
            if not migration_sql:
                raise MigrationError(f"Migration file {filename} is empty.")

        try:
            # If migration times out, _run_migration_with_timeout()
            # raises MigrationTimeoutError
            await self._run_migration_with_timeout(migration_sql)
        except MigrationTimeoutError as mte:
            # Timed out: remain dirty
            self._logger.error(f"Migration {version} timed out: {mte}")
            raise
        except Exception as e:
            # Another error => remain dirty
            self._logger.error(f"Migration {version} failed: {e}")
            raise MigrationError(f"Migration {version} failed: {e!s}") from e

        # Step 3: Mark dirty=FALSE
        try:
            async with self._storage._transaction() as cur:
                await cur.execute(
                    "UPDATE v2.migrations SET dirty = FALSE WHERE version = %s;",
                    (version,),
                )
        except Exception as e:
            self._logger.error(f"Failed to mark migration {version} as clean: {e}")
            raise MigrationError(
                f"Could not mark version={version} as non-dirty",
            ) from e

        self._logger.info(f"Successfully applied migration {filename}")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _validate_migration_filename(self, filename: str) -> tuple[int, str]:
        """
        Validates migration filename format: <version>_<description>.up.sql
        e.g. 1_create_users.up.sql -> (1, "create_users")
        """
        import re

        pattern = r"^(\d+)_([a-z0-9_]+)\.up\.sql$"
        match = re.match(pattern, filename)
        if not match:
            raise InvalidMigrationFilenameError(
                f"Invalid migration filename: {filename}. Expected '<version>_<desc>.up.sql'",
            )

        version = int(match.group(1))
        description = match.group(2)
        return version, description

    def _validate_migration_has_no_transaction_commands(
        self,
        migration_sql: str,
    ) -> None:
        """
        Ensures the migration SQL does not contain any transaction commands
        (e.g., BEGIN, COMMIT).
        """
        from re import MULTILINE, search

        if search(r"^\s*BEGIN;\s*", migration_sql, MULTILINE):
            raise MigrationError("Migration file contains 'BEGIN;'")
        if search(r"^\s*COMMIT;\s*", migration_sql, MULTILINE):
            raise MigrationError("Migration file contains 'COMMIT;'")
        if search(r"^\s*ROLLBACK;\s*", migration_sql, MULTILINE):
            raise MigrationError("Migration file contains 'ROLLBACK;'")

    async def _run_migration_with_timeout(
        self,
        migration_sql: str,
    ) -> None:
        """
        Runs migration_sql with a Postgres-side *local* statement_timeout
        so the server cancels the query if it exceeds self._timeout.
        This version uses the storage's transaction method which handles BEGIN/COMMIT automatically.
        """
        statement_ms = int(self._timeout * 1000)
        try:
            async with self._storage._transaction() as cur:
                # Only affects the current transaction scope
                # Using SQL().format() to safely insert the timeout value
                await cur.execute(SQL("SET LOCAL statement_timeout = {}").format(statement_ms))
                # migration_sql is trusted SQL from our migration files
                await cur.execute(SQL(migration_sql))  # type: ignore[arg-type]

        except QueryCanceled as exc:
            # Postgres forcibly canceled the query due to statement_timeout
            # The transaction context manager will handle rollback automatically
            raise MigrationTimeoutError(
                f"Migration timed out after {self._timeout} seconds",
            ) from exc
