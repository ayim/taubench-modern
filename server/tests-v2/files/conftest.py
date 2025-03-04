import os
from pathlib import Path

import pytest

from tests.integration_tests.bootstrap_agent_server import AgentServerProcess


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Ensure environment variables are loaded."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


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
    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = str(value)

    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "false")
    if start_server == "true":
        print("Starting agent server")
        agent_server_data_dir = Path(tmpdir) / "agent_server_data"
        agent_server_data_dir.mkdir(parents=True, exist_ok=True)
        agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)
        agent_server_process.start(
            logs_dir=logs_dir,
            env=env_vars,
        )
        yield f"http://{agent_server_process.host}:{agent_server_process.port}"
        agent_server_process.stop()
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", 8000)
        yield f"http://{host}:{port}"


@pytest.fixture
def base_url_agent_server_sqlite(tmpdir, logs_dir, files_location):
    env_vars = {
        "S4_AGENT_SERVER_DB_TYPE": "sqlite",
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
    }
    yield from _get_base_url(tmpdir, logs_dir, files_location, env_vars)


@pytest.fixture
def base_url_agent_server_sqlite_cloud(tmpdir, logs_dir, files_location):
    env_vars = {
        "S4_AGENT_SERVER_DB_TYPE": "sqlite",
        "FILE_MANAGEMENT_API_URL": "https://localhost:8001",
        "S4_AGENT_SERVER_FILE_MANAGER": "cloud",
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
        "FILE_MANAGEMENT_API_URL": "https://localhost:8001",
        "S4_AGENT_SERVER_FILE_MANAGER": "cloud",
    }
    yield from _get_base_url(tmpdir, logs_dir, files_location, env_vars)
