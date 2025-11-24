import typing
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import cast

import pytest

if typing.TYPE_CHECKING:
    from psycopg import AsyncConnection
    from psycopg.rows import TupleRow
    from psycopg_pool import AsyncConnectionPool

    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage
    from server.tests.storage.sample_model_creator import SampleModelCreator


@pytest.fixture
async def sqlite_storage(tmp_path: Path) -> "AsyncGenerator[SQLiteStorage, None]":
    """
    Initialize SQLiteStorage with an ephemeral database.
    We'll also seed a system user, just like in Postgres tests.
    """
    from agent_platform.server.file_manager.option import FileManagerService
    from agent_platform.server.storage.option import StorageService

    storage_instance = await _create_sqlite_storage(tmp_path)

    StorageService.set_for_testing(storage_instance)
    FileManagerService.reset()

    yield storage_instance
    await _teardown_sqlite_storage(tmp_path, storage_instance)

    StorageService.reset()
    FileManagerService.reset()


async def _create_sqlite_storage(tmp_path: Path) -> "SQLiteStorage":
    """Helper function to create and setup SQLite storage."""
    from agent_platform.server.storage.sqlite import SQLiteStorage

    test_file_path = tmp_path / "test_sqlite_storage.db"
    if test_file_path.exists():
        test_file_path.unlink()
    storage_instance = SQLiteStorage(db_path=str(test_file_path))
    await storage_instance.setup()
    await storage_instance.get_or_create_user(
        sub="tenant:testing:system:system_user",
    )
    return storage_instance


async def _teardown_sqlite_storage(tmp_path: Path, storage_instance: "SQLiteStorage") -> None:
    await storage_instance.teardown()
    test_file_path = tmp_path / "test_sqlite_storage.db"
    if test_file_path.exists():
        test_file_path.unlink()


@pytest.fixture(scope="session")
async def postgres_testing(request):
    # Lazy import testing.postgresql only when needed
    already_yielded = False
    try:
        import testing.postgresql

        with testing.postgresql.Postgresql() as postgresql:
            try:
                yield postgresql
                already_yielded = True
            finally:
                postgresql.stop()
    except Exception:
        # If pytest is being run with -m "not postgresql", we ignore this error and return None.
        if not already_yielded:
            if "not postgresql" not in request.config.getoption("-m"):
                raise
            else:
                yield None
        else:
            raise


@pytest.fixture(scope="session")
async def postgres_test_db(
    postgres_testing,
) -> "AsyncGenerator[AsyncConnectionPool[AsyncConnection[TupleRow]], None] | AsyncGenerator[None, None]":  # noqa: E501
    """Creates a shared temporary Postgres instance for the entire test session."""
    from psycopg import AsyncConnection
    from psycopg.rows import TupleRow
    from psycopg_pool import AsyncConnectionPool

    if postgres_testing is None:  # This means we are running with -m "not postgresql"
        yield None
        return

    dsn = postgres_testing.url()
    pool = None
    try:
        # Increase min_size to maintain connections and reduce
        # max_size to prevent too many connections
        pool = AsyncConnectionPool(
            conninfo=dsn,
            min_size=2,  # Keep minimum connections alive
            max_size=50,
            num_workers=2,
            open=False,
            # Add timeout parameters
            timeout=5,
            reconnect_timeout=5,
            # Configure connection recycling
            max_lifetime=3600,  # Recycle connections after 1 hour
            max_idle=300,  # Close idle connections after 5 minutes
        )
        await pool.open()
        yield cast(AsyncConnectionPool[AsyncConnection[TupleRow]], pool)
    finally:
        if pool:
            await pool.close()


async def _create_postgres_storage(
    postgres_test_db: "AsyncConnectionPool[AsyncConnection[TupleRow]]", postgres_testing
) -> "PostgresStorage":
    """Helper function to create and setup PostgreSQL storage."""
    from agent_platform.server.storage.postgres import PostgresStorage

    # Pre-truncate: Drop the schema 'v2' if it exists, then recreate it
    async with postgres_test_db.connection() as conn:  # pyright: ignore [reportAttributeAccessIssue]
        async with conn.cursor() as cur:
            await cur.execute("DROP SCHEMA IF EXISTS v2 CASCADE;")
            await cur.execute("CREATE SCHEMA v2;")

    storage_instance = PostgresStorage(pool=postgres_test_db, dsn=postgres_testing.url())  # pyright: ignore [reportArgumentType]
    await storage_instance.setup()
    await storage_instance.get_or_create_user(
        sub="tenant:testing:system:system_user",
    )
    return storage_instance


@pytest.fixture
async def postgres_storage(
    postgres_test_db: "AsyncConnectionPool[AsyncConnection[TupleRow]]", postgres_testing
) -> "AsyncGenerator[PostgresStorage, None]":
    """
    Initialize storage with the shared test database.

    Before running migrations, we clean the slate by dropping
    the 'v2' schema (if it exists) and recreating it. This
    pre-truncates any existing state from previous tests.
    """
    from agent_platform.server.file_manager.option import FileManagerService
    from agent_platform.server.storage.option import StorageService

    try:
        storage_instance = await _create_postgres_storage(postgres_test_db, postgres_testing)
        StorageService.set_for_testing(storage_instance)
        FileManagerService.reset()

        yield storage_instance

        StorageService.reset()
        FileManagerService.reset()

        # No teardown: trying to keep pool open for the duration of the test session.
        # await storage_instance.teardown()
    except Exception as e:
        # Log any connection issues
        import logging

        logging.error(f"Error in storage fixture: {e}")
        raise


@pytest.fixture(
    params=[
        pytest.param("sqlite", marks=[]),
        pytest.param("postgres", marks=[pytest.mark.postgresql]),
    ]
)
async def storage(
    request,
    tmp_path: Path,
    postgres_test_db: "AsyncConnectionPool[AsyncConnection[TupleRow]]",
    postgres_testing,
) -> AsyncGenerator["SQLiteStorage | PostgresStorage", None]:
    """
    Parametrized fixture that provides both SQLite and Postgres storage implementations.
    PostgreSQL tests will be skipped when running with -m "not postgresql",
    but SQLite tests will still run.
    """
    from agent_platform.server.file_manager.option import FileManagerService
    from agent_platform.server.storage.option import StorageService

    if request.param == "postgres":
        if postgres_testing is None:
            raise Exception(
                """postgres_testing is None, this should only happen when running
                with -m 'not postgresql', but somehow it seems that postgres is being
                used anyway"""
            )
        storage_instance = await _create_postgres_storage(postgres_test_db, postgres_testing)

        StorageService.set_for_testing(storage_instance)
        FileManagerService.reset()

        yield storage_instance
    else:  # sqlite
        storage_instance = await _create_sqlite_storage(tmp_path)

        StorageService.set_for_testing(storage_instance)
        FileManagerService.reset()

        yield storage_instance
        await _teardown_sqlite_storage(tmp_path, storage_instance)

    StorageService.reset()
    FileManagerService.reset()


@pytest.fixture
async def sqlite_model_creator(
    sqlite_storage: "SQLiteStorage", tmp_path: Path
) -> "SampleModelCreator":
    from server.tests.storage.sample_model_creator import SampleModelCreator

    smc = SampleModelCreator(sqlite_storage, tmp_path)
    await smc.setup()
    return smc


@pytest.fixture
async def postgres_model_creator(
    postgres_storage: "PostgresStorage", tmp_path: Path
) -> "SampleModelCreator":
    from server.tests.storage.sample_model_creator import SampleModelCreator

    smc = SampleModelCreator(postgres_storage, tmp_path)
    await smc.setup()
    return smc
