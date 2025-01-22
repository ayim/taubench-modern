import os
from functools import lru_cache
from pathlib import Path

import pytest


@pytest.fixture
def logs_dir(request) -> Path:
    directory = (
        Path(os.path.normpath(os.path.abspath(os.path.dirname(__file__))))
        / f"logs/{request.node.name}-{os.getpid()}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.fixture
def base_url_agent_server(tmpdir, logs_dir):
    from tests.integration_tests.bootstrap_agent_server import AgentServerProcess

    start_server = os.getenv("INTEGRATION_TEST_START_SERVER", "false")
    if start_server == "true":
        agent_server_data_dir = Path(tmpdir) / "agent_server_data"
        agent_server_data_dir.mkdir(parents=True, exist_ok=True)
        agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)
        agent_server_process.start(logs_dir=logs_dir)
        yield f"http://{agent_server_process.host}:{agent_server_process.port}"
        agent_server_process.stop()
    else:
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", 8000)
        yield f"http://{host}:{port}"


@lru_cache
def get_default_sema4ai_home_dir() -> Path:
    import sys

    home_env_var = os.environ.get("SEMA4AI_HOME")
    if home_env_var:
        home = Path(home_env_var)
    else:
        if sys.platform == "win32":
            localappdata = os.environ.get("LOCALAPPDATA")
            if not localappdata:
                raise RuntimeError("Error. LOCALAPPDATA not defined in environment!")
            home = Path(localappdata) / "sema4ai"
        else:
            # Linux/Mac
            home = Path("~/.sema4ai").expanduser()
    return home


@pytest.fixture
def action_server_process(tmpdir):
    import sys

    from tests.integration_tests.bootstrap_action_server import ActionServerProcess

    # We need to download the action server to the default sema4ai home dir
    # because the action server will use it to store the actions.
    action_server_download_dir = get_default_sema4ai_home_dir() / "action-server-bin"
    action_server_download_dir.mkdir(parents=True, exist_ok=True)

    version = "2.5.1"
    from sema4ai.common import tools

    suffix = ""
    if sys.platform == "win32":
        suffix = ".exe"

    target_location = action_server_download_dir / f"action-server-{version}{suffix}"
    action_server_tool = tools.ActionServerTool(
        target_location=target_location,
        tool_version=version,
    )
    action_server_tool.download()

    action_server_process = ActionServerProcess(
        datadir=Path(tmpdir) / "action_server_data",
        executable_path=target_location,
    )
    yield action_server_process
    action_server_process.stop()


@pytest.fixture(scope="session")
def openai_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    return key
