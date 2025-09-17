import os
import sys
import time
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
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

        loop_exception = None

        while not finished.is_set():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("127.0.0.1", port))
                connected_once.set()
                s.recv(1024)
            except Exception as exc:
                loop_exception = exc
                time.sleep(1 / 20)

        if loop_exception and not connected_once.is_set():
            import traceback

            traceback.print_exception(loop_exception)

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
    base_url_agent_server_with_data_frames,
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

    with AgentServerClient(base_url_agent_server_with_data_frames) as agent_client:
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
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
        result, _ = agent_client.send_message_to_agent_thread(
            agent_id, thread_id, "Which tools/actions can you call?"
        )

        result = result.lower()

        if "contact" not in result or ("retrieve" not in result and "list" not in result):
            raise AssertionError(
                "Agent did not provide that it has the list contact action. "
                f"Found result: {result!r}"
            )

        result, _ = agent_client.send_message_to_agent_thread(
            agent_id, thread_id, "Please list all contacts"
        )
        result = result.lower().replace("\xa0", " ")

        if "john doe" not in result and "jane doe" not in result:
            raise AssertionError(
                f"Agent did not find contacts: 'john doe' or 'jane doe'. Found result: {result!r}"
            )

        _, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id, thread_id, "Please call my_named_query"
        )
        found = False
        for tool_call in tool_calls:
            if "Data frame data_frame_my_named_query created from my_named_query" in str(tool_call):
                found = True
                break
        assert found, (
            f"'Data frame data_frame_my_named_query created from my_named_query' not found in "
            f"tool calls. Tool calls found: {tool_calls}"
            "This means that a data frame was not automatically created when my_named_query"
            " was called (or it wasn't called at all)."
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


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_async_action_polling_with_fast_retry_interval(
    base_url_agent_server_with_async_actions,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    """
    Integration test for async action polling with fast retry intervals.

    This test:
    1. Sets the retry interval environment variable to 0.1 seconds
    2. Calls the test_sleep_action that takes 0.5 seconds to complete
    3. Tests happy path where the action eventually succeeds after multiple fast polling attempts

    This verifies that async polling mechanism works correctly with configurable retry intervals.
    Note: This is an end-to-end test that includes LLM processing time, so timing assertions
    are focused on successful completion rather than precise timing measurements.
    """
    from agent_platform.orchestrator.agent_server_client import (
        ActionPackage,
        AgentServerClient,
        SecretKey,
    )

    assert os.getenv("SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION") == "true", (
        "Async actions must be enabled"
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

    with AgentServerClient(base_url_agent_server_with_async_actions) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[
                ActionPackage(
                    name="ActionPackage",
                    organization="Organization",
                    version="0.0.1",
                    url=url,
                    api_key=SecretKey(value=api_key),
                    whitelist="",
                    allowed_actions=["sleep_action"],  # Only allow our test action
                )
            ],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # First, verify the agent has access to the sleep action
        result, _ = agent_client.send_message_to_agent_thread(
            agent_id, thread_id, "What actions can you call? List them."
        )

        result = result.lower()

        if "sleep" not in result:
            raise AssertionError(
                f"Agent did not report having access to test_sleep_action. Found result: {result!r}"
            )

        # Record the start time
        start_time = time.time()

        # Call the sleep action with a duration that will require multiple polling attempts
        # We'll use 0.5 seconds, which with 0.1 second intervals should result
        # in ~5 polling attempts.

        result, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id, thread_id, "Please call the sleep_action with duration_seconds=0.5"
        )

        tool_call = tool_calls[0] if tool_calls else None
        assert tool_call is not None, "No tool calls returned."
        assert tool_call.tool_name == "sleep_action", (
            f"Expected sleep action but got: {tool_call.tool_name}"
        )
        assert "result" in tool_call.result
        assert "error" in tool_call.result
        assert tool_call.result["result"] == "Action completed after sleeping for 0.5 seconds"
        assert tool_call.result["error"] is None
        assert tool_call.input_data.get("duration_seconds") == 0.5, "Expected duration 0.5"

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Verify the timing - this is an end-to-end test that includes LLM processing time,
        # so we need to account for the full latency including:
        # - LLM processing the request and deciding to call the action (1-3 seconds)
        # - The 0.5 second sleep action itself
        # - Agent/action server communication overhead
        # The main goal is to verify the action completes successfully, not strict timing
        if elapsed_time < 0.4:
            raise AssertionError(
                f"Action completed too quickly ({elapsed_time:.2f}s). "
                f"Expected at least 0.4 seconds for a 0.5s sleep action."
            )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_async_action_error_handling(
    base_url_agent_server_with_async_actions,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    """
    Integration test for async action error handling.

    This test:
    1. Calls the test_sleep_then_error_action that sleeps for 3 seconds then raises an ActionError
    2. Forces the action into async mode due to the sleep duration
    3. Tests that the error is properly propagated through the async polling flow
    4. Verifies that our enhanced error handling works correctly in async mode

    This verifies that async error handling works correctly.
    """
    from agent_platform.orchestrator.agent_server_client import (
        ActionPackage,
        AgentServerClient,
        SecretKey,
    )

    assert os.getenv("SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION") == "true", (
        "Async actions must be enabled"
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

    with AgentServerClient(base_url_agent_server_with_async_actions) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[
                ActionPackage(
                    name="ActionPackage",
                    organization="Organization",
                    version="0.0.1",
                    url=url,
                    api_key=SecretKey(value=api_key),
                    whitelist="",
                    allowed_actions=["sleep_then_error_action"],  # Only allow our slow error action
                )
            ],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Record the start time
        start_time = time.time()

        # Call the slow error action
        result, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            "Please call the sleep_then_error_action with sleep_seconds=3.0",
        )

        tool_call = tool_calls[0] if tool_calls else None
        assert tool_call is not None, "No tool calls returned."
        assert tool_call.tool_name == "sleep_then_error_action", (
            f"Expected slow error action but got: {tool_call.tool_name}"
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Verify the tool call result shows proper error handling
        # The tool call should have error information from our enhanced error handling
        tool_result = tool_call.result
        if not tool_result:
            raise AssertionError(f"Tool result is empty. Tool call: {tool_call}")

        # Check if the tool result contains error information
        # Should have error field from our _handle_status_check function
        assert "error" in tool_result, f"Tool result should contain error field. Got: {tool_result}"

        error_message = tool_result.get("error", "")
        assert error_message, "Error field should not be empty"
        assert "error after sleeping for 3" in error_message, (
            f"Error message should contain the sleep duration error message. Got: {error_message}"
        )

        # Verify reasonable timing - should take at least 3 seconds (sleep time) but not too long
        if elapsed_time < 2.5:  # Should take at least close to 3 seconds
            raise AssertionError(
                f"Error action completed too quickly ({elapsed_time:.2f}s). "
                f"Expected at least ~3 seconds due to sleep."
            )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
async def test_agent_details_endpoint(
    base_url_agent_server,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    """Integration test for the agent-details endpoint.
    Tests that we can get agent details including action package status."""
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
        # Create an agent with two action packages
        action_packages = [
            ActionPackage(
                name=f"test_package_{i}",
                organization="test_org",
                version="1.0.0",
                url=url
                if i == 0
                else "http://non-existent-url:12345",  # Second package has invalid URL
                api_key=SecretKey(value=api_key),
                whitelist="",
                allowed_actions=[],
            )
            for i in range(2)
        ]

        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=action_packages,
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )

        # Get agent details using the client method
        agent_details = agent_client.get_agent_details(agent_id)
        assert "runbook" in agent_details, "Agent details should include runbook"
        assert "action_packages" in agent_details, "Agent details should include action packages"

        # First URL has valid server, second URL fails,
        # so we should get 1 online package + 1 offline package
        online_packages = [
            pkg for pkg in agent_details["action_packages"] if pkg["status"] == "online"
        ]
        offline_packages = [
            pkg for pkg in agent_details["action_packages"] if pkg["status"] == "offline"
        ]

        assert len(online_packages) == 1, "Should have one online package from valid URL"
        assert len(offline_packages) == 1, "Should have one offline package from invalid URL"

        # The online package should be the actual server package name
        online_package = online_packages[0]
        assert online_package["name"] == "Simpleactionpackage"
        assert online_package["version"] == "1.0.0"
        assert online_package["status"] == "online"
        assert len(online_package["actions"]) > 0, "Online package should have actions"

        # The offline package should use the agent package name (since server call failed)
        offline_package = offline_packages[0]
        assert offline_package["name"] == "test_package_1"  # Agent package name for failed requests
        assert offline_package["version"] == "1.0.0"
        assert offline_package["status"] == "offline"
        assert len(offline_package["actions"]) == 0, "Offline package should have no actions"


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
async def test_create_agent_from_package_with_knowledge_file(
    base_url_agent_server,
    openai_api_key,
):
    """
    Test that an agent with knowledge files is created successfully.
    Knowledge files are not supported in Agent Server v2;
    this test is here to make sure that an agent package with knowledge files
    does not affect agent creation and interaction in v2.
    """
    import base64

    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    test_agents_dir = Path(__file__).parent / "resources" / "test-agents"

    test_package_path = test_agents_dir / "agent-package-with-knowledge-file.zip"
    if not test_package_path.exists():
        pytest.skip("agent-package-with-knowledge-file.zip not found")

    package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

    with AgentServerClient(base_url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_from_package_and_return_agent_id(
            name="VS Code One Changed",
            agent_package_base64=package_base64,
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
        response = agent_client.send_message_to_agent_thread(
            agent_id, thread_id, "What is the capital of France? Answer with just the capital."
        )
        assert "Paris" in response[0], "Response should contain Paris"


if __name__ == "__main__":
    import pytest

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(pytest.main([]))
