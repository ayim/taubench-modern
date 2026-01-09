import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

# Import cloud server fixture for cloud tests
from server.tests.files.test_api_endpoints_cloud import cloud_server  # noqa: F401
from server.tests.integration.work_items.conftest import (
    WorkItemsServerConfig,
    all_databases_cloud,
    all_databases_local,
    all_databases_matrix,
)


@pytest.fixture
def files_location(tmpdir) -> Path:
    return Path(tmpdir) / "files"


@pytest.fixture
def resources_dir() -> Path:
    return Path(os.path.normpath(os.path.abspath(__file__))).parent / "resources"


@contextmanager
def start_agent_server(tmpdir, logs_dir, env: dict[str, str] | None = None) -> Iterator[str]:
    import logging

    from agent_platform.orchestrator.bootstrap_agent_server import AgentServerProcess

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

    logger.debug(f"Agent server started with host={agent_server_process.host}, port={agent_server_process.port}")
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


@pytest.fixture(scope="session")
def base_url_agent_server_session(tmp_path_factory, base_logs_directory):
    """Session-scoped agent server that starts once and is reused across all tests.

    This is faster than function-scoped fixtures but requires tests to be independent
    (create their own agents/threads) to avoid interference.
    """
    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "true")
    if start_server == "true":
        tmpdir = tmp_path_factory.mktemp("agent_server_session")
        logs_dir = base_logs_directory / "agent_server_session"
        logs_dir.mkdir(parents=True, exist_ok=True)

        with start_agent_server(tmpdir, logs_dir) as url:
            yield url
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", "8000")
        yield f"http://{host}:{port}"


@pytest.fixture
def base_url_agent_server_with_data_frames(tmpdir, logs_dir, files_location):
    env_vars = {
        "SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES": "true",
    }

    with start_agent_server(tmpdir, logs_dir, env=env_vars) as url:
        yield url


@pytest.fixture(
    params=[
        "async",
        "sync",
    ]
)
def base_url_agent_server_sync_and_async_actions_and_sync_mode(tmpdir, logs_dir, files_location, request):
    """Fixture that starts agent server with async actions enabled."""

    sync_mode = request.param

    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "true")
    if start_server == "true":
        if sync_mode == "async":
            env_vars = {
                "SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION": "true",
                "ACTIONS_ASYNC_RETRY_INTERVAL": "0.1",
                "ACTIONS_ASYNC_MAX_RETRIES": "100",
                "ACTIONS_ASYNC_TIMEOUT": "0",  # force async mode
            }
        else:
            env_vars = {
                "SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION": "false",
            }

        with patch.dict(os.environ, env_vars):
            with start_agent_server(tmpdir, logs_dir, env=env_vars) as url:
                yield {"url": url, "sync_mode": sync_mode}

    else:  # noqa
        if sync_mode == "async":
            host = os.getenv("API_HOST", "localhost")
            port = os.getenv("API_PORT", "8000")
            yield {"url": f"http://{host}:{port}", "sync_mode": sync_mode}

        else:
            # devs can tweak this manually if neededed, but given async is the default
            # only test for it.
            pytest.skip("Only async mode is supported when starting the server manually.")


@pytest.fixture
def base_url_agent_server_with_work_items(tmpdir, logs_dir):
    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "true")
    if start_server == "true":
        env_vars = {
            "S4_AGENT_SERVER_FILE_MANAGER_TYPE": "local",  # Explicitly use local file manager
        }

        with patch.dict(os.environ, env_vars):
            with start_agent_server(tmpdir, logs_dir, env=env_vars) as url:
                yield url
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", "8000")
        yield f"http://{host}:{port}"


