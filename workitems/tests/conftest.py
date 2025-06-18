import platform
import shutil
import subprocess
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy.exc
from agent_platform.orchestrator.bootstrap_agent_server import AgentServerProcess
from agent_platform.orchestrator.pytest_fixtures import base_logs_directory  # noqa: F401
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from agent_platform.workitems.agents.client import AgentClient, AgentInfo
from agent_platform.workitems.api import router as workitems_router
from agent_platform.workitems.db import instance
from agent_platform.workitems.orm.base import Base


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


################################################################################
# Fixtures for unit-tests
################################################################################


@pytest.fixture
def session(database_url) -> Generator[Session, None, None]:
    """Create a database session for each test and clean up after."""
    engine = create_engine(database_url, echo=True)
    maker = sessionmaker(bind=engine)
    session = maker()

    yield session

    # Cleanup: Delete all data from all tables
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(text(f"DELETE FROM {table.name}"))
    session.commit()
    session.close()

    engine.dispose()


@pytest.fixture
def mock_agent_client() -> MockAgentClient:
    """Provide a mock AgentClient with test data."""
    return MockAgentClient()


@pytest.fixture
async def _app(
    database_url: str, mock_agent_client: MockAgentClient
) -> AsyncGenerator[FastAPI, None]:
    """Create FastAPI app for testing with a mocked AgentServerClient."""
    # Initialize the database manager with test database, and forces
    # use of this database
    instance.init_engine(database_url)

    app = FastAPI()
    app.include_router(workitems_router)

    # Override the agent client dependency for testing
    def get_test_agent_client():
        return mock_agent_client

    # Override the dependency
    from agent_platform.workitems.api import get_agent_client

    app.dependency_overrides[get_agent_client] = get_test_agent_client

    yield app

    # Cleanup: Delete all data from all tables
    engine = None
    try:
        engine = create_engine(database_url, echo=True)
        session = sessionmaker(bind=engine)()
        # Cleanup: Delete all data from all tables
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f"DELETE FROM {table.name}"))
        session.commit()
        session.close()
    finally:
        if engine is not None:
            engine.dispose()


@pytest_asyncio.fixture
async def client(_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing the FastAPI app with a mocked AgentServerClient."""
    async with AsyncClient(
        transport=ASGITransport(app=_app), base_url="http://testserver"
    ) as client:
        yield client


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
