# These are the fixtures from the agent server sdk.
# Meant to be used in pytest tests.
import logging
import os
from pathlib import Path

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def base_logs_directory() -> Path:
    # Get the logs directory based on the cwd (search for the pyproject.toml to find the root)
    initial_cwd = cwd = Path(os.path.normpath(os.path.abspath(os.path.dirname("."))))

    while True:
        if (cwd / "pyproject.toml").exists():
            base_logs_directory = cwd / "logs"
            break

        next_cwd = cwd.parent
        if next_cwd == cwd or not next_cwd:
            base_logs_directory = initial_cwd / "logs"
            msg = (
                f"Could not find the root of the project (pyproject.toml "
                f"file not found as a parent of: {initial_cwd}). "
                f"Using {base_logs_directory} as the base logs directory."
            )
            log.critical(msg)
            break

        cwd = next_cwd
    base_logs_directory.mkdir(parents=True, exist_ok=True)

    # Ok, we have the base logs directory, now, add a `run-<next-run-id>` directory to it.
    next_run_id = 0
    for directory in os.listdir(base_logs_directory):
        if directory.startswith("run-"):
            try:
                next_run_id = max(next_run_id, int(directory.split("-")[1]))
            except ValueError:
                pass  # Could not do `int`

    next_run_id += 1
    used_dir = base_logs_directory / f"run-{next_run_id}-pid-{os.getpid()}"
    used_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n\nLOGS DIRECTORY: {used_dir}\n")
    return used_dir


@pytest.fixture
def logs_dir(base_logs_directory, request) -> Path:
    directory = base_logs_directory / request.node.name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.fixture
def copy_tmpdir_on_failure(request, tmpdir, logs_dir):
    """
    Copy the tmpdir contents to the logs_dir on failure so that
    we can inspect the contents of the tmpdir on a failure in the ci.
    """
    failed = request.session.testsfailed
    yield

    if failed != request.session.testsfailed:
        import shutil

        # Copy tmpdir contents to logs directory with test name
        dest = logs_dir / "tmpdir_contents"
        shutil.copytree(tmpdir, dest, dirs_exist_ok=True)


def assert_status(response, message: str = "", valid_statuses: tuple[int, ...] = (200,)):
    if response.status not in valid_statuses:
        raise AssertionError(
            f"{message}\nExpected status: {valid_statuses}\n"
            f"Actual status: {response.status}\nBody: {response.data!r}"
        )


@pytest.fixture
def action_server_executable_path() -> Path:
    from agent_platform.orchestrator.default_locations import (
        get_action_server_executable_path,
    )

    action_server_path = get_action_server_executable_path()
    return action_server_path


@pytest.fixture
def action_server_process(tmpdir, action_server_executable_path: Path):
    from agent_platform.orchestrator.bootstrap_action_server import ActionServerProcess

    action_server_process = ActionServerProcess(
        datadir=Path(tmpdir) / "action_server_data",
        executable_path=action_server_executable_path,
    )
    yield action_server_process
    action_server_process.stop()


@pytest.fixture(scope="session")
def openai_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    return key


@pytest.fixture(scope="session")
def anthropic_api_key():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

    return key
