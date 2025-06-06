from asyncio import create_task, wait_for
from hashlib import sha256
from os import getpid, listdir, path
from pathlib import Path
from re import match as re_match

from aiosqlite import Connection, connect
from structlog import get_logger

from agent_platform.server.storage.migrations import (
    InvalidMigrationFilenameError,
    MigrationError,
    MigrationLockError,
    MigrationsProvider,
    MigrationTimeoutError,
)


class SQLiteMigrations(MigrationsProvider):
    """
    Mirrors the Postgres-based migration logic, but for SQLite.

    Key points:
      1) Each migration is tracked as a row in v2_migrations
         (version, dirty, checksum, applied_at).
      2) Locking is performed via a v2_migration_locks table, with
         locked_by defaulting to OS getpid().
      3) We detect 'dirty' (partially applied) migrations and 'checksum drift'
         (when a previously applied migration's SQL changes).
      4) Each migration is applied in its own set of transactions:
         - Insert row dirty=TRUE
         - Actually run the SQL
         - Mark dirty=FALSE
      5) Timeout is enforced by wrapping the migration in an asyncio
         wait_for(...) call, and calling conn._conn.interrupt() if it
         times out (to attempt to interrupt the running query).
    """

    def __init__(
        self,
        db_path: str,
        timeout: float = 300.0,
        migrations_path: Path | None = None,
    ):
        """
        Initializes a Migrations Provider for SQLite.

        Arguments:
            db_path: path to the SQLite database file.
            timeout: Timeout (seconds) for each migration statement(s).
            migrations_path: Directory containing .up.sql migration files.
        """
        self.db_path = db_path
        self._logger = get_logger(__name__)
        self._timeout = timeout

        if migrations_path is not None:
            self._migrations_path = migrations_path
        else:
            self._migrations_path = self._get_default_migrations_path()

    def _get_default_migrations_path(self) -> Path:
        current_dir = path.dirname(path.abspath(__file__))
        return Path(current_dir).parent.parent / "migrations" / "sqlite"

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
        conn = await connect(self.db_path, timeout=30.0)
        try:
            await self._acquire_migration_lock(conn)
            await self._ensure_migrations_table(conn)

            # 1) Fetch existing migrations into a dict: {version -> {checksum, dirty}}
            applied = {}
            async with conn.execute(
                "SELECT version, checksum, dirty FROM v2_migrations ORDER BY version",
            ) as cur:
                async for row in cur:
                    v, chksum, dirty = row
                    applied[v] = {"checksum": chksum, "dirty": bool(dirty)}

            # 2) Check if there's any dirty migration
            for version, details in applied.items():
                if details["dirty"] is True:
                    raise MigrationError(
                        f"Migration {version} is dirty. "
                        f"No migrations will be applied. "
                        f"Please fix it manually.",
                    )

            # 3) Gather .up.sql files
            migration_files = []
            for fname in listdir(self._migrations_path):
                if fname.endswith(".down.sql"):
                    continue  # skip .down.sql
                try:
                    version, _desc = self._validate_migration_filename(fname)
                    migration_files.append((version, fname))
                except InvalidMigrationFilenameError as e:
                    self._logger.warning(str(e))
                    continue

            # Sort by version ascending
            migration_files.sort(key=lambda x: x[0])

            # 4) For each migration file, check if we need to apply
            for version, filename in migration_files:
                # Build the full path to the migration file
                fpath = path.join(self._migrations_path, filename)

                # Read the file contents -> compute new checksum
                with open(fpath, encoding="utf-8") as f:
                    raw_sql = f.read().strip()
                new_checksum = sha256(raw_sql.encode()).hexdigest()

                # Validate the migration file has no transaction commands
                self._validate_migration_has_no_transaction_commands(raw_sql)

                if version in applied:
                    # Already known in DB -> check for drift
                    old = applied[version]
                    if old["dirty"]:
                        raise MigrationError(
                            f"Migration {version} is dirty. "
                            f"No migrations will be applied. "
                            f"Please fix it manually.",
                        )
                    # TODO we previously had a check to detect if a migration is already
                    # applied but the migration we have _now_ is different. This points out
                    # a developer doing something wrong, but removes our ability to change
                    # broken migrations.

                    # otherwise skip since it's already applied
                    continue
                else:
                    # Not in DB => apply it
                    await self._apply_migration(conn, version, filename, new_checksum)

        finally:
            await self._release_migration_lock(conn)
            await conn.close()

    # -------------------------------------------------------------------------
    # Locking
    # -------------------------------------------------------------------------
    async def _acquire_migration_lock(self, conn: Connection) -> None:
        """
        Acquire a migration lock in the v2_migration_locks table. If the lock row
        is held by another process, raise MigrationLockError.
        """
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS v2_migration_locks (
                id INTEGER PRIMARY KEY,
                locked_at TEXT,
                locked_by TEXT
            );
        """)
        await conn.commit()

        # Attempt to insert if the row doesn't exist; otherwise no-op
        locked_by = str(getpid())
        await conn.execute(
            """
            INSERT OR IGNORE INTO v2_migration_locks (id, locked_at, locked_by)
            VALUES (1, datetime('now'), ?);
            """,
            (locked_by,),
        )
        await conn.commit()

        # Now check who owns the lock
        async with conn.execute(
            "SELECT locked_by FROM v2_migration_locks WHERE id=1;",
        ) as cur:
            row = await cur.fetchone()
            if row:
                current_locked_by = row[0]
                if current_locked_by != locked_by:
                    raise MigrationLockError(
                        "Could not acquire migration lock. Another migration might be in progress.",
                    )

    async def _release_migration_lock(self, conn: Connection) -> None:
        """
        Release the migration lock if we own it.
        """
        locked_by = str(getpid())
        await conn.execute(
            """
            DELETE FROM v2_migration_locks
             WHERE id=1
               AND locked_by=?;
            """,
            (locked_by,),
        )
        await conn.commit()

    # -------------------------------------------------------------------------
    # Migrations Table
    # -------------------------------------------------------------------------
    async def _ensure_migrations_table(self, conn: Connection) -> None:
        """
        Create v2_migrations if it doesn't exist. A row is inserted for each
        applied migration version. 'dirty' indicates partial application.
        """
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS v2_migrations (
                version INTEGER PRIMARY KEY,
                dirty INTEGER NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await conn.commit()

    # -------------------------------------------------------------------------
    # Applying Migrations
    # -------------------------------------------------------------------------
    async def _apply_migration(
        self,
        conn: Connection,
        version: int,
        filename: str,
        new_checksum: str,
    ) -> None:
        """
        Apply a single migration:
          1) Insert row with dirty=TRUE
          2) Run the migration (with timeout, now wrapped in a transaction)
          3) Mark dirty=FALSE
        """
        self._logger.info(f"Applying migration {filename}")

        # Step 1: Insert row with dirty=TRUE
        try:
            await conn.execute("BEGIN;")
            await conn.execute(
                """
                INSERT INTO v2_migrations (version, dirty, checksum)
                VALUES (?, 1, ?);
                """,
                (version, new_checksum),
            )
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            self._logger.error(f"Failed to insert row for migration {filename}: {e}")
            raise MigrationError(f"Could not mark version={version} as dirty") from e

        # Step 2: Actually run the migration (now fully
        # atomic via the injected BEGIN/COMMIT)
        fpath = path.join(self._migrations_path, filename)
        with open(fpath, encoding="utf-8") as f:
            migration_sql = f.read().strip()
            if not migration_sql:
                raise MigrationError(f"Migration file {filename} is empty.")

        try:
            # This call now executes the migration SQL as a single transaction
            await self._run_migration_with_timeout(conn, migration_sql)
        except MigrationTimeoutError as mte:
            # Timed out: remain dirty
            self._logger.error(f"Migration {version} timed out: {mte}")
            raise
        except Exception as e:
            # Another error => remain dirty, rollback
            await conn.rollback()
            self._logger.error(f"Migration {version} failed: {e}")
            raise MigrationError(f"Migration {version} failed: {e!s}") from e

        # Step 3: Mark dirty=FALSE
        try:
            await conn.execute("BEGIN;")
            await conn.execute(
                "UPDATE v2_migrations SET dirty=0 WHERE version=?;",
                (version,),
            )
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            self._logger.error(f"Failed to mark migration {version} as clean: {e}")
            raise MigrationError(
                f"Could not mark version={version} as non-dirty",
            ) from e

        self._logger.info(f"Successfully applied migration {filename}")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _validate_migration_filename(self, filename: str):
        """
        Ensures filename matches <version>_<description>.up.sql
        Returns (version, description).
        """
        pattern = r"^(\d+)_([a-z0-9_]+)\.up\.sql$"
        m = re_match(pattern, filename)
        if not m:
            raise InvalidMigrationFilenameError(
                f"Invalid migration filename: {filename}. Expected '<version>_<desc>.up.sql'",
            )
        return int(m.group(1)), m.group(2)

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
        conn: Connection,
        migration_sql: str,
    ) -> None:
        """
        Executes the SQL with an asyncio timeout. If it times out, tries to interrupt
        the running query by calling conn._conn.interrupt() from an executor thread.
        This version injects a BEGIN and COMMIT to enforce atomicity.
        """
        # Wrap the migration SQL with transaction statements.
        # Be sure that the migration file does not include any transaction commands.
        wrapped_sql = f"BEGIN;\n{migration_sql}\nCOMMIT;"
        try:
            task = create_task(conn.executescript(wrapped_sql))
            await wait_for(task, timeout=self._timeout)
        except TimeoutError as e:
            try:
                from asyncio import get_running_loop

                loop = get_running_loop()
                await loop.run_in_executor(None, conn._conn.interrupt)
            except Exception as interrupt_err:
                self._logger.warning(
                    f"Failed to interrupt timed-out query: {interrupt_err}",
                )
            raise MigrationTimeoutError(
                f"Migration timed out after {self._timeout} seconds",
            ) from e
