import os
import sys
import traceback
from typing import Callable

import pytest
from dotenv import load_dotenv

load_dotenv()


def test_start_agent_server_with_lock_file(tmpdir, logs_dir):
    import json
    from contextlib import contextmanager
    from pathlib import Path

    from agent_server_orchestrator.bootstrap_agent_server import AgentServerProcess
    from sema4ai.common.process import Process
    from sema4ai.common.wait_for import wait_for_condition

    agent_server_data_dir = Path(tmpdir) / "agent_server_data"

    @contextmanager
    def start(parent_pid: int = 0):
        class CustomAgentServerProcess(AgentServerProcess):
            def get_base_args(self) -> list[str]:
                return super().get_base_args() + [
                    "--use-data-dir-lock",
                    "--kill-lock-holder",
                    "--parent-pid",
                    str(parent_pid),
                ]

        agent_server_data_dir.mkdir(parents=True, exist_ok=True)
        agent_server_process = CustomAgentServerProcess(datadir=agent_server_data_dir)
        agent_server_process.start(logs_dir=logs_dir)
        try:
            yield agent_server_process
        finally:
            agent_server_process.stop()

    from sema4ai.common.process import is_process_alive

    with start() as agent_server_process:
        assert agent_server_process.process.is_alive()

        def pid_file_exists():
            pid_file = agent_server_data_dir / "agent-server.pid"
            return pid_file.exists()

        wait_for_condition(pid_file_exists)
        with start() as agent_server_process2:
            # Previous one must exit before the new one can start
            wait_for_condition(lambda: not agent_server_process.process.is_alive())
            pid_file = agent_server_data_dir / "agent-server.pid"
            data = json.loads(pid_file.read_text())
            assert data["pid"] == agent_server_process2.process.pid
            assert data["lock_file"]
            assert data["port"] == agent_server_process2.port
            assert data["base_url"]
            assert agent_server_process2.process.is_alive()

    # Ok, now, test --parent-pid

    # Simulate the parent process id.
    process = Process(["python", "-c", "import time; time.sleep(10000)"])
    process.start()

    try:
        with start(parent_pid=process.pid) as agent_server_process:
            assert agent_server_process.process.is_alive()
            process.stop()
            wait_for_condition(lambda: not is_process_alive(process.pid))

            try:
                wait_for_condition(
                    lambda: not agent_server_process.process.is_alive(), timeout=20
                )
            except Exception:
                raise AssertionError(
                    f"Agent server process {agent_server_process.process.pid} did not exit after parent process {process.pid} exited."
                )
    finally:
        process.stop()


def test_api_interaction_with_action_server(
    base_url_agent_server,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    from agent_server_orchestrator.agent_server_client import (
        ActionPackageDataClass,
        AgentServerClient,
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
            openai_api_key,
            action_packages=[
                ActionPackageDataClass(
                    name="ActionPackage",
                    organization="Organization",
                    version="0.0.1",
                    url=url,
                    api_key=api_key,
                    whitelist="",
                )
            ],
        )

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
        result = agent_client.send_message_to_agent_thread(
            thread_id, "Which tools/actions can you call?"
        ).lower()
        if "list" not in result or "contact" not in result:
            raise AssertionError(
                "Agent did not provide that it has the list contact action. Found result: "
                f"{result!r}"
            )
        result = agent_client.send_message_to_agent_thread(
            thread_id, "Please list all contacts"
        ).lower()
        if "john doe" not in result and "jane doe" not in result:
            raise AssertionError(
                "Agent did not find contacts: 'john doe' or 'jane doe'. Found result: "
                f"{result!r}"
            )


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
            mode="w+", delete=False, suffix=".txt", dir=str(tmpdir)
        )
        temp_file.write(content)
        temp_file.close()
        return temp_file.name, key, value

    return _do_create


