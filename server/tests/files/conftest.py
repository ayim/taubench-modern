import os
from pathlib import Path

import pytest
from agent_platform.orchestrator.bootstrap_agent_server import AgentServerProcess

# Get storage and auth fixtures.
from server.tests.auth_fixtures import *  # noqa: F403
from server.tests.storage_fixtures import *  # noqa: F403


@pytest.fixture(scope="session", autouse=True)
def _load_env():
    """Ensure environment variables are loaded."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


@pytest.fixture
def files_location(tmpdir) -> Path:
    return Path(tmpdir) / "files"


@pytest.fixture
def create_sample_file(tmpdir):
    def _do_create():
        import random
        import string
        import tempfile

        key = "".join(random.choices(string.ascii_lowercase, k=5))
        value = "".join(random.choices(string.ascii_lowercase, k=5))
        content = f"This is a sample file for testing. Key: {key}, Value: {value}"

        temp_file = tempfile.NamedTemporaryFile(
            mode="w+",
            delete=False,
            suffix=".txt",
            dir=str(tmpdir),
        )
        temp_file.write(content)
        temp_file.close()
        return temp_file.name, key, value

    return _do_create


@pytest.fixture(scope="session")
def openai_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    return key


def _get_base_url(tmpdir, logs_dir, files_location, env_vars):
    # Use patch.dict to properly isolate environment variables
    from unittest.mock import patch

    # Set INTEGRATION_TEST_START_SERVER to true by default (it should be
    # possible to anyone to get the project and run "make test-integration"
    # and have tests pass -- INTEGRATION_TEST_START_SERVER can be set to
    # False when developing locally to connect to a running instance if needed).
    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "true")
    if start_server == "true":
        print("Starting agent server")
        agent_server_data_dir = Path(tmpdir) / "agent_server_data"
        agent_server_data_dir.mkdir(parents=True, exist_ok=True)
        agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)

        # Use patch.dict to isolate environment variables
        with patch.dict(os.environ, env_vars):
            agent_server_process.start(
                logs_dir=logs_dir,
                timeout=10 * 60,
                env=env_vars,
            )
            try:
                yield f"http://{agent_server_process.host}:{agent_server_process.port}"
            finally:
                agent_server_process.stop()
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", "8000")
        yield f"http://{host}:{port}"


@pytest.fixture
def base_url_agent_server_sqlite(tmpdir, logs_dir, files_location):
    env_vars = {
        "S4_AGENT_SERVER_DB_TYPE": "sqlite",
        "S4_AGENT_SERVER_FILE_MANAGER_TYPE": "local",  # Explicitly use local file manager
    }
    yield from _get_base_url(tmpdir, logs_dir, files_location, env_vars)


@pytest.fixture
def base_url_agent_server_postgres(tmpdir, logs_dir, files_location):
    env_vars = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "agent-server",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "S4_AGENT_SERVER_FILE_MANAGER_TYPE": "local",  # Explicitly use local file manager
    }
    yield from _get_base_url(tmpdir, logs_dir, files_location, env_vars)


@pytest.fixture
def base_url_agent_server_sqlite_cloud(tmpdir, logs_dir, files_location):
    env_vars = {
        "S4_AGENT_SERVER_DB_TYPE": "sqlite",
        "FILE_MANAGEMENT_API_URL": "http://localhost:8001",
        "S4_AGENT_SERVER_FILE_MANAGER_TYPE": "cloud",
    }
    yield from _get_base_url(tmpdir, logs_dir, files_location, env_vars)


@pytest.fixture
def base_url_agent_server_postgres_cloud(tmpdir, logs_dir, files_location):
    env_vars = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "agent-server",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "FILE_MANAGEMENT_API_URL": "http://localhost:8001",
        "S4_AGENT_SERVER_FILE_MANAGER_TYPE": "cloud",
    }
    yield from _get_base_url(tmpdir, logs_dir, files_location, env_vars)
