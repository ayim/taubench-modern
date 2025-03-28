
from pathlib import Path

import aiosqlite
import pytest

from sema4ai_agent_server.storage.v2.migrations_v2 import (
    MigrationError,
    MigrationLockError,
    MigrationTimeoutError,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.migrations import SQLiteMigrationsV2


@pytest.fixture
async def sqlite_db_path(tmp_path_factory):
    """Provide a temporary SQLite file path for testing."""
    db_file = tmp_path_factory.mktemp("data") / "test.db"
    return str(db_file)


@pytest.mark.asyncio
async def test_sqlite_run_migrations_successfully(sqlite_db_path):
    """Test that migrations run successfully and create expected tables in SQLite."""
    path_to_migrations = (
        Path(__file__).parent.parent.parent.parent / "sema4ai_agent_server"
        / "migrations" / "v2" / "sqlite"
    )
    migrations = SQLiteMigrationsV2(sqlite_db_path, migrations_path=path_to_migrations)
    await migrations.run_migrations()

    # Check that a table is created, for example 'v2_agent'.
    async with aiosqlite.connect(sqlite_db_path) as conn:
        cursor = await conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='v2_agent';
        """)
        row = await cursor.fetchone()
        assert row is not None, "Expected 'v2_agent' table to exist after migrations"

    # You might also check the migrations table to ensure the highest version is correct
    async with aiosqlite.connect(sqlite_db_path) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT version FROM v2_migrations ORDER BY version DESC LIMIT 1;",
            )
            row = await cur.fetchone()
            latest_version = row[0] if row else None

            # Let's count the number of migrations we have in the migrations folder
            migration_files = [
                f for f in path_to_migrations.iterdir()
                if f.is_file() and f.name.endswith(".up.sql")
            ]
            num_migrations = len(migration_files)
            assert (
                latest_version == num_migrations
            ), (
                f"Expected the latest migration version to be {num_migrations}, "
                f"got {latest_version}"
            )


@pytest.mark.asyncio
async def test_sqlite_run_migrations_dirty_state(sqlite_db_path):
    """Test that a dirty migration state raises MigrationError in SQLite."""
    # Create the migrations table with a 'dirty=1' row
    async with aiosqlite.connect(sqlite_db_path) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS v2_migrations (
                version INTEGER PRIMARY KEY,
                dirty INTEGER NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await conn.execute("""
            INSERT INTO v2_migrations (version, dirty, checksum)
            VALUES (1, 1, 'dummy-checksum');
        """)
        await conn.commit()

    migrations = SQLiteMigrationsV2(sqlite_db_path)

    with pytest.raises(MigrationError) as exc_info:
        await migrations.run_migrations()

    assert "is dirty. No migrations will be applied." in str(exc_info.value)


@pytest.mark.asyncio
async def test_sqlite_migration_timeout(sqlite_db_path, tmp_path):
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

        # Create a SQLiteMigrationsV2 instance with a shorter timeout
        migrations = SQLiteMigrationsV2(
            sqlite_db_path, timeout=1.0, migrations_path=temp_migration_path.parent,
        )

        # Run migrations and expect timeout
        with pytest.raises(MigrationTimeoutError):
            await migrations.run_migrations()

    finally:
        # Clean up the temporary file
        if temp_migration_path.exists():
            temp_migration_path.unlink()


@pytest.mark.asyncio
async def test_sqlite_invalid_migration_filename(sqlite_db_path, tmp_path):
    """
    Test that migrations with invalid filenames are ignored and a warning is logged.
    """
    # Create a temporary invalid migration file
    temp_migration_path = tmp_path / "invalid_migration.up.sql"
    try:
        # Create an invalid migration file
        with open(temp_migration_path, "w") as f:
            f.write("CREATE TABLE test (id INTEGER PRIMARY KEY);")

        # Initialize migrations instance pointing to the temporary directory
        migrations = SQLiteMigrationsV2(
            sqlite_db_path, migrations_path=temp_migration_path.parent,
        )

        # Run migrations
        await migrations.run_migrations()

        # Check that the invalid file was ignored
        async with aiosqlite.connect(sqlite_db_path) as conn:
            async with conn.execute(
                "SELECT version FROM v2_migrations ORDER BY version DESC LIMIT 1;",
            ) as cur:
                row = await cur.fetchone()
                latest_version = row[0] if row else 0

                # Since the invalid file was ignored,
                # no new migrations should have been applied
                assert latest_version == 0

    finally:
        # Clean up the temporary file
        if temp_migration_path.exists():
            temp_migration_path.unlink()

@pytest.mark.asyncio
async def test_sqlite_migration_lock_cannot_be_acquired(sqlite_db_path):
    """
    Test that a MigrationLockError is raised if we cannot acquire the lock.
    We simulate another process holding the lock by inserting a row with
    a locked_at that has not expired.
    """
    # Manually create the locks table and insert a lock row
    async with aiosqlite.connect(sqlite_db_path) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS v2_migration_locks (
                id INTEGER PRIMARY KEY,
                locked_at TIMESTAMP,
                locked_by TEXT
            );
        """)
        await conn.execute("""
            INSERT INTO v2_migration_locks (id, locked_at, locked_by)
            VALUES (1, datetime('now'), 'some-other-pid');
        """)
        await conn.commit()

    # Attempt to run migrations, expect the lock acquisition to fail
    migrations = SQLiteMigrationsV2(sqlite_db_path)

    with pytest.raises(MigrationLockError) as exc_info:
        await migrations.run_migrations()

    assert "Could not acquire migration lock" in str(exc_info.value)

