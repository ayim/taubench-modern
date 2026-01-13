import asyncio
import shutil
import sys
import typing
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import cast

import pytest
from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from psycopg import AsyncConnection
    from psycopg.rows import TupleRow
    from psycopg_pool import AsyncConnectionPool

    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage
    from server.tests.storage.sample_model_creator import SampleModelCreator

# setup the event loop globally
if sys.platform == "win32":
    # Fix: psycopg.pool - WARNING: error connecting in 'pool-1': Psycopg cannot use the
    # 'ProactorEventLoop' to run in async mode. Please use a compatible event loop,
    # for instance by setting 'asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())'
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = get_logger(__name__)


@pytest.fixture(scope="session")
async def sqlite_template_db(tmp_path_factory) -> "AsyncGenerator[Path, None]":
    """
    Create a template SQLite database file once per session.
    This template includes all migrations and the system user.
    Individual tests will copy this template to avoid re-running migrations.
    """
    from agent_platform.server.storage.sqlite import SQLiteStorage

    # Use a session-scoped temporary directory
    template_dir = tmp_path_factory.mktemp("sqlite_template")
    template_file_path = template_dir / "template_sqlite_storage.db"

    # Create and setup the template database
    storage_instance = SQLiteStorage(db_path=str(template_file_path))
    await storage_instance.setup()
    await storage_instance.get_or_create_user(
        sub="tenant:testing:system:system_user",
    )
    await storage_instance.teardown()

    return template_file_path


@pytest.fixture
async def sqlite_storage(tmp_path: Path, sqlite_template_db: Path) -> "AsyncGenerator[SQLiteStorage, None]":
    """
    Initialize SQLiteStorage with an ephemeral database.
    We'll also seed a system user, just like in Postgres tests.
    """
    from agent_platform.server.file_manager.option import FileManagerService
    from agent_platform.server.storage.option import StorageService

    storage_instance = await _create_sqlite_storage(tmp_path, sqlite_template_db)

    StorageService.set_for_testing(storage_instance)
    FileManagerService.reset()

    yield storage_instance
    await _teardown_sqlite_storage(tmp_path, storage_instance)

    StorageService.reset()
    FileManagerService.reset()


async def _create_sqlite_storage(tmp_path: Path, template_db_path: Path | None = None) -> "SQLiteStorage":
    """Helper function to create and setup SQLite storage.

    If template_db_path is provided, copies the template database file
    instead of creating a new one from scratch.
    """
    from agent_platform.server.storage.sqlite import SQLiteStorage

    test_file_path = tmp_path / "test_sqlite_storage.db"
    if test_file_path.exists():
        test_file_path.unlink()

    # If template is provided, copy it instead of creating from scratch
    if template_db_path and template_db_path.exists():
        shutil.copy2(template_db_path, test_file_path)
        # Note: We don't copy WAL/SHM files as SQLite will create new ones as needed

    storage_instance = SQLiteStorage(db_path=str(test_file_path))
    await storage_instance.setup()

    # Only create user if we didn't use a template (template already has it)
    if template_db_path is None or not template_db_path.exists():
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
async def postgres_testing(request, tmp_path_factory):
    import tempfile

    # Lazy import testing.postgresql only when needed
    already_yielded = False
    try:
        import testing.common.database
        import testing.postgresql

        class CustomPostgresql(testing.postgresql.Postgresql):
            def terminate(self, *args):
                # We need to override to work on Windows.
                import signal

                if sys.platform == "win32":
                    send_signal = signal.CTRL_BREAK_EVENT
                else:
                    send_signal = signal.SIGINT

                testing.common.database.Database.terminate(self, send_signal)

        kwargs = {"base_dir": str(tmp_path_factory.mktemp("pg"))}

        if sys.platform != "win32":
            # Use /tmp on macOS/Linux to avoid long path issues with PostgreSQL domain sockets
            socket_dir = tempfile.mkdtemp(prefix="pgtest-", dir="/tmp")
            args: str = str(testing.postgresql.Postgresql.DEFAULT_SETTINGS["postgres_args"])
            args += f" -c unix_socket_directories={socket_dir}"
            kwargs["postgres_args"] = args

        with CustomPostgresql(**kwargs) as postgresql:
            try:
                logger.info("Starting postgres at:", base_dir=postgresql.base_dir)
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
) -> "AsyncGenerator[AsyncConnectionPool[AsyncConnection[TupleRow]], None] | AsyncGenerator[None, None]":
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
            # Add timeout parameters (avoid short timeouts that cause flaky tests)
            timeout=30,
            reconnect_timeout=30,
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

    storage_instance = PostgresStorage(dsn=postgres_testing.url())  # pyright: ignore [reportArgumentType]
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

        await storage_instance.teardown()
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
    sqlite_template_db: Path,
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
        await storage_instance.teardown()
    else:  # sqlite
        storage_instance = await _create_sqlite_storage(tmp_path, sqlite_template_db)

        StorageService.set_for_testing(storage_instance)
        FileManagerService.reset()

        yield storage_instance
        await _teardown_sqlite_storage(tmp_path, storage_instance)

    StorageService.reset()
    FileManagerService.reset()


@pytest.fixture
async def sqlite_model_creator(sqlite_storage: "SQLiteStorage", tmp_path: Path) -> "SampleModelCreator":
    from server.tests.storage.sample_model_creator import SampleModelCreator

    smc = SampleModelCreator(sqlite_storage, tmp_path)
    await smc.setup()
    return smc


@pytest.fixture
async def postgres_model_creator(postgres_storage: "PostgresStorage", tmp_path: Path) -> "SampleModelCreator":
    from server.tests.storage.sample_model_creator import SampleModelCreator

    smc = SampleModelCreator(postgres_storage, tmp_path)
    await smc.setup()
    return smc
