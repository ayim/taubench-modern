from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .agent_server_cli_wrapper import AgentServerCliWrapper


def wait_for_non_error_condition(generate_error_or_none, timeout=10, sleep=1 / 20.0):
    import time

    curtime = time.time()

    while True:
        try:
            error_msg = generate_error_or_none()
        except Exception as e:
            error_msg = str(e)
            print("Saw error waiting for condition:", error_msg)

        if error_msg is None:
            break

        if timeout is not None and (time.time() - curtime > timeout):
            raise TimeoutError(f"Condition not reached in {timeout} seconds\n{error_msg}")
        time.sleep(sleep)


@contextmanager
def _bootstrap_agent_server(agent_server_cli: "AgentServerCliWrapper"):
    """
    Bootstrap the agent server and wait for it to be ready.
    """
    import time

    http_port = agent_server_cli.get_http_port()

    print("Testing connection to agent server")

    def make_connection():
        import sema4ai_http

        curtime = time.time()
        try:
            # Test the health endpoint
            response = sema4ai_http.get(f"http://localhost:{http_port}/api/v2/ok", timeout=5)
            if response.status_code == 200:
                print(f"Took {time.time() - curtime:.2f} seconds to connect to agent server")
                return None
            else:
                return f"Agent server health check failed with status {response.status_code}"
        except Exception as e:
            return f"Failed to connect to agent server on port {http_port}: {e!s}"

    # Wait for the agent server to be ready
    wait_for_non_error_condition(make_connection, timeout=60, sleep=2)

    yield agent_server_cli

    # Cleanup is handled by the wrapper's stop method


@pytest.fixture(scope="session")
def agent_server_cli(request, tmpdir_factory) -> Iterator["AgentServerCliWrapper"]:
    from .agent_server_cli_wrapper import AgentServerCliWrapper

    wrapper = AgentServerCliWrapper(Path(str(tmpdir_factory.mktemp("agent-server-cli"))))

    def teardown():
        wrapper.stop()

    # Check if agent server is already running on port 9000
    import sema4ai_http

    try:
        response = sema4ai_http.get("http://localhost:9000/api/v2/ok", timeout=2)
        if response.status_code == 200:
            print("Agent server already running on port 9000 and passed health check")
            # Create a mock wrapper for the existing server
            wrapper._launch_json = {
                "success": True,
                "data": {
                    "api": {"host": "127.0.0.1", "port": "9000"},
                    "isRunning": True,
                    "pid": 0,
                    "pidFilePath": str(wrapper._tmpdir / "agent-server.pid"),
                },
            }
            yield wrapper

            wrapper.stop()

    except Exception as e:
        print(f"Health check failed: {e}")
        # Check if port is in use (which means server is running but health check failed)
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", 9000))
            sock.close()
            if result == 0:
                print("Port 9000 is in use, assuming agent server is running")
                # Create a mock wrapper for the existing server
                wrapper._launch_json = {
                    "success": True,
                    "data": {
                        "api": {"host": "127.0.0.1", "port": "9000"},
                        "isRunning": True,
                        "pid": 0,
                        "pidFilePath": str(wrapper._tmpdir / "agent-server.pid"),
                    },
                }
                try:
                    yield wrapper
                finally:
                    teardown()
        except Exception:
            pass  # Continue with normal startup

    # This can be pretty slow (and may be common with pytest-xdist).
    wrapper.download_agent_server_cli()
    wrapper.start()

    try:
        with _bootstrap_agent_server(wrapper) as agent_server:
            yield agent_server
    finally:
        teardown()


@pytest.fixture(scope="session")
def agent_server_port(agent_server_cli: "AgentServerCliWrapper") -> int:
    return agent_server_cli.get_http_port()
