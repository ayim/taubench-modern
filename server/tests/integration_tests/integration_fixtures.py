import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def files_location(tmpdir) -> Path:
    return Path(tmpdir) / "files"


@pytest.fixture
def resources_dir() -> Path:
    return Path(os.path.normpath(os.path.abspath(__file__))).parent / "resources"


@contextmanager
def start_agent_server(
    tmpdir, logs_dir, env: dict[str, str] | None = None
) -> Iterator[str]:
    from agent_server_orchestrator.bootstrap_agent_server import AgentServerProcess

    agent_server_data_dir = Path(tmpdir) / "agent_server_data"
    agent_server_data_dir.mkdir(parents=True, exist_ok=True)
    agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)
    agent_server_process.start(logs_dir=logs_dir, env=env)
    try:
        yield f"http://{agent_server_process.host}:{agent_server_process.port}"
    finally:
        agent_server_process.stop()


@pytest.fixture
def base_url_agent_server(tmpdir, logs_dir, files_location):
    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "true")
    if start_server == "true":
        with start_agent_server(tmpdir, logs_dir) as url:
            yield url
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", 8000)
        yield f"http://{host}:{port}"
