import typing
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import cast

import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from agent_platform.core.mcp.mcp_server import MCPServer

if typing.TYPE_CHECKING:
    from agent_platform.core.agent.agent import Agent
    from agent_platform.core.thread.thread import Thread
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.fixture
def sample_agent(sample_user_id: str) -> "Agent":
    from datetime import UTC, datetime
    from uuid import uuid4

    from agent_platform.core.actions.action_package import ActionPackage
    from agent_platform.core.agent.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.agent.observability_config import ObservabilityConfig
    from agent_platform.core.agent.question_group import QuestionGroup
    from agent_platform.core.runbook.runbook import Runbook
    from agent_platform.core.utils.secret_str import SecretString

    return Agent(
        user_id=sample_user_id,
        agent_id=str(uuid4()),
        name="Test Agent",
        description="Test Description",
        runbook_structured=Runbook(
            raw_text="# Objective\nYou are a helpful assistant.",
            content=[],
        ),
        version="1.0.0",
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        action_packages=[
            ActionPackage(
                name="test-action-package",
                organization="test-organization",
                version="1.0.0",
                url="https://api.test.com",
                api_key=SecretString("test"),
                allowed_actions=["action_1", "action_2"],
            ),
            ActionPackage(
                name="test-action-package-2",
                organization="test-organization-2",
                version="1.0.0",
                url="https://api.test-2.com",
                api_key=SecretString("test-2"),
                allowed_actions=[],
            ),
        ],
        agent_architecture=AgentArchitecture(
            name="agent-architecture-default-v2",
            version="1.0.0",
        ),
        question_groups=[
            QuestionGroup(
                title="Test Question Group",
                questions=[
                    "Here's one question",
                    "Here's another question",
                ],
            ),
        ],
        observability_configs=[
            ObservabilityConfig(
                type="langsmith",
                api_key="test",
                api_url="https://api.langsmith.com",
                settings={"some_extra_setting": "some_extra_value"},
            ),
        ],
        platform_configs=[],
        extra={"agent_extra": "some_extra_value"},
    )


@pytest.fixture
def sample_thread(
    sample_user_id: str,
    sample_agent: "Agent",
) -> "Thread":
    from datetime import UTC, datetime
    from uuid import uuid4

    from agent_platform.core.thread.base import ThreadMessage, ThreadTextContent
    from agent_platform.core.thread.thread import Thread

    return Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Test Thread",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello, how are you?")],
            ),
            ThreadMessage(
                role="agent",
                content=[ThreadTextContent(text="I'm fine, thank you!")],
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={"thread_metadata": "some_metadata"},
    )


@pytest.fixture
def sample_mcp_server_http() -> MCPServer:
    """Sample MCP server using HTTP transport."""
    return MCPServer(
        name="test-http-server",
        transport="streamable-http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer test-token"},
    )


@pytest.fixture
def sample_mcp_server_stdio() -> MCPServer:
    """Sample MCP server using stdio transport."""
    return MCPServer(
        name="test-stdio-server",
        transport="stdio",
        command="python",
        args=["-m", "mcp_test_server"],
        env={"TEST_ENV": "test_value"},
        cwd="/tmp",
    )


@pytest.fixture
def sample_mcp_server_sse() -> MCPServer:
    """Sample MCP server using SSE transport."""
    return MCPServer(
        name="test-sse-server",
        transport="sse",
        url="https://example.com/sse",
    )


@pytest.fixture(scope="session", autouse=True)
def _disable_logging() -> Generator[None, None, None]:
    """Disable verbose logging for the entire session."""
    from logging import CRITICAL, INFO, getLogger

    getLogger("agent_platform.server.storage.postgres.migrations").setLevel(CRITICAL)
    getLogger("agent_platform.server.storage.postgres.postgres").setLevel(CRITICAL)

    getLogger("agent_platform.storage.sqlite.migrations").setLevel(CRITICAL)
    getLogger("agent_platform.storage.sqlite.sqlite").setLevel(CRITICAL)

    yield

    getLogger("agent_platform.storage.sqlite.migrations").setLevel(INFO)
    getLogger("agent_platform.storage.sqlite.sqlite").setLevel(INFO)

    getLogger("agent_platform.server.storage.postgres.migrations").setLevel(INFO)
    getLogger("agent_platform.server.storage.postgres.postgres").setLevel(INFO)


@pytest.fixture(scope="session")
async def postgres_testing():
    # Lazy import testing.postgresql only when needed
    import testing.postgresql

    with testing.postgresql.Postgresql() as postgresql:
        try:
            yield postgresql
        finally:
            postgresql.stop()


@pytest.fixture(scope="session", params=[pytest.param("postgres", marks=[pytest.mark.postgresql])])
async def postgres_test_db(
    postgres_testing,
) -> "AsyncGenerator[AsyncConnectionPool[AsyncConnection[TupleRow]], None]":
    """Creates a shared temporary Postgres instance for the entire test session."""
    from psycopg import AsyncConnection
    from psycopg.rows import TupleRow
    from psycopg_pool import AsyncConnectionPool

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


async def _create_sqlite_storage(tmp_path: Path) -> "SQLiteStorage":
    """Helper function to create and setup SQLite storage."""
    from agent_platform.server.storage.sqlite import SQLiteStorage

    test_file_path = tmp_path / "test_sqlite_storage.db"
    storage_instance = SQLiteStorage(db_path=str(test_file_path))
    if test_file_path.exists():
        test_file_path.unlink()
    await storage_instance.setup()
    await storage_instance.get_or_create_user(
        sub="tenant:testing:system:system_user",
    )
    return storage_instance


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
async def sqlite_storage(tmp_path: Path) -> "AsyncGenerator[SQLiteStorage, None]":
    """
    Initialize SQLiteStorage with an ephemeral database.
    We'll also seed a system user, just like in Postgres tests.
    """
    storage_instance = await _create_sqlite_storage(tmp_path)
    yield storage_instance
    await storage_instance.teardown()
    test_file_path = tmp_path / "test_sqlite_storage.db"
    if test_file_path.exists():
        test_file_path.unlink()


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
    try:
        storage_instance = await _create_postgres_storage(postgres_test_db, postgres_testing)
        yield storage_instance
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
    if request.param == "postgres":
        storage_instance = await _create_postgres_storage(postgres_test_db, postgres_testing)
        yield storage_instance
    else:  # sqlite
        storage_instance = await _create_sqlite_storage(tmp_path)
        yield storage_instance
        await storage_instance.teardown()
        test_file_path = tmp_path / "test_sqlite_storage.db"
        if test_file_path.exists():
            test_file_path.unlink()