def test_api_interaction(
    base_url_agent_server: str,
    openai_api_key: str,
    create_sample_file: Callable[[], tuple[str, str, str]],
):
    import random

    from agent_server_orchestrator.agent_server_client import (
        AgentServerClient,
        print_header,
        print_info,
        print_success,
    )

    uploaded_agent_files: list[str] = []
    uploaded_thread_files: list[str] = []
    try:
        with AgentServerClient(base_url_agent_server) as agent_client:

            def make_file_uploads(
                thread_id: str, agent_id: str
            ) -> tuple[list[str], list[str], list[tuple[str, str]]]:
                print_header("TESTING FILE UPLOADS")

                # Thread file upload
                thread_file, thread_key, thread_value = create_sample_file()
                thread_response = agent_client.upload_file_to_thread(
                    thread_id, thread_file, embedded=True
                )
                assert thread_response.status_code == 200, (
                    f"File upload to thread: bad response: {thread_response.status_code} {thread_response.text}"
                )

                # Agent file upload
                agent_file, agent_key, agent_value = create_sample_file()
                agent_response = agent_client.upload_file_to_agent(agent_id, agent_file)
                assert agent_response.status_code == 200, (
                    f"File upload to agent: bad response: {agent_response.status_code} {agent_response.text}"
                )

                # Multiple file uploads
                multi_files = [create_sample_file()[0] for _ in range(4)]
                agent_files, thread_files = multi_files[:2], multi_files[2:]
                thread_multi_response = agent_client.upload_files_to_thread(
                    thread_id, thread_files
                )
                assert thread_multi_response.status_code == 200, (
                    f"Multiple file upload to thread: bad response: {thread_multi_response.status_code} {thread_multi_response.text}"
                )

                agent_multi_response = agent_client.upload_files_to_agent(
                    agent_id, agent_files
                )

                assert agent_multi_response.status_code == 200, (
                    f"Multiple file upload to agent: bad response: {agent_multi_response.status_code} {agent_multi_response.text}"
                )

                total_files = (
                    1 + 1 + 2 + 2
                )  # 1 thread, 1 agent, 2 multi-thread, 2 multi-agent
                print_success(f"Successfully uploaded {total_files} files")

                return (
                    [agent_file] + agent_files,
                    [thread_file] + thread_files,
                    [
                        (thread_key, thread_value),
                        (agent_key, agent_value),
                    ],
                )

            def make_async_run(thread_id: str) -> None:
                import time

                print_header("TESTING ASYNCHRONOUS RUN")
                async_message = "What's the weather like today?"
                print_info(f"Creating async run with message: {async_message}")
                async_run_response = agent_client.create_async_run(
                    thread_id, async_message
                )
                assert "run_id" in async_run_response, (
                    f"Async run ID not received in response: {async_run_response!r}"
                )

                run_id = async_run_response["run_id"]
                print_success(f"Async run created with ID: {run_id}")

                print_info("Polling for run completion")

                timeout_at = time.time() + 15
                while True:
                    status_response = agent_client.get_run_status(run_id)
                    if status_response is None:
                        raise Exception("async poll failure (status response is None)")

                    if status_response and status_response["status"] == "complete":
                        break
                    if time.time() > timeout_at:
                        raise Exception(
                            f"Run did not complete in time. Status: {status_response!r}"
                        )
                    time.sleep(0.25)

                print_success("Run completed successfully")

                thread_state = agent_client.get_thread_state(thread_id)

                if not thread_state["last_ai_message"]:
                    raise AssertionError(
                        "No AI message found in the thread state after async run. Received thread state: "
                        f"{thread_state!r}"
                    )
                print_success("Received AI message after async run")

            agent_id = agent_client.create_agent_and_return_agent_id(openai_api_key)

            thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
            agent_client.send_message_to_agent_thread(thread_id)
            make_async_run(thread_id)
            uploaded_agent_files, uploaded_thread_files, key_value_pairs = (
                make_file_uploads(thread_id, agent_id)
            )

            # ---------------------- check file retrieval ----------------------
            print_header("TESTING FILE RETRIEVAL")
            if not uploaded_thread_files:
                raise Exception("No files available to test file retrieval")

            def try_retrieve_file_info() -> tuple[bool, str | None]:
                """Try to retrieve file info and return success status and error message."""
                try:
                    file_ref = os.path.basename(uploaded_thread_files[0])
                    print_info(f"Retrieving file info for: {file_ref}")
                    file_info = agent_client.get_file_info_by_ref(thread_id, file_ref)
                    assert file_info is not None, "File information retrieval failed"
                    assert file_ref in file_info["file_url"], (
                        f"Retrieved file_ref does not match the requested one. Expected: {file_ref}, Got URL: {file_info['file_url']}"
                    )
                    print_success(
                        f"Successfully retrieved file information for {file_ref}"
                    )
                    return True, None
                except AssertionError as e:
                    return False, str(e)

            # First attempt
            success, error_msg = try_retrieve_file_info()

            # Retry once if first attempt failed
            if not success:
                print_info(
                    f"First file retrieval attempt failed: {error_msg}. Retrying once..."
                )
                success, error_msg = try_retrieve_file_info()

                # If retry also failed, raise the assertion error
                if not success:
                    raise AssertionError(
                        f"File information retrieval failed after retry: {error_msg}"
                    )

            # ---------------------- check information retrieval ----------------------
            print_header("TESTING INFORMATION RETRIEVAL")
            if not key_value_pairs:
                raise AssertionError(
                    "No key-value pairs available for testing retrieval"
                )

            def try_retrieve_value() -> tuple[bool, str | None]:
                """Try to retrieve a value from the agent and return success status and error message."""
                try:
                    chosen_pair = random.choice(key_value_pairs)
                    key, expected = chosen_pair
                    question = f"What is the value associated with the key '{key}'?"
                    print_info(f"Asking question: {question}")
                    response = agent_client.send_message_to_agent_thread(
                        thread_id, question
                    )
                    assert expected in response, (
                        f"Expected value '{expected}' not found in the response: {response}"
                    )
                    print_success(f"Successfully retrieved value for key '{key}'")
                    return True, None
                except AssertionError as e:
                    return False, str(e)

            # First attempt
            success, error_msg = try_retrieve_value()

            # Retry once if first attempt failed
            if not success:
                print_info(f"First attempt failed: {error_msg}. Retrying once...")
                success, error_msg = try_retrieve_value()

                # If retry also failed, raise the assertion error
                if not success:
                    raise AssertionError(
                        f"Information retrieval failed after retry: {error_msg}"
                    )
    finally:
        # Clean up files
        for file_path in uploaded_agent_files + uploaded_thread_files:
            try:
                os.unlink(file_path)
            except Exception:
                traceback.print_exc()


