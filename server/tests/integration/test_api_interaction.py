import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def agent_server_data_dir(tmpdir):
    return Path(tmpdir) / "agent_server_data"


def get_free_port() -> int:
    """Get a free port from the OS."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))  # Bind to port 0 lets OS choose a free port
        s.listen(1)
        port = s.getsockname()[1]
        return port


@pytest.fixture
def start_agent_server(logs_dir, agent_server_data_dir):
    from contextlib import contextmanager

    @contextmanager
    def start(parent_pid: int = 0, port: int = 0, kill_lock_holder: bool = True):
        from agent_platform.orchestrator.bootstrap_agent_server import AgentServerProcess

        additional_args = [
            "--use-data-dir-lock",
        ]

        if kill_lock_holder:
            additional_args.append("--kill-lock-holder")

        if parent_pid:
            additional_args.append(f"--parent-pid={parent_pid}")

        if port:
            additional_args.append(f"--port={port}")

        agent_server_data_dir.mkdir(parents=True, exist_ok=True)
        agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)
        agent_server_process.start(logs_dir=logs_dir, additional_args=additional_args)
        try:
            yield agent_server_process
        finally:
            agent_server_process.stop()

    return start


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_agent_server_port_reuse(start_agent_server, logs_dir):
    import threading

    connected_once = threading.Event()
    finished = threading.Event()

    def my_func():
        import socket

        while not finished.is_set():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("127.0.0.1", port))
                connected_once.set()
                s.recv(1024)
            except Exception:
                import traceback

                traceback.print_exc()

    try:
        port = get_free_port()
        with start_agent_server(port=port, kill_lock_holder=False) as agent_server_process:
            assert agent_server_process.process.is_alive()
            thread = threading.Thread(target=my_func)
            thread.start()

            if not connected_once.wait(timeout=10):
                raise AssertionError("Agent server did not connect to the port")

        with start_agent_server(port=port, kill_lock_holder=False) as agent_server_process:
            assert agent_server_process.process.is_alive()
    finally:
        finished.set()


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_start_agent_server_with_lock_file(  # noqa: C901
    agent_server_data_dir, start_agent_server
) -> None:
    import json

    from sema4ai.common.process import Process, is_process_alive
    from sema4ai.common.wait_for import (
        wait_for_condition,
        wait_for_expected_func_return,
    )

    with start_agent_server() as agent_server_process:
        assert agent_server_process.process.is_alive()

        pid_file = agent_server_data_dir / "agent-server.pid"

        def pid_file_exists_and_is_json_valid():
            if not pid_file.exists():
                return "pid file does not exist"
            try:
                pid_file_content = pid_file.read_text()
            except Exception:
                return "pid file is not readable"

            if not pid_file_content:
                return "pid file is empty"
            try:
                json.loads(pid_file_content)
            except Exception:
                return f"pid file is not valid json. Content: {pid_file_content!r}"
            return "ok"

        wait_for_expected_func_return(pid_file_exists_and_is_json_valid, "ok")
        initial_pid = json.loads(pid_file.read_text())["pid"]

        with start_agent_server() as agent_server_process2:
            # Previous one must exit before the new one can start
            wait_for_condition(lambda: not agent_server_process.process.is_alive())

            def pid_file_contains_new_pid():
                try:
                    pid_file_content = pid_file.read_text()
                except Exception:
                    return "pid file is not readable"
                if not pid_file_content:
                    return "pid file is empty"
                try:
                    data = json.loads(pid_file_content)
                except Exception:
                    return f"pid file is not valid json. Content: {pid_file_content!r}"

                if initial_pid != data["pid"]:
                    return "ok"
                return f"pid was kept the same ({initial_pid})"

            # When using the python from uv, it does a double-launch
            # i.e.: .venv\Scripts\python.exe ends up calling
            # <user>\Roaming\uv\python\cpython-3.11.11-windows-x86_64-none\python.exe
            # which is a different process than the one we want to test against
            # (this means we can't use `pid` directly,
            # so, we just check that the pid is different).
            wait_for_expected_func_return(pid_file_contains_new_pid, "ok")

            data = json.loads(pid_file.read_text())
            assert data["lock_file"]
            assert data["port"] == agent_server_process2.port
            assert data["base_url"]
            assert agent_server_process2.process.is_alive()

    # Ok, now, test --parent-pid

    # Simulate the parent process id.
    process = Process([sys.executable, "-c", "import time; time.sleep(10000)"])
    process.start()

    try:
        with start_agent_server(parent_pid=process.pid) as agent_server_process:
            assert agent_server_process.process.is_alive()
            process.stop()
            wait_for_condition(lambda: not is_process_alive(process.pid))

            try:
                wait_for_condition(lambda: not agent_server_process.process.is_alive(), timeout=20)
            except Exception as e:
                raise AssertionError(
                    f"Agent server process {agent_server_process.process.pid} did not "
                    f"exit after parent process {process.pid} exited."
                ) from e
    finally:
        process.stop()


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_api_interaction_with_action_server(
    base_url_agent_server,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    from agent_platform.orchestrator.agent_server_client import (
        ActionPackage,
        AgentServerClient,
        SecretKey,
    )

    cwd = resources_dir / "simple_action_package"
    api_key = "test"
    action_server_process.start(
        cwd=cwd,
        actions_sync=True,
        min_processes=1,
        max_processes=1,
        reuse_processes=True,
        lint=True,
        timeout=500,  # Can be slow (time to bootstrap env)
        additional_args=["--api-key", api_key],
        logs_dir=logs_dir,
    )
    url = f"http://{action_server_process.host}:{action_server_process.port}"

    with AgentServerClient(base_url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            # openai_api_key,
            action_packages=[
                ActionPackage(
                    name="ActionPackage",
                    organization="Organization",
                    version="0.0.1",
                    url=url,
                    api_key=SecretKey(value=api_key),
                    whitelist="",
                    allowed_actions=[],
                )
            ],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                },
            ],
        )

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
        result = agent_client.send_message_to_agent_thread(
            agent_id, thread_id, "Which tools/actions can you call?"
        ).lower()
        if "list" not in result or "contact" not in result:
            raise AssertionError(
                "Agent did not provide that it has the list contact action. "
                f"Found result: {result!r}"
            )
        result = agent_client.send_message_to_agent_thread(
            agent_id, thread_id, "Please list all contacts"
        ).lower()
        if "john doe" not in result and "jane doe" not in result:
            raise AssertionError(
                f"Agent did not find contacts: 'john doe' or 'jane doe'. Found result: {result!r}"
            )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_agent_server_port_conflict(tmpdir, logs_dir):  # noqa: C901 PLR0915
    """Test that trying to start a server on a port that's already in use
    fails with the expected error message.
    """
    import time
    from contextlib import contextmanager

    from agent_platform.orchestrator.agent_server_client import print_info
    from agent_platform.orchestrator.bootstrap_agent_server import AgentServerProcess

    from sema4ai.common.wait_for import wait_for_condition

    # Create a directory for agent server data
    agent_server_data_dir = Path(tmpdir) / "agent_server_data"
    agent_server_data_dir.mkdir(parents=True, exist_ok=True)

    # Get a specific port to use for both server attempts
    specific_port = get_free_port()

    # Helper to start a server with a specific port
    @contextmanager
    def start_server_with_port(
        port: int, should_succeed: bool = True
    ) -> Iterator[tuple[AgentServerProcess, Path | None]]:
        agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)
        # When starting the second server, we expect it to fail, so we need to capture
        # the logs or error output
        if should_succeed:
            agent_server_process.start(logs_dir=logs_dir, port=port)
            try:
                yield agent_server_process, None
            finally:
                agent_server_process.stop()
        else:
            # For the failing case, we want to capture the error message
            # Create a specific logs directory for the second server
            second_server_logs_dir = Path(logs_dir) / "second_server"
            second_server_logs_dir.mkdir(exist_ok=True)

            # The second server is expected to fail, so we need to catch the exception
            yielded_already = False
            try:
                # Start the server - this should raise an exception when it fails
                # to bind.
                # Pass the same port to create the conflict
                agent_server_process.start(
                    logs_dir=second_server_logs_dir,
                    port=port,  # Pass port here to create the conflict
                )
                # If we get here, the server somehow started successfully, which
                # is unexpected but we'll still yield it properly
                try:
                    yielded_already = True
                    yield (
                        agent_server_process,
                        second_server_logs_dir / "agent-server.log",
                    )
                finally:
                    agent_server_process.stop()
            except Exception as e:
                if not yielded_already:
                    # This is expected - the server should fail to start
                    print_info(f"Second server failed to start as expected: {e}")
                    # Prepare the error log path where we expect error messages
                    # to be written
                    error_log_path = second_server_logs_dir / "agent-server.log"
                    # Yield even though it failed
                    try:
                        yield agent_server_process, error_log_path
                    finally:
                        # Try to stop it (probably not necessary but just to be safe)
                        try:
                            agent_server_process.stop()
                        except Exception:
                            pass
                else:
                    raise e

    # First, start a server on the specific port
    with start_server_with_port(specific_port) as (first_server, _):
        # Wait for the server to be fully started
        def server_is_running():
            return first_server.process.is_alive()

        wait_for_condition(server_is_running, timeout=10)
        assert first_server.process.is_alive(), "First server should be running"

        # Now try to start a second server on the same port
        with start_server_with_port(specific_port, should_succeed=False) as result:
            second_server, error_log_path = result
            assert error_log_path is not None, "Error log path should not be None"

            # Wait a bit for the error to be logged
            time.sleep(2)

            # The second server should fail to start
            assert not second_server.process.is_alive(), "Second server should not be running"

            # Check the error message
            error_log_content = ""
            if error_log_path.exists():
                error_log_content = error_log_path.read_text()
            else:
                # Try to find any log files in the directory
                # Make sure we have the logs directory reference even if the start()
                # method raised an exception
                second_server_logs_dir = Path(logs_dir) / "second_server"
                log_files = list(second_server_logs_dir.glob("*.log"))
                if log_files:
                    # Use the most recently modified log file
                    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
                    error_log_content = latest_log.read_text()

            # Wait a bit longer and try again if no content found
            if not error_log_content:
                time.sleep(3)
                # Make sure we have the logs directory reference even if the start()
                # method raised an exception
                second_server_logs_dir = Path(logs_dir) / "second_server"
                log_files = list(second_server_logs_dir.glob("*.log"))
                if log_files:
                    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
                    error_log_content = latest_log.read_text()

            # Look for the expected error message
            import re

            assert any(
                re.search(r"Failed to bind socket", line) for line in error_log_content.splitlines()
            ), (
                "Error log should contain 'Failed to bind socket' in one of its lines, "
                f"but was:\n{error_log_content}"
            )

            # Also check for port-in-use related messages
            port_error_patterns = [
                r"Address already in use",  # Unix message
                r"Failed to bind socket:",  # Generic bind failure message
            ]
            found_port_error = any(
                any(re.search(pattern, line) for line in error_log_content.splitlines())
                for pattern in port_error_patterns
            )
            assert found_port_error, (
                "Error log should contain port conflict message in one of its lines, "
                f"but was:\n{error_log_content}"
            )

            # Verify the error message about not being able to continue
            assert any(
                re.search(r"Cannot continue without binding to a socket. Exiting.", line)
                for line in error_log_content.splitlines()
            ), (
                "Error log should contain 'Cannot continue without binding to a socket."
                f" Exiting.' in one of its lines, but was:\n{error_log_content}"
            )


if __name__ == "__main__":
    import pytest

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(pytest.main([]))
