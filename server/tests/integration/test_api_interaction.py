import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient


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
            if "Data frame my_named_query created from my_named_query" in str(tool_call):
                found = True
                break
        assert found, (
            f"'Data frame my_named_query created from my_named_query' not found in "
            f"tool calls. Tool calls found: {tool_calls}"
            "This means that a data frame was not automatically created when my_named_query"
            " was called (or it wasn't called at all)."
        )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_mcp_calling_with_action_server(
    base_url_agent_server_session,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    from agent_platform.core.mcp.mcp_server import MCPServer

    # Bootstrap the action server
    cwd = resources_dir / "simple_action_package"
    action_server_process.start(
        cwd=cwd,
        actions_sync=True,
        min_processes=1,
        max_processes=1,
        reuse_processes=True,
        lint=True,
        timeout=500,
        logs_dir=logs_dir,
    )

    url = f"http://{action_server_process.host}:{action_server_process.port}"

    with AgentServerClient(base_url_agent_server_session) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            runbook="""
            You are a test agent that must call the tool/action that the user asks for.
            Pay attention to the tool/action name and call it exactly as requested.
            If it fails just return the failure.
            """,
            mcp_servers=[
                MCPServer(
                    url=url + "/mcp",
                    name="ActionServer",
                    headers={"X-some-secret": "my-secret-test"},
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

        _, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            """Please call the add_contact_with_secret with

            name=John Doe
            email=john.doe@example.com
            phone=1234567890

            Call it as fast as possible without doing or requesting anything else.",
            """,
        )
        tool_call = tool_calls[0] if tool_calls else None
        assert tool_call is not None, "No tool calls returned"
        result = tool_call.result
        structured_content = result.get("structuredContent")
        assert structured_content is not None, f"No structured content found in result: {result}"
        assert not result.get("content"), f"Content found in result: {result}"
        assert isinstance(structured_content, dict), (
            f"Structured content is not a dictionary: {structured_content}"
        )
        assert set(structured_content.keys()) == {"error", "result"}, (
            f"Structured content keys are not {'error', 'result'}: {structured_content}"
        )
        assert structured_content["error"] is None, f"Error is not None: {structured_content}"
        assert structured_content["result"] is not None, f"Result is not None: {structured_content}"
        assert structured_content["result"]["message"] == "Added contact with secret my-secret-test"


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_action_error_handling(
    base_url_agent_server,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    """Verify a sync action returns result on success and error on failure."""
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
        timeout=500,
        additional_args=["--api-key", api_key],
        logs_dir=logs_dir,
    )
    url = f"http://{action_server_process.host}:{action_server_process.port}"

    with AgentServerClient(base_url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[
                ActionPackage(
                    name="ActionPackage",
                    organization="Organization",
                    version="0.0.1",
                    url=url,
                    api_key=SecretKey(value=api_key),
                    whitelist="",
                    allowed_actions=[
                        "always_error_action_action_response",
                        "always_error_action_internal_error",
                    ],
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

        # Error case via custom action that always returns an error
        _, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            "Please call the always_error_action with message=Test error",
        )
        tool_call = tool_calls[0] if tool_calls else None
        assert tool_call is not None, "No tool calls returned for error case"
        assert tool_call.tool_name == "always_error_action_action_response"
        assert "result" in tool_call.result
        assert "error" in tool_call.result
        assert tool_call.result["result"] is None
        assert "Test error" in tool_call.result["error"]

        # Error case via custom action that always errors out internally
        _, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            "Please call the always_error_action_internal_error action",
        )
        tool_call = tool_calls[0] if tool_calls else None
        assert tool_call is not None, "No tool calls returned for error case"
        assert tool_call.tool_name == "always_error_action_internal_error"
        assert "error_code" in tool_call.result
        assert "message" in tool_call.result
        assert tool_call.result["error_code"] == "internal-error"
        assert tool_call.result["message"] == "Unexpected error (ValueError)"


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
    base_url_agent_server_sync_and_async_actions_and_sync_mode,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    import functools
    from concurrent.futures.thread import ThreadPoolExecutor
    from textwrap import dedent

    from agent_platform.orchestrator.agent_server_client import (
        ActionPackage,
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

    agent_server_url = base_url_agent_server_sync_and_async_actions_and_sync_mode["url"]
    sync_mode = base_url_agent_server_sync_and_async_actions_and_sync_mode["sync_mode"]

    if sync_mode == "async":
        assert os.getenv("SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION") == "true", (
            "Async actions must be enabled"
        )
    else:
        assert os.getenv("SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION") == "false", (
            "Async actions must NOT be enabled"
        )

    with AgentServerClient(agent_server_url) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            runbook=dedent("""
            You're a test agent which is used to test action/tool error handling.
            The user will ask you to call a tool with some input. Call the tool
            as requested and return the result.
            The tool MUST only be called once. Make sure you call the which matches
            exactly the one requested by the user (there may be more than one tool
            with similar names, you MUST call the one that matches the user request).
            """),
            action_packages=[
                ActionPackage(
                    name="ActionPackage",
                    organization="Organization",
                    version="0.0.1",
                    url=url,
                    api_key=SecretKey(value=api_key),
                    whitelist="",
                    # Only allow our test actions
                    allowed_actions=[
                        "sleep_action",
                        "sleep_then_error_action",
                        "raise_unexpected_action_error",
                        "raise_unexpected_value_error",
                    ],
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

        functions = [
            functools.partial(check_async_action_happy_path, agent_client, agent_id),
            functools.partial(check_async_action_error, agent_client, agent_id),
            functools.partial(check_unexpected_action_error, agent_client, agent_id),
            functools.partial(check_unexpected_value_error, agent_client, agent_id),
        ]

        # for func in functions:
        #     func()
        # return

        # Execute the functions in parallel using regular threading (futures)
        with ThreadPoolExecutor(max_workers=len(functions)) as executor:
            results = [executor.submit(func) for func in functions]

            for future in results:
                future.result()


def check_async_action_happy_path(agent_client: AgentServerClient, agent_id: str):
    """
    Integration test for async action polling with fast retry intervals.

    This test:
    1. Sets the retry interval environment variable to 0.1 seconds
    2. Calls the test_sleep_action that takes 0.5 seconds to complete
    3. Tests happy path where the action eventually succeeds after multiple
       fast polling attempts

    This verifies that async polling mechanism works correctly with configurable retry
    intervals.
    Note: This is an end-to-end test that includes LLM processing time, so timing assertions
    are focused on successful completion rather than precise timing measurements.
    """

    thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

    # Record the start time
    start_time = time.time()

    # Call the sleep action with a duration that will require multiple polling attempts
    # We'll use 0.5 seconds, which with 0.1 second intervals should result
    # in ~5 polling attempts.

    result, tool_calls = agent_client.send_message_to_agent_thread(
        agent_id, thread_id, "Please call the sleep_action with duration_seconds=0.5"
    )

    tool_call = tool_calls[0] if tool_calls else None
    assert tool_call is not None, f"No tool calls returned. Result: {result}"
    assert tool_call.tool_name == "sleep_action", (
        f"Expected sleep action but got: {tool_call.tool_name}"
    )
    assert tool_call.result == {
        "result": "Action completed after sleeping for 0.5 seconds",
        "error": None,
    }
    assert not tool_call.error, f"Tool call should not have an error. Got: {tool_call.error}"
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


def check_async_action_error(agent_client: AgentServerClient, agent_id: str):
    """
    Now, test for async action error handling.

    This test:
    1. Calls the test_sleep_then_error_action that sleeps for 1 seconds then
       raises an ActionError
    2. Forces the action into async mode due to the sleep duration
    3. Tests that the error is properly propagated through the async polling flow
    4. Verifies that our enhanced error handling works correctly in async mode

    This verifies that async error handling works correctly.
    """

    thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

    # Call the slow error action
    result, tool_calls = agent_client.send_message_to_agent_thread(
        agent_id,
        thread_id,
        "Please call the sleep_then_error_action with sleep_seconds=1.0",
    )

    tool_call = tool_calls[0] if tool_calls else None
    assert tool_call is not None, f"No tool calls returned. Result: {result}"
    assert tool_call.tool_name == "sleep_then_error_action", (
        f"Expected slow error action but got: {tool_call.tool_name}"
    )

    assert set(tool_call.result.keys()) == {"result", "error"}
    assert tool_call.error, f"Tool result should contain error field. Got: {tool_call}"

    error_message = tool_call.error
    assert error_message, "Error field should not be empty"
    assert "error after sleeping for 1" in error_message, (
        f"Error message should contain the sleep duration error message. Got: {error_message}"
    )


def check_unexpected_action_error(agent_client: AgentServerClient, agent_id: str):
    """
    Now, test for an unexpected action error without the `Response[T]` shape.
    """

    thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

    # Call the unexpected action error
    result, tool_calls = agent_client.send_message_to_agent_thread(
        agent_id,
        thread_id,
        "Please call the raise_unexpected_action_error action",
    )

    tool_call = tool_calls[0] if tool_calls else None
    assert tool_call is not None, f"No tool calls returned. Result: {result}"
    assert tool_call.tool_name == "raise_unexpected_action_error", (
        f"Expected unexpected action error but got: {tool_call.tool_name}"
    )

    error_message = tool_call.error
    assert error_message, "Error field should not be empty"
    assert "UNEXPECTED ACTION ERROR IS RAISED" in error_message, (
        f"Error message should contain the unexpected error message "
        f"'UNEXPECTED ACTION ERROR IS RAISED'. Got: {error_message}"
    )


def check_unexpected_value_error(agent_client: AgentServerClient, agent_id: str):
    """
    Now, test for an unexpected value error without the `Response[T]` shape.
    """

    thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

    # Call the unexpected action error
    result, tool_calls = agent_client.send_message_to_agent_thread(
        agent_id,
        thread_id,
        "Please call the raise_unexpected_value_error action",
    )

    tool_call = tool_calls[0] if tool_calls else None
    assert tool_call is not None, f"No tool calls returned. Result: {result}"
    assert tool_call.tool_name == "raise_unexpected_value_error", (
        f"Expected unexpected value error but got: {tool_call.tool_name}.\n"
        f"Result: {result}.\nTool call: {tool_call}"
    )

    assert tool_call.error, f"Tool call should contain error field. Got: {tool_call}"

    error_message = tool_call.error
    assert error_message, "Error field should not be empty"
    assert "UNEXPECTED VALUE ERROR IS RAISED" not in error_message, (
        f"Error message should NOT contain the unexpected error message "
        f"'UNEXPECTED VALUE ERROR IS RAISED'. Got: {error_message}"
    )
    assert "ValueError" in error_message, (
        f"Error message should contain the ValueError message. Got: {error_message}"
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

        # The online package should be the actual server package name (human-friendly format)
        online_package = online_packages[0]
        assert online_package["name"] == "Simple Action Package"
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
