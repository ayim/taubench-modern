import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

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
    import logging

    from agent_server_orchestrator.bootstrap_agent_server import AgentServerProcess

    logger = logging.getLogger("start_agent_server")

    logger.debug(f"Starting agent server with tmpdir={tmpdir}, logs_dir={logs_dir}")

    agent_server_data_dir = Path(tmpdir) / "agent_server_data"
    agent_server_data_dir.mkdir(parents=True, exist_ok=True)
    agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)

    logger.debug("Starting agent server process...")
    # The start method now uses the refactored approach:
    # 1. setup_output_files - Sets up stdout/stderr capture
    # 2. register_port_callback - Registers a callback for port detection
    # 3. register_application_start_callback - Registers a callback for application
    #    startup
    # 4. start_process_and_wait_for_preconditions - Starts the process and waits for
    #    all preconditions
    agent_server_process.start(logs_dir=logs_dir, timeout=10 * 60, env=env)

    logger.debug(
        f"Agent server started with host={agent_server_process.host}, "
        f"port={agent_server_process.port}"
    )
    url = f"http://{agent_server_process.host}:{agent_server_process.port}"
    logger.debug(f"Yielding URL: {url}")

    try:
        yield url
    finally:
        logger.debug("Stopping agent server process...")
        agent_server_process.stop()
        logger.debug("Agent server process stopped")


@pytest.fixture
def base_url_agent_server(tmpdir, logs_dir, files_location):
    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "true")
    if start_server == "true":
        with start_agent_server(tmpdir, logs_dir) as url:
            yield url
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", "8000")
        yield f"http://{host}:{port}"
