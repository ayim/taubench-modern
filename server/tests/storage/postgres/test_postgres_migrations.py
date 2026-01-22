from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from psycopg import AsyncCursor
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from agent_platform.server.storage.migrations import (
    MigrationError,
    MigrationTimeoutError,
)
from agent_platform.server.storage.postgres.migrations import PostgresMigrations

CursorProvider = Callable[[], AbstractAsyncContextManager[AsyncCursor[DictRow]]]

pytestmark = pytest.mark.postgresql

if TYPE_CHECKING:
    from agent_platform.server.storage.postgres.postgres import PostgresStorage


@pytest.fixture(autouse=True)
async def _reset_schema(postgres_test_db: AsyncConnectionPool):
    """
    Resets the v2 schema before each test:
    - Drops the schema if it exists (removing all tables,
      including migration locks/cache)
    - Recreates a clean v2 schema.
    This ensures that each migration test starts from a known baseline.
    """
    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            # Drop the schema if it exists and all its objects.
            await cur.execute("DROP SCHEMA IF EXISTS v2 CASCADE;")
            # Recreate the schema.
            await cur.execute("CREATE SCHEMA v2;")


@pytest.fixture
async def postgres_storage_for_migrations(postgres_testing):
    """Create a SQLiteStorage instance for migration testing.

    This sets up the storage without running migrations, so we can test
    the migration system in isolation.
    """
    from agent_platform.server.storage.postgres.postgres import PostgresStorage

    storage = PostgresStorage(dsn=postgres_testing.url())
    await storage.setup(migrate=False)

    yield storage

    await storage.teardown()