def _get_work_items_server_url(
    tmpdir,
    logs_dir,
    server_config: WorkItemsServerConfig,
    cloud_server=None,  # noqa: F811
):
    """Create work items server URL with specified storage and file management configuration."""

    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "true")
    if start_server == "true":
        # Build environment variables based on configuration
        env_vars = {
            # We need to set the Work Item URL,
            # so that the tests related to building work item URL succeed.
            "SEMA4AI_AGENT_SERVER_WORK_ITEM_URL": "https://localhost:8000/tenants/123/worker/{agent_id}/{work_item_id}/{thread_id}",
        }

        if server_config.storage_type == "sqlite":
            env_vars["S4_AGENT_SERVER_DB_TYPE"] = "sqlite"
        else:  # postgres
            env_vars.update(
                {
                    "POSTGRES_HOST": "localhost",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_DB": "agent-server",
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "postgres",
                }
            )

        if server_config.file_management_type == "cloud":
            env_vars.update(
                {
                    "FILE_MANAGEMENT_API_URL": "http://localhost:8001",
                    "S4_AGENT_SERVER_FILE_MANAGER_TYPE": "cloud",
                }
            )
        else:  # local
            env_vars["S4_AGENT_SERVER_FILE_MANAGER_TYPE"] = "local"

        # Use patch.dict to properly isolate environment variables
        with patch.dict(os.environ, env_vars):
            with start_agent_server(tmpdir, logs_dir, env=env_vars) as url:
                yield url
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", "8000")
        yield f"http://{host}:{port}"


def _get_evals_server_url(
    tmpdir,
    logs_dir,
    server_config: WorkItemsServerConfig,
    cloud_server=None,  # noqa: F811
):
    """Create evals server URL with specified storage and file management configuration."""

    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "true")
    if start_server == "true":
        # Build environment variables based on configuration
        env_vars = {}

        if server_config.storage_type == "sqlite":
            env_vars["S4_AGENT_SERVER_DB_TYPE"] = "sqlite"
        else:  # postgres
            env_vars.update(
                {
                    "POSTGRES_HOST": "localhost",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_DB": "agent-server",
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "postgres",
                }
            )

        if server_config.file_management_type == "cloud":
            env_vars.update(
                {
                    "FILE_MANAGEMENT_API_URL": "http://localhost:8001",
                    "S4_AGENT_SERVER_FILE_MANAGER_TYPE": "cloud",
                }
            )
        else:  # local
            env_vars["S4_AGENT_SERVER_FILE_MANAGER_TYPE"] = "local"

        # Use patch.dict to properly isolate environment variables
        with patch.dict(os.environ, env_vars):
            with start_agent_server(tmpdir, logs_dir, env=env_vars) as url:
                yield url
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", "8000")
        yield f"http://{host}:{port}"


@pytest.fixture(params=all_databases_matrix)
def base_url_agent_server_workitems_matrix(request, tmpdir, logs_dir, cloud_server):  # noqa: F811
    """Parameterized fixture providing work items server URLs for all storage/file_management
    combinations."""
    server_config = request.param
    yield from _get_work_items_server_url(tmpdir, logs_dir, server_config, cloud_server)


@pytest.fixture(params=all_databases_matrix)
def base_url_agent_server_evals_matrix(request, tmpdir, logs_dir, cloud_server):  # noqa: F811
    """Parameterized fixture providing evals server URLs for all storage/file_management
    combinations."""
    server_config = request.param
    yield from _get_evals_server_url(tmpdir, logs_dir, server_config, cloud_server)


@pytest.fixture
def base_url_agent_server_evals_sqlite(tmpdir, logs_dir):
    """Fixture providing evals server URL backed by sqlite storage."""

    server_config = WorkItemsServerConfig("sqlite", "local")
    yield from _get_evals_server_url(tmpdir, logs_dir, server_config)


@pytest.fixture(params=all_databases_cloud)
def base_url_agent_server_workitems_cloud_matrix(request, tmpdir, logs_dir, cloud_server):  # noqa: F811
    """Parameterized fixture for testing across storage types (sqlite vs postgres)
    with cloud files."""
    server_config = request.param
    yield from _get_work_items_server_url(tmpdir, logs_dir, server_config, cloud_server)


@pytest.fixture(params=all_databases_local)
def base_url_agent_server_workitems_storage_matrix(request, tmpdir, logs_dir):
    """Parameterized fixture for testing across storage types (sqlite vs postgres)
    with local files."""
    storage_type = request.param
    server_config = WorkItemsServerConfig(storage_type, "local")
    yield from _get_work_items_server_url(tmpdir, logs_dir, server_config)