@pytest.mark.asyncio
async def test_sqlite_migration_checksum_drift(sqlite_db_path, tmp_path):
    """
    Test that if a migration file changes after it's already applied,
    we detect checksum drift and raise MigrationError.
    """
    # 1) Create a valid migration file in a temporary directory
    migration_file = tmp_path / "1_create_test_table.up.sql"
    migration_file.write_text("CREATE TABLE drift_test (id INTEGER PRIMARY KEY);")

    # 2) Point migrations to that temp directory and run them once
    migrations = SQLiteMigrationsV2(sqlite_db_path, migrations_path=tmp_path)
    await migrations.run_migrations()

    # 3) Modify the SAME file content (simulate drift)
    migration_file.write_text(
        "CREATE TABLE drift_test (id INTEGER PRIMARY KEY, name TEXT);",
    )

    # 4) Run migrations again and expect a checksum drift error
    with pytest.raises(MigrationError) as exc_info:
        await migrations.run_migrations()

    assert "Checksum drift detected for migration 1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_sqlite_migration_sql_syntax_error(sqlite_db_path, tmp_path):
    """
    Test that an invalid SQL statement in a migration file causes MigrationError,
    and the migration remains dirty.
    """
    # Create a migration file with a syntax error
    bad_migration = tmp_path / "2_bad_syntax.up.sql"
    # 'CREAT' missing 'E'
    bad_migration.write_text("CREAT TABLE bad_syntax (id INTEGER PRIMARY KEY);")

    migrations = SQLiteMigrationsV2(sqlite_db_path, migrations_path=tmp_path)

    with pytest.raises(MigrationError) as exc_info:
        await migrations.run_migrations()

    # The error should mention "Migration 2 failed:"
    assert "Migration 2 failed:" in str(exc_info.value)

    # Verify that the migration is still marked 'dirty'
    async with aiosqlite.connect(sqlite_db_path) as conn:
        async with conn.execute(
            "SELECT dirty FROM v2_migrations WHERE version=2;",
        ) as cur:
            row = await cur.fetchone()
            # The row should exist and be dirty (1)
            assert row is not None, "Expected a row for version=2 in v2_migrations"
            assert row[0] == 1, "Expected migration 2 to remain dirty after SQL error."