@pytest.mark.flaky(max_runs=5, min_passes=1)
@pytest.mark.asyncio
async def test_postgres_run_migrations_successfully(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool
):
    """
    Test that running migrations completes without error
    and that the final schema is as expected.
    """
    path_to_migrations = (
        Path(__file__).parent.parent.parent.parent / "src" / "agent_platform" / "server" / "migrations" / "postgres"
    )
    migrations = PostgresMigrations(
        postgres_storage_for_migrations,
        migrations_path=path_to_migrations,
    )

    # Run the migrations
    await migrations.run_migrations()

    # After running migrations, check that certain tables exist:
    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            # Example: Check that a "v2.agent" table now exists
            await cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE  table_schema = 'v2'
                    AND    table_name   = 'agent'
                );
            """)
            row = await cur.fetchone()
            assert row is not None
            table_exists = row[0]
            assert table_exists, "Expected 'v2.agent' table to exist after migrations"

    # You might also check the migrations table to ensure the highest version is correct
    async with postgres_test_db.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT version FROM v2.migrations ORDER BY version DESC LIMIT 1;",
            )
            row = await cur.fetchone()
            latest_version = row["version"] if row else None

            # Let's count the number of migrations we have in the migrations folder
            migration_files = [f for f in path_to_migrations.iterdir() if f.is_file() and f.name.endswith(".up.sql")]
            num_migrations = len(migration_files)
            assert latest_version == num_migrations, (
                f"Expected the latest migration version to be {num_migrations}, got {latest_version}"
            )


@pytest.mark.asyncio
async def test_postgres_run_migrations_dirty_state(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool
):
    """
    Test that running migrations fails if the 'dirty' flag is set.
    We artificially set a dirty row in the migrations table,
    then confirm a MigrationError is raised.
    """
    migrations = PostgresMigrations(postgres_storage_for_migrations)

    # Manually set the "dirty" flag
    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("CREATE SCHEMA IF NOT EXISTS v2;")
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS v2.migrations (
                    version BIGINT PRIMARY KEY,
                    dirty BOOLEAN NOT NULL,
                    checksum VARCHAR(64) NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await cur.execute("""
                INSERT INTO v2.migrations (version, dirty, checksum)
                VALUES (1, TRUE, 'dummy-checksum')
                ON CONFLICT (version) DO UPDATE SET dirty = EXCLUDED.dirty;
            """)

    # Now check that applying migrations raises a MigrationError
    with pytest.raises(MigrationError) as exc_info:
        await migrations.run_migrations()

    assert "is dirty. No migrations will be applied." in str(exc_info.value)


@pytest.mark.asyncio
async def test_postgres_migration_timeout(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool, tmp_path: Path
):
    """
    Test that a MigrationTimeoutError is raised when a migration exceeds the timeout.
    """
    # Create a temporary migration file that takes longer than the timeout
    temp_migration_path = tmp_path / "1_long_running.up.sql"
    try:
        # Create a migration file with a long-running query
        with open(temp_migration_path, "w") as f:
            f.write("""
                WITH RECURSIVE t(x) AS (
                    SELECT 1
                    UNION ALL
                    SELECT x+1 FROM t WHERE x<500000000
                )
                SELECT x FROM t;
            """)

        # Create a PostgresMigrations instance with a shorter timeout
        migrations = PostgresMigrations(
            postgres_storage_for_migrations,
            timeout=1.0,
            migrations_path=Path(str(temp_migration_path.parent)),
        )

        # Run migrations and expect timeout
        with pytest.raises(MigrationTimeoutError):
            await migrations.run_migrations()

    finally:
        # Clean up the temporary file
        if temp_migration_path.exists():
            temp_migration_path.unlink()


@pytest.mark.asyncio
async def test_postgres_invalid_migration_filename(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool, tmp_path: Path
):
    """
    Test that migrations with invalid filenames are ignored and a warning is logged.
    """
    # Create a temporary invalid migration file
    temp_migration_path = tmp_path / "invalid_migration.up.sql"
    try:
        # Create an invalid migration file
        with open(temp_migration_path, "w") as f:
            f.write("CREATE TABLE test (id SERIAL PRIMARY KEY);")

        # Initialize migrations instance pointing to the temporary directory
        migrations = PostgresMigrations(
            postgres_storage_for_migrations, migrations_path=Path(str(temp_migration_path.parent))
        )

        # Run migrations
        await migrations.run_migrations()

        # Check that the invalid file was ignored
        async with postgres_test_db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT version FROM v2.migrations ORDER BY version DESC LIMIT 1;",
                )
                row = await cur.fetchone()
                latest_version = row[0] if row else 0

                # Since the invalid file was ignored, no new
                # migrations should have been applied
                assert latest_version == 0

    finally:
        # Clean up the temporary file
        if temp_migration_path.exists():
            temp_migration_path.unlink()


# TODO: do we want this migration locking on?
# @pytest.mark.asyncio
# async def test_postgres_migration_lock_cannot_be_acquired(
#     postgres_test_db: AsyncConnectionPool,
#     cursor_provider: CursorProvider,
# ):
#     """
#     Test that a MigrationLockError is raised if we cannot acquire the lock.
#     We simulate another process holding the lock by inserting a row with
#     a locked_at that has not expired.
#     """
#     # Manually insert a lock row so that the current process can't overwrite it
#     async with postgres_test_db.connection() as conn:
#         async with conn.cursor() as cur:
#             await cur.execute("CREATE SCHEMA IF NOT EXISTS v2;")
#             await cur.execute(
#                 """
#                 CREATE TABLE IF NOT EXISTS v2.migration_locks (
#                     id INTEGER PRIMARY KEY,
#                     locked_at TIMESTAMP WITH TIME ZONE,
#                     locked_by TEXT
#                 );
#                 """,
#             )
#             # Insert a row with locked_at = NOW
#             await cur.execute(
#                 """
#                 INSERT INTO v2.migration_locks (id, locked_at, locked_by)
#                 VALUES (1, CURRENT_TIMESTAMP, 'some-other-pid');
#                 """,
#             )

#     # Attempt to run migrations, expect the lock acquisition to fail
#     migrations = PostgresMigrations(postgres_storage_for_migrations)

#     with pytest.raises(MigrationLockError) as exc_info:
#         await migrations.run_migrations()

