import os
import platform
import shutil
import subprocess
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from pathlib import Path
from uuid import uuid4

import dotenv
import pytest
import pytest_asyncio
import requests
import sqlalchemy.exc
from agent_platform.orchestrator.bootstrap_agent_server import AgentServerProcess
from agent_platform.orchestrator.pytest_fixtures import base_logs_directory  # noqa: F401
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.workitems.agents.client import AgentClient, AgentInfo, InvokeAgentResponse
from agent_platform.workitems.agents.models import RunStatusResponse
from agent_platform.workitems.api import router as workitems_router
from agent_platform.workitems.db import DatabaseManager, instance
from agent_platform.workitems.main import _configure_logging
from agent_platform.workitems.orm.base import Base
from agent_platform.workitems.orm.workitem import WorkItemORM


class MockAgentClient(AgentClient):
    """Mock AgentClient with static test data."""

    def __init__(self):
        self.agents = {
            "test-agent-1": AgentInfo(
                agent_id="test-agent-1", name="Test Agent 1", user_id="user-123"
            ),
            "test-agent-2": AgentInfo(
                agent_id="test-agent-2", name="Test Agent 2", user_id="user-456"
            ),
        }

    async def describe_agent(self, agent_id: str) -> AgentInfo | None:
        """Return agent info for test agents, None for others."""
        return self.agents.get(agent_id)

    async def invoke_agent(
        self, agent_id: str, payload: InitiateStreamPayload
    ) -> InvokeAgentResponse:
        """Mock invoke_agent method."""
        return InvokeAgentResponse(
            run_id="test-run-id",
            status="running",
        )

    async def get_messages(self, run_id: str) -> list[ThreadMessage]:
        """Mock get_messages method."""
        return [
            ThreadMessage(
                role="agent",
                content=[
                    ThreadTextContent(text="test-message", complete=True),  # type: ignore
                ],
                complete=True,
            ),
        ]

    async def get_run_status(self, run_id: str) -> RunStatusResponse | None:
        """Mock get_run_status method."""
        return RunStatusResponse(
            run_id=run_id,
            status="completed",
        )


