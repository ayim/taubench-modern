from collections.abc import AsyncGenerator, Generator

import pytest
import testing.postgresql
from psycopg_pool import AsyncConnectionPool

from sema4ai_agent_server.storage.v2.postgres_v2 import PostgresStorageV2


@pytest.fixture(scope="session", autouse=True)
def _disable_logging() -> Generator[None, None, None]:
    """Disable verbose logging for the entire session."""
    from logging import CRITICAL, INFO

    from structlog import get_logger

    get_logger("sema4ai_agent_server.storage.v2.postgres_v2.migrations").setLevel(CRITICAL)
    get_logger("sema4ai_agent_server.storage.v2.postgres_v2.postgres").setLevel(CRITICAL)
    yield
    get_logger("sema4ai_agent_server.storage.v2.postgres_v2.migrations").setLevel(INFO)
    get_logger("sema4ai_agent_server.storage.v2.postgres_v2.postgres").setLevel(INFO)

@pytest.fixture(scope="session")
async def postgres_test_db() -> AsyncGenerator[AsyncConnectionPool, None]:
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
            yield pool
        finally:
            if pool:
                await pool.close()
            postgresql.stop()

@pytest.fixture
async def storage(postgres_test_db: AsyncConnectionPool):
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
        storage = PostgresStorageV2(pool=postgres_test_db)
        await storage.setup_v2()  # Runs migrations to re-create tables in 'v2'.

        # Seed the system user.
        await storage.get_or_create_user_v2(sub="tenant:testing:system:system_user")
        yield storage
        # No teardown: trying to keep pool open for the duration of the test session.
        # await storage.teardown_v2()
    except Exception as e:
        # Log any connection issues
        import logging
        logging.error(f"Error in storage fixture: {e}")
        raise

@pytest.fixture
async def sample_user_id(storage: PostgresStorageV2) -> str:
    return await storage.get_system_user_id_v2()