#     assert "Could not acquire migration lock" in str(exc_info.value)


@pytest.mark.asyncio
async def test_postgres_migration_checksum_drift(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool, tmp_path: Path
):
    """
    Test that if a migration file changes after it's already applied,
    we detect checksum drift and raise MigrationError.
    """
    # 1) Create a valid migration file in a temporary directory
    migration_file = tmp_path / "1_create_test_table.up.sql"
    migration_file.write_text("CREATE TABLE drift_test (id SERIAL PRIMARY KEY);")

    # 2) Point our migrations to that temp directory and run them once
    migrations = PostgresMigrations(postgres_storage_for_migrations, migrations_path=tmp_path)
    await migrations.run_migrations()

    # <--- Force unlock here so that the next run can reacquire the lock. --->
    async with postgres_storage_for_migrations._cursor() as cur:
        # Just wipe out the lock row entirely (or only if locked_by = <pid1>)
        await cur.execute("DELETE FROM v2.migration_locks WHERE id = 1;")

    # 3) Modify the SAME file content (simulate drift)
    migration_file.write_text(
        "CREATE TABLE drift_test (id SERIAL PRIMARY KEY, name TEXT);",
    )

    # 4) Run migrations again and expect a checksum drift error
    with pytest.raises(MigrationError) as exc_info:
        await migrations.run_migrations()

    assert "Checksum drift detected for migration 1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_postgres_empty_migration_file(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool, tmp_path: Path
):
    """
    Test that an empty migration file raises a MigrationError.
    """
    # Create an empty migration file
    empty_migration = tmp_path / "2_empty_file.up.sql"
    empty_migration.write_text("")  # No contents

    # Run migrations
    migrations = PostgresMigrations(postgres_storage_for_migrations, migrations_path=tmp_path)

    with pytest.raises(MigrationError) as exc_info:
        await migrations.run_migrations()

    assert f"Migration file {empty_migration.name} is empty." in str(exc_info.value)


@pytest.mark.asyncio
async def test_postgres_migration_sql_syntax_error(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool, tmp_path: Path
):
    """
    Test that an invalid SQL statement in a migration file causes MigrationError,
    and does not corrupt the migrations table.
    """
    # Create a migration file with a syntax error
    bad_migration = tmp_path / "3_bad_syntax.up.sql"
    # Missing 'E'
    bad_migration.write_text("CREAT TABLE bad_syntax (id SERIAL PRIMARY KEY);")

    migrations = PostgresMigrations(postgres_storage_for_migrations, migrations_path=tmp_path)

    with pytest.raises(MigrationError) as exc_info:
        await migrations.run_migrations()

    assert "Migration 3 failed:" in str(
        exc_info.value,
    ), "Expected a MigrationError due to syntax error."

    # Verify that the migration is still marked 'dirty' (or not in DB at all)
    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT dirty FROM v2.migrations WHERE version = 3;")
            row = await cur.fetchone()
            # Either row won't exist or it will be dirty.
            # Implementation detail: we first insert dirty=TRUE, then run the
            # migration, then rollback.
            # So the record might remain with dirty=TRUE.
            if row:
                assert row[0] is True, "Expected migration 3 to remain dirty after SQL error."


@pytest.mark.asyncio
async def test_postgres_migrations_idempotency(
    postgres_storage_for_migrations: "PostgresStorage",
    postgres_test_db: AsyncConnectionPool,
    tmp_path: Path,
):
    """
    Run migrations twice and verify that the number of applied
    migrations remains the same.
    """
    # Use your normal migrations directory.
    migrations_path = (
        Path(__file__).parent.parent.parent.parent / "src" / "agent_platform" / "server" / "migrations" / "postgres"
    )
    migrations = PostgresMigrations(postgres_storage_for_migrations, migrations_path=migrations_path)

    await migrations.run_migrations()
    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM v2.migrations")
            row = await cur.fetchone()
            assert row is not None
            initial_count = row[0]

    # <--- Force unlock here so that the next run can reacquire the lock. --->
    async with postgres_storage_for_migrations._cursor() as cur:
        # Just wipe out the lock row entirely (or only if locked_by = <pid1>)
        await cur.execute("DELETE FROM v2.migration_locks WHERE id = 1;")

    await migrations.run_migrations()
    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM v2.migrations")
            row = await cur.fetchone()
            assert row is not None
            second_count = row[0]

    assert initial_count == second_count, "Postgres migrations are not idempotent."