################################################################################
# Database fixtures (starts a PostgreSQL container and provides a database URL)
################################################################################


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Start PostgreSQL container once per test session."""
    if not _is_docker_available():
        pytest.skip("Skipping test as Docker is not available")

    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> Generator[str, None, None]:
    """Get database URL from PostgreSQL container."""
    # Build URL using psycopg (version 3) instead of psycopg2
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    username = postgres_container.username
    password = postgres_container.password
    database = postgres_container.dbname

    url = f"postgresql+psycopg://{username}:{password}@{host}:{port}/{database}"

    # Initialize the tables before continuing
    max_retries = 10
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            engine = create_engine(url, echo=True)
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            # If connection works, create tables
            Base.metadata.create_all(engine)

            yield url

            engine.dispose()
            return
        except sqlalchemy.exc.OperationalError as e:
            if attempt < max_retries - 1:
                print(f"Database attempt {attempt + 1} failed, retrying in {retry_delay}s")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff
            else:
                raise e


################################################################################
# Fixtures for E2E tests (starts a standalone agent-server as a separate process)
################################################################################


@pytest.fixture
def logs_dir(base_logs_directory, request) -> Path:  # noqa: F811
    directory = base_logs_directory / request.node.name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.fixture
def agent_server_data_dir(tmpdir):
    return Path(tmpdir) / "agent_server_data"


@pytest.fixture
def agent_server_url(
    tmpdir, logs_dir, agent_server_data_dir, database_url
) -> Generator[str, None, None]:
    print(f"Starting agent server with logs_dir={logs_dir}, workitems database_url={database_url}")

    agent_server_data_dir = Path(tmpdir) / "agent_server_data"
    agent_server_data_dir.mkdir(parents=True, exist_ok=True)
    agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)

    env = {
        "SEMA4AI_WORKITEMS_DATABASE_URL": database_url,
        # wait 1s in between scans over the DB looking for work-items
        "WORKITEMS_WORKER_INTERVAL": "1",
    }

    print("Starting agent server process...")
    agent_server_process.start(logs_dir=logs_dir, timeout=10 * 60, env=env)

    print(
        f"Agent server started with host={agent_server_process.host}, "
        f"port={agent_server_process.port}"
    )
    url = f"http://{agent_server_process.host}:{agent_server_process.port}"
    print(f"Yielding URL: {url}")

    try:
        yield url
    finally:
        print("Stopping agent server process...")
        agent_server_process.stop()
        print("Agent server process stopped")


@pytest.fixture
async def agent_id(agent_server_url: str) -> AsyncGenerator[str, None]:
    dotenv.load_dotenv()
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        pytest.skip("OPENAI_API_KEY environment variable not set")

    payload = {
        "mode": "conversational",
        "name": f"test-work-items-agent-{uuid4()}",
        "version": "1.0.0",
        "description": ("This is a test agent for work-items testing."),
        "runbook": "# Objective\nYou are a helpful assistant.",
        "platform_configs": [
            {
                "kind": "openai",
                "openai_api_key": openai_key,
            },
        ],
        "agent_architecture": {
            "name": "agent_platform.architectures.default",
            "version": "1.0.0",
        },
    }

    response = requests.post(f"{agent_server_url}/api/v2/agents", json=payload)
    assert response.status_code == 200, f"Failed to create agent: {response.json()}"

    agent_id = response.json()["agent_id"]
    yield agent_id

    # Cleanup the agent
    requests.delete(f"{agent_server_url}/api/v2/agents/{agent_id}")


################################################################################
# Fixtures for unit-tests
################################################################################


@pytest.fixture
async def database_manager(database_url) -> AsyncGenerator[DatabaseManager, None]:
    """Create a database session for each test and clean up after."""

    database_manager = DatabaseManager()
    database_manager.init_engine(database_url)

    yield database_manager

    # Cleanup: Delete all data from all tables
    async with database_manager.begin() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(text(f"DELETE FROM {table.name}"))


@pytest.fixture
def mock_agent_client() -> MockAgentClient:
    """Provide a mock AgentClient with test data."""
    return MockAgentClient()


@pytest.fixture
async def _app(
    database_url: str, mock_agent_client: MockAgentClient
) -> AsyncGenerator[FastAPI, None]:
    """Create FastAPI app for testing with a mocked AgentServerClient."""
    _configure_logging()

    # Initialize the database manager with test database, and forces
    # use of this database
    instance.init_engine(database_url)

    app = FastAPI()
    app.include_router(workitems_router)

    # Override the agent client dependency for testing
    def get_test_agent_client():
        return mock_agent_client

    # Override the dependency
    from agent_platform.workitems.api import get_agent_client_from_request

    app.dependency_overrides[get_agent_client_from_request] = get_test_agent_client

    yield app

    # Cleanup: Delete all data from all tables
    engine = None
    try:
        engine = create_async_engine(database_url, echo=True)
        session = async_sessionmaker(bind=engine)()
        # Cleanup: Delete all data from all tables
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(text(f"DELETE FROM {table.name}"))
        await session.commit()
        await session.close()
    finally:
        if engine is not None:
            await engine.dispose()


@pytest_asyncio.fixture
async def client(_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing the FastAPI app with a mocked AgentServerClient."""
    async with AsyncClient(
        transport=ASGITransport(app=_app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
def mock_run_agent(
    agent_server_url: str,
) -> Callable[[AsyncSession, WorkItemORM, AgentClient], Awaitable[bool]]:
    """Fake run_agent function that always returns True."""

    async def noop_run_agent(
        session: AsyncSession, item: WorkItemORM, agent_client: AgentClient
    ) -> bool:
        return True

    return noop_run_agent


################################################################################
# Docker-related fixtures
################################################################################


def _is_docker_available() -> bool:
    """Check if docker is available and running on the system."""
    if platform.system() == "Windows" or not shutil.which("docker"):
        return False
    try:
        # Run 'docker info' and check if it succeeds
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,  # Don't hang for too long if docker daemon is stuck
            check=True,  # Raise an exception if the command returns non-zero
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        # Handle any subprocess errors (timeout, command failed, etc.)
        return False


@pytest.fixture(scope="session")
def docker_available() -> bool:
    """Check if Docker is available and running on the system."""
    return _is_docker_available()


@pytest.fixture(autouse=False)
def require_docker(docker_available):
    """Skip test if Docker is not available. Use this fixture in tests that need Docker."""
    if not docker_available:
        pytest.skip("Skipping test as Docker is not available")