@pytest.mark.asyncio
async def test_sqlite_empty_migration_file(sqlite_db_path, tmp_path):
    """
    Test that an empty migration file raises a MigrationError.
    """
    # Create an empty migration file
    empty_migration = tmp_path / "3_empty_file.up.sql"
    empty_migration.write_text("")  # no contents

    migrations = SQLiteMigrationsV2(sqlite_db_path, migrations_path=tmp_path)

    with pytest.raises(MigrationError) as exc_info:
        await migrations.run_migrations()

    assert f"Migration file {empty_migration.name} is empty." in str(exc_info.value)


@pytest.mark.asyncio
async def test_sqlite_migrations_idempotency(sqlite_db_path, tmp_path):
    """
    Run migrations twice and verify that the number of
    applied migrations remains the same.
    """
    # Use your normal migrations directory.
    migrations_path = (
        Path(__file__).parent.parent.parent.parent /
        "sema4ai_agent_server" / "migrations" / "v2" / "sqlite"
    )
    migrations = SQLiteMigrationsV2(sqlite_db_path, migrations_path=migrations_path)

    await migrations.run_migrations()
    async with aiosqlite.connect(sqlite_db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM v2_migrations") as cur:
            row = await cur.fetchone()
            initial_count = row[0]

    await migrations.run_migrations()
    async with aiosqlite.connect(sqlite_db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM v2_migrations") as cur:
            row = await cur.fetchone()
            second_count = row[0]

    assert initial_count == second_count, "SQLite migrations are not idempotent."


@pytest.mark.asyncio
async def test_sqlite_empty_migrations_directory(sqlite_db_path, tmp_path):
    """
    Point the migrations engine to an empty directory and verify that no migrations
    are applied.
    """
    empty_dir = tmp_path / "empty_migrations"
    empty_dir.mkdir()
    migrations = SQLiteMigrationsV2(sqlite_db_path, migrations_path=empty_dir)

    await migrations.run_migrations()

    async with aiosqlite.connect(sqlite_db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM v2_migrations") as cur:
            row = await cur.fetchone()
            count = row[0]

    assert count == 0, "Expected no migrations when the migrations directory is empty."


@pytest.mark.asyncio
async def test_sqlite_rollback_on_failure(sqlite_db_path, tmp_path):
    """
    Create a migration file with a valid SQL statement followed by an invalid one.
    Verify that when the migration fails, no partial schema changes are applied.
    """
    migration_dir = tmp_path / "faulty_migrations"
    migration_dir.mkdir()
    migration_file = migration_dir / "1_faulty.up.sql"
    migration_file.write_text("""
        CREATE TABLE rollback_test (id INTEGER PRIMARY KEY);
        INVALID SQL STATEMENT;
    """)
    migrations = SQLiteMigrationsV2(sqlite_db_path, migrations_path=migration_dir)

    with pytest.raises(MigrationError):
        await migrations.run_migrations()

    async with aiosqlite.connect(sqlite_db_path) as conn:
        async with conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rollback_test';
        """) as cur:
            row = await cur.fetchone()

    assert row is None, (
        "Table 'rollback_test' should not exist after a migration failure."
    )


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
    sqlite_db_path, tmp_path, bad_sql, err_msg,
):
    """
    Write a migration file that contains transaction commands and ensure
    that the migration run raises a MigrationError with an appropriate message.
    """
    # Create a temporary migrations directory
    migration_dir = tmp_path / "bad_migrations"
    migration_dir.mkdir(exist_ok=True)

    # Write the bad migration file; the filename has the
    # correct version/description pattern.
    migration_file = migration_dir / "1_bad.up.sql"
    migration_file.write_text(bad_sql)

    # Initialize the migrations provider with the temporary migration directory.
    # Note that sqlite_db_path is a fixture that should point to an
    # empty SQLite DB file.
    migrations = SQLiteMigrationsV2(
        str(sqlite_db_path), migrations_path=migration_dir,
    )

    # Running the migrations should trigger a MigrationError due to
    # forbidden transaction commands.
    with pytest.raises(MigrationError) as excinfo:
        await migrations.run_migrations()

    # Check that the error message contains the correct hint
    assert err_msg in str(excinfo.value)