@pytest.mark.asyncio
async def test_postgres_empty_migrations_directory(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool, tmp_path: Path
):
    """
    Point the migrations engine to an empty directory and verify that no migrations
    are applied.
    """
    empty_dir = tmp_path / "empty_migrations"
    empty_dir.mkdir()
    migrations = PostgresMigrations(postgres_storage_for_migrations, migrations_path=empty_dir)

    await migrations.run_migrations()

    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM v2.migrations")
            row = await cur.fetchone()
            assert row is not None
            count = row[0]

    assert count == 0, "Expected no migrations when the migrations directory is empty."


@pytest.mark.asyncio
async def test_postgres_rollback_on_failure(
    postgres_storage_for_migrations: "PostgresStorage", postgres_test_db: AsyncConnectionPool, tmp_path: Path
):
    """
    Create a migration file with a valid SQL statement followed by an invalid one.
    Verify that when the migration fails, no partial schema changes are applied.
    """
    migration_dir = tmp_path / "faulty_migrations"
    migration_dir.mkdir()
    migration_file = migration_dir / "1_faulty.up.sql"

    # Make sure we have explicit transaction boundaries in the migration SQL
    migration_file.write_text("""
        CREATE TABLE v2.rollback_test (id INTEGER PRIMARY KEY);
        SELECT INVALID_FUNCTION();  -- This will cause an error
    """)

    migrations = PostgresMigrations(postgres_storage_for_migrations, migrations_path=migration_dir)

    with pytest.raises(MigrationError):
        await migrations.run_migrations()

    # Check if the table exists - the EXISTS query returns a boolean
    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'v2'
                    AND    table_name   = 'rollback_test'
                );
            """)
            row = await cur.fetchone()
            table_exists = row[0] if row else False

    assert not table_exists, "Table 'rollback_test' should not exist after a migration failure."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bad_sql", "err_msg"),
    [
        (
            "BEGIN;\nCREATE TABLE test (id INTEGER);",
            "Migration file contains 'BEGIN;'",
        ),
        (
            "   BEGIN;  \nCREATE TABLE test (id INTEGER);",
            "Migration file contains 'BEGIN;'",
        ),
        (
            "CREATE TABLE test (id INTEGER);\nCOMMIT;",
            "Migration file contains 'COMMIT;'",
        ),
        (
            "ROLLBACK;\nCREATE TABLE test (id INTEGER);",
            "Migration file contains 'ROLLBACK;'",
        ),
    ],
)
async def test_migration_script_with_transaction_commands(
    postgres_storage_for_migrations: "PostgresStorage",
    postgres_test_db: AsyncConnectionPool,
    tmp_path: Path,
    bad_sql: str,
    err_msg: str,
):
    """
    Write a migration file that contains transaction commands and ensure
    that the migration run raises a MigrationError with an appropriate message.
    """
    # Create a temporary migrations directory
    migration_dir = tmp_path / "bad_migrations"
    migration_dir.mkdir(exist_ok=True)

    # Write the bad migration file; the filename
    # has the correct version/description pattern.
    migration_file = migration_dir / "1_bad.up.sql"
    migration_file.write_text(bad_sql)

    # Initialize the migrations provider with the temporary migration directory.
    migrations = PostgresMigrations(postgres_storage_for_migrations, migrations_path=migration_dir)

    # Running the migrations should trigger a MigrationError
    # due to forbidden transaction commands.
    with pytest.raises(MigrationError) as excinfo:
        await migrations.run_migrations()

    # Check that the error message contains the correct hint
    assert err_msg in str(excinfo.value)
