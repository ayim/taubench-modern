from collections.abc import AsyncGenerator, Generator
from typing import cast

import pytest
import testing.postgresql
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from agent_platform.server.storage.postgres import PostgresStorage


@pytest.fixture(scope="session", autouse=True)
def _disable_logging() -> Generator[None, None, None]:
    """Disable verbose logging for the entire session."""
    from logging import CRITICAL, INFO, getLogger

    getLogger("agent_platform.server.storage.postgres.migrations").setLevel(CRITICAL)
    getLogger("agent_platform.server.storage.postgres.postgres").setLevel(CRITICAL)
    yield
    getLogger("agent_platform.server.storage.postgres.migrations").setLevel(INFO)
    getLogger("agent_platform.server.storage.postgres.postgres").setLevel(INFO)

@pytest.fixture(scope="session")
async def postgres_test_db() -> AsyncGenerator[
    AsyncConnectionPool[AsyncConnection[TupleRow]],
    None,
]:
    """Creates a shared temporary Postgres instance for the entire test session."""
    with testing.postgresql.Postgresql() as postgresql:
        dsn = postgresql.url()
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
            postgresql.stop()

@pytest.fixture
async def storage(postgres_test_db: AsyncConnectionPool[AsyncConnection[TupleRow]]):
    """
    Initialize storage with the shared test database.

    Before running migrations, we clean the slate by dropping
    the 'v2' schema (if it exists) and recreating it. This
    pre-truncates any existing state from previous tests.
    """
    try:
        # Pre-truncate: Drop the schema 'v2' if it exists, then recreate it.
        async with postgres_test_db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP SCHEMA IF EXISTS v2 CASCADE;")
                await cur.execute("CREATE SCHEMA v2;")

        # Now instantiate storage and run migrations.
        storage = PostgresStorage(pool=postgres_test_db)
        await storage.setup()  # Runs migrations to re-create tables in 'v2'.

        # Seed the system user.
        await storage.get_or_create_user(sub="tenant:testing:system:system_user")
        yield storage
        # No teardown: trying to keep pool open for the duration of the test session.
        # await storage.teardown()
    except Exception as e:
        # Log any connection issues
        import logging
        logging.error(f"Error in storage fixture: {e}")
        raise

@pytest.fixture
async def sample_user_id(storage: PostgresStorage) -> str:
    return await storage.get_system_user_id()
