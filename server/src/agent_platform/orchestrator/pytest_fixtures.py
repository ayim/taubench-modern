# These are the fixtures from the agent server sdk.
# Meant to be used in pytest tests.
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from filelock import FileLock

log = logging.getLogger(__name__)


def _get_prewarm_lock_path() -> Path:
    """Get a consistent lock file path for pre-warming across all workers."""
    return Path(tempfile.gettempdir()) / "sema4ai_action_server_prewarm.lock"


def _prewarm_action_server_environment(
    executable_path: Path,
    action_package_path: Path,
) -> None:
    """
    Pre-warm the action server environment by importing an action package.
    This triggers RCC to download micromamba and create the holotree environment.

    Uses file locking to ensure only one process does the download/bootstrap
    at a time. The operation is idempotent - if the environment already exists
    in the holotree cache, the import completes quickly.
    """
    lock_path = _get_prewarm_lock_path()

    log.info("Acquiring lock for pre-warming action server environment...")

    with FileLock(lock_path, timeout=900):  # 15 minute timeout for download/bootstrap
        log.info(f"Lock acquired. Pre-warming action server environment from {action_package_path}")

        with tempfile.TemporaryDirectory() as tmpdir:
            datadir = Path(tmpdir) / "prewarm_datadir"
            datadir.mkdir(parents=True, exist_ok=True)

            args = [
                str(executable_path),
                "import",
                f"--dir={action_package_path}",
                f"--datadir={datadir}",
                "--db-file=:memory:",
            ]

            log.info(f"Running: {' '.join(args)}")

            try:
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=900,  # 15 minute timeout
                    cwd=str(action_package_path),
                    check=False,
                )

                if result.returncode != 0:
                    log.error(f"Pre-warm failed with return code {result.returncode}")
                    log.error(f"Stdout: {result.stdout}")
                    log.error(f"Stderr: {result.stderr}")
                    raise RuntimeError(f"Failed to pre-warm action server environment: {result.stderr}")

                log.info("Action server environment pre-warmed successfully")

            except subprocess.TimeoutExpired:
                log.error("Pre-warm timed out after 15 minutes")
                raise


@pytest.fixture(scope="session")
def prewarm_action_server_env(action_server_executable_path: Path) -> None:
    """
    Session-scoped fixture that pre-warms the RCC/micromamba environment.

    This fixture uses file-based locking to ensure that when running tests
    in parallel with pytest-xdist, only one worker process downloads and
    bootstraps the RCC/micromamba environment. Other workers will wait for
    the lock and then verify the environment is ready.

    This prevents race conditions where multiple workers try to download
    micromamba concurrently, leading to "permission denied" errors.
    """
    # Path: server/src/agent_platform/orchestrator/pytest_fixtures.py
    # We need: server/tests/integration/resources/
    server_dir = Path(__file__).parent.parent.parent.parent  # -> server/src -> server/
    resources_dir = server_dir / "tests" / "integration" / "resources"
    action_package_path = resources_dir / "simple_action_package"

    if not action_package_path.exists():
        log.warning(f"Action package path not found: {action_package_path}, skipping pre-warm")
        return

    _prewarm_action_server_environment(
        executable_path=action_server_executable_path,
        action_package_path=action_package_path,
    )


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
            f"{message}\nExpected status: {valid_statuses}\nActual status: {response.status}\nBody: {response.data!r}"
        )


@pytest.fixture(scope="session")
def action_server_executable_path() -> Path:
    from agent_platform.orchestrator.default_locations import (
        get_action_server_executable_path,
    )

    action_server_path = get_action_server_executable_path()
    return action_server_path


@pytest.fixture
def action_server_process(tmpdir, action_server_executable_path: Path, prewarm_action_server_env):
    import subprocess
    import threading

    from agent_platform.orchestrator.bootstrap_action_server import ActionServerProcess

    action_server_process = ActionServerProcess(
        datadir=Path(tmpdir) / "action_server_data",
        executable_path=action_server_executable_path,
    )
    yield action_server_process

    # Stop with timeout to prevent indefinite hangs during teardown
    stop_timeout = 30  # seconds
    stop_event = threading.Event()

    def stop_with_timeout():
        try:
            action_server_process.stop()
        finally:
            stop_event.set()

    stop_thread = threading.Thread(target=stop_with_timeout, daemon=True)
    stop_thread.start()
    stop_thread.join(timeout=stop_timeout)

    if not stop_event.is_set():
        log.error(
            f"Action server process did not stop within {stop_timeout}s timeout. "
            "This may indicate a hung subprocess. Attempting forceful cleanup..."
        )
        # Try to forcefully kill the process if we have access to it
        if hasattr(action_server_process, "_process") and action_server_process._process:
            try:
                pid = action_server_process._process.pid
                log.warning(f"Sending SIGKILL to action server process tree (PID: {pid})")
                subprocess.run(
                    ["pkill", "-9", "-P", str(pid)],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                subprocess.run(["kill", "-9", str(pid)], capture_output=True, timeout=5, check=False)
            except Exception as e:
                log.error(f"Failed to forcefully kill action server process: {e}")


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
