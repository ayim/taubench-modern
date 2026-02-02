import logging
from dataclasses import dataclass
from pathlib import Path

import pytest

log = logging.getLogger(__name__)

DEBUG_GO = False

# To debug from VSCode use a launch config like this
# (run the test and then launch the config below):
# {
#     "name": "Connect to server",
#     "type": "go",
#     "request": "attach",
#     "mode": "remote",
#     "remotePath": "${workspaceFolder}",
#     "port": 59000,
#     "host": "127.0.0.1",
#     "debugAdapter": "dlv-dap"
# }


@dataclass
class RunResult:
    cmdline: list[str]
    stdout: str
    stderr: str
    returncode: int

    def __str__(self):
        import subprocess

        return (
            f"cmdline: {subprocess.list2cmdline(self.cmdline)}\n"
            f"stdout: {self.stdout}\n"
            f"stderr: {self.stderr}\n"
            f"returncode: {self.returncode}"
        )


def get_release_artifact_relative_path(sys_platform: str, executable_name: str) -> str:
    """
    Helper function for getting the release artifact relative path
    as defined in S3 bucket.

    Args:
        sys_platform: Platform for which the release artifact is being retrieved.
        executable_name: Name of the executable we want to get the path for.
    """
    import platform

    machine = platform.machine()
    is_64 = not machine or "64" in machine

    if sys_platform == "win32":
        if is_64:
            return f"windows64/{executable_name}.exe"
        else:
            return f"windows32/{executable_name}.exe"

    elif sys_platform == "darwin":
        return f"macos64/{executable_name}"

    elif is_64:
        return f"linux64/{executable_name}"
    else:
        return f"linux32/{executable_name}"


def run(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> RunResult:
    """
    Returns the stdout and stderr of the command
    """
    import subprocess

    print("Running: ", subprocess.list2cmdline(args))

    completed_process = subprocess.run(  # noqa: UP022
        args,
        cwd=cwd,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env=env,
        check=False,
    )

    return RunResult(
        cmdline=args,
        stdout=completed_process.stdout.decode("utf-8", "replace"),
        stderr=completed_process.stderr.decode("utf-8", "replace"),
        returncode=completed_process.returncode,
    )


def get_action_server_version(location: str) -> RunResult:
    """
    Args:
        location: The location of the action server to get the version for.

    Returns:
        The version of the action server.
    """
    return run([location, "version"], cwd=None)


def verify_action_server_downloaded_ok(
    location: str, version: str, raise_on_error: bool = True
) -> bool:
    """
    Returns:
        True if everything is ok and version matches and False otherwise.
    """
    import os.path
    import time

    if not os.path.isfile(location):
        if raise_on_error:
            raise Exception(f"Action server {location} is not a file!")
        return False
    if not os.access(location, os.X_OK):
        if raise_on_error:
            raise Exception(f"Action server {location} is not executable!")
        return False

    times = 5
    timeout = 1
    version_result = None

    for _ in range(times):
        version_result = get_action_server_version(location)
        if version_result.returncode == 0:
            if version_result.stdout.strip() == version.strip():
                return True
            else:
                if raise_on_error:
                    raise Exception(
                        f"The currently downloaded version of {location} "
                        f"({version_result.stdout!r}) "
                        f"does not match the required version "
                        f"for the vscode extension: {version}"
                    )
                return False
        time.sleep(timeout / times)

    if raise_on_error:
        raise Exception(f"Action server {location} failed to execute. Details: {version_result}")

    return False


ACTION_SERVER_VERSION = "3.0.0"

PARENT_PATH = Path(__file__).absolute().parent


def _get_action_server_path() -> Path:
    import sys

    if sys.platform == "win32":
        path = PARENT_PATH / "action-server" / "action-server.exe"
    else:
        path = PARENT_PATH / "action-server" / "action-server"
    return path


def _download_action_server_if_needed() -> None:
    import os.path
    import stat
    import sys

    path = _get_action_server_path()

    if not os.path.exists(path) or not verify_action_server_downloaded_ok(
        str(path), ACTION_SERVER_VERSION
    ):
        from sema4ai_http import download_with_resume  # type: ignore

        relative_path = get_release_artifact_relative_path(sys.platform, "action-server")

        base_url = "https://cdn.sema4.ai/action-server/releases"
        url = f"{base_url}/{ACTION_SERVER_VERSION}/{relative_path}"
        download_with_resume(url, path)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture(scope="session")
def action_server() -> Path:
    path = _get_action_server_path()
    if not verify_action_server_downloaded_ok(str(path), ACTION_SERVER_VERSION):
        raise Exception(f"Action server {path} is not OK!")
    return path


CLI_DIR = Path(__file__).parent.parent.parent.parent / "packages" / "golang-agent-cli"


def _get_agent_cli_relative_path() -> str:
    import sys

    if sys.platform == "win32":
        return "build/agent-cli.exe"
    else:
        return "build/agent-cli"


def _get_agent_cli_path() -> Path:
    import os

    assert os.path.exists(CLI_DIR), f"Expected cli directory to exist, but it does not: {CLI_DIR}"

    path = _get_agent_cli_relative_path()

    target = (CLI_DIR / path).absolute()

    return target


@pytest.fixture(scope="session")
def agent_cli() -> Path:
    import os

    p = _get_agent_cli_path()
    assert os.path.exists(p), f"Expected agent-cli to exist: {p}"
    return p


def _build_agent_cli():
    path = _get_agent_cli_relative_path()
    cmd = ["go", "build", "-o", path]

    if DEBUG_GO:
        cmd.append("-gcflags=all=-N -l")

    contents = run(cmd, cwd=CLI_DIR)
    if contents.returncode != 0:
        raise Exception(
            f"Failed to build agent-cli. stdout:\n{contents.stdout}\nstderr:\n{contents.stderr}"
        )


def pytest_configure(config):
    """
    This is run when pytest is setting up in the controller process
    and in the workers too.

    We use the hook to run things that should only run once,
    like downloading the action server.
    """
    import threading

    if hasattr(config, "workerinput"):
        # prevent workers to run the same code
        return

    # Download the action server in a thread
    # (as it's IO/network bound) so we can build the cli in parallel
    t = threading.Thread(target=_download_action_server_if_needed)
    t.start()
    _build_agent_cli()
    t.join()