def test_agent_server_port_conflict(tmpdir, logs_dir):
    """Test that trying to start a server on a port that's already in use
    fails with the expected error message.
    """
    import socket
    import time
    from contextlib import contextmanager
    from pathlib import Path

    from agent_server_orchestrator.agent_server_client import print_info
    from agent_server_orchestrator.bootstrap_agent_server import AgentServerProcess
    from sema4ai.common.wait_for import wait_for_condition

    def is_port_in_use(port: int) -> bool:
        """Check if a port is already in use without binding to it."""
        try:
            import psutil

            for conn in psutil.net_connections():
                try:
                    if conn.laddr.port == port:
                        return True
                except (PermissionError, OSError):
                    continue
        except Exception:
            pass
        return False

    def get_free_port() -> int:
        """Get a free port from the OS."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))  # Bind to port 0 lets OS choose a free port
            s.listen(1)
            port = s.getsockname()[1]
            # Double check the port is actually free using psutil
            if is_port_in_use(port):
                # If port is in use, try again
                return get_free_port()
            return port

    # Create a directory for agent server data
    agent_server_data_dir = Path(tmpdir) / "agent_server_data"
    agent_server_data_dir.mkdir(parents=True, exist_ok=True)

    # Get a specific port to use for both server attempts
    specific_port = get_free_port()

    # Helper to start a server with a specific port
    @contextmanager
    def start_server_with_port(port: int, should_succeed: bool = True):
        agent_server_process = AgentServerProcess(datadir=agent_server_data_dir)
        # When starting the second server, we expect it to fail, so we need to capture
        # the logs or error output
        if should_succeed:
            agent_server_process.start(logs_dir=logs_dir, port=port)
            try:
                yield agent_server_process
            finally:
                agent_server_process.stop()
        else:
            # For the failing case, we want to capture the error message
            # Create a specific logs directory for the second server
            second_server_logs_dir = Path(logs_dir) / "second_server"
            second_server_logs_dir.mkdir(exist_ok=True)

            # The second server is expected to fail, so we need to catch the exception
            try:
                # Start the server - this should raise an exception when it fails to bind
                # Pass the same port to create the conflict
                agent_server_process.start(
                    logs_dir=second_server_logs_dir,
                    port=port,  # Pass port here to create the conflict
                )
                # If we get here, the server somehow started successfully, which is unexpected
                # but we'll still yield it properly
                try:
                    yield (
                        agent_server_process,
                        second_server_logs_dir / "agent-server.log",
                    )
                finally:
                    agent_server_process.stop()
            except Exception as e:
                # This is expected - the server should fail to start
                print_info(f"Second server failed to start as expected: {e}")
                # Prepare the error log path where we expect error messages to be written
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

    # First, start a server on the specific port
    with start_server_with_port(specific_port) as first_server:
        # Wait for the server to be fully started
        def server_is_running():
            return first_server.process.is_alive()

        wait_for_condition(server_is_running, timeout=10)
        assert first_server.process.is_alive(), "First server should be running"

        # Now try to start a second server on the same port
        with start_server_with_port(specific_port, should_succeed=False) as result:
            second_server, error_log_path = result

            # Wait a bit for the error to be logged
            time.sleep(2)

            # The second server should fail to start
            assert not second_server.process.is_alive(), (
                "Second server should not be running"
            )

            # Check the error message
            error_log_content = ""
            if error_log_path.exists():
                error_log_content = error_log_path.read_text()
            else:
                # Try to find any log files in the directory
                # Make sure we have the logs directory reference even if the start() method raised an exception
                second_server_logs_dir = Path(logs_dir) / "second_server"
                log_files = list(second_server_logs_dir.glob("*.log"))
                if log_files:
                    # Use the most recently modified log file
                    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
                    error_log_content = latest_log.read_text()

            # Wait a bit longer and try again if no content found
            if not error_log_content:
                time.sleep(3)
                # Make sure we have the logs directory reference even if the start() method raised an exception
                second_server_logs_dir = Path(logs_dir) / "second_server"
                log_files = list(second_server_logs_dir.glob("*.log"))
                if log_files:
                    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
                    error_log_content = latest_log.read_text()

            # Look for the expected error message
            import platform
            import re

            # Error message patterns are different between Windows and non-Windows
            is_windows = platform.system() == "Windows"

            if is_windows:
                # On Windows, we only expect the specific port failure message
                assert any(
                    re.search(rf"Port {specific_port} is already in use", line)
                    for line in error_log_content.splitlines()
                ), (
                    f"Error log should contain 'Port {specific_port} is already in use' in one of its lines, but was:\n{error_log_content}"
                )
            else:
                # On non-Windows, check for socket binding failure
                assert any(
                    re.search(r"Failed to bind socket", line)
                    for line in error_log_content.splitlines()
                ), (
                    f"Error log should contain 'Failed to bind socket' in one of its lines, but was:\n{error_log_content}"
                )

                # Also check for port-in-use related messages
                port_error_patterns = [
                    r"Address already in use",  # Unix message
                    r"Failed to bind socket:",  # Generic bind failure message
                ]
                found_port_error = any(
                    any(
                        re.search(pattern, line)
                        for line in error_log_content.splitlines()
                    )
                    for pattern in port_error_patterns
                )
                assert found_port_error, (
                    f"Error log should contain port conflict message in one of its lines, but was:\n{error_log_content}"
                )

                # Verify the error message about not being able to continue
                assert any(
                    re.search(
                        r"Cannot continue without binding to a socket. Exiting.", line
                    )
                    for line in error_log_content.splitlines()
                ), (
                    f"Error log should contain 'Cannot continue without binding to a socket. Exiting.' in one of its lines, but was:\n{error_log_content}"
                )


if __name__ == "__main__":
    import pytest

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(pytest.main([]))
