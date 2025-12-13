import http
import json
import logging
import multiprocessing
import os
import platform
import socket
import tempfile
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from datetime import timedelta
from functools import cache
from typing import Any, cast
from unittest.mock import patch

import httpx
import pytest
import uvicorn
from fastapi import Request
from mcp import ClientSession as MCPClientSession
from mcp.client.streamable_http import streamablehttp_client as mcp_streamablehttp_client
from mcp.types import TextContent
from starlette.applications import Starlette
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route

from agent_platform.core.thread import Thread, ThreadMessage, ThreadTextContent

logger = logging.getLogger(__name__)

if platform.system() == "Windows":
    # On Windows, 'spawn' is the default, but we need to ensure it's explicitly set.
    # This helps with process management and prevents timeouts
    multiprocessing.set_start_method("spawn", force=True)
else:
    multiprocessing.set_start_method("fork")

MOCK_USER_SUB = "test-user-user"

# Skip all tests in this module on Windows
# TODO: @Vlad, these are still failing _consistently_ on Windows.
pytestmark = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Skipped on Windows due to persistent issues",
)


@cache
def get_agent_ids() -> list[str]:
    return ["b4083775-bd95-4590-aa2c-3b508c2f19af", "34071679-bd8f-466f-baec-f2c11ac52f83"]


@contextmanager
def windows_temporary_file():
    # On Windows, a file opened by NamedTemporaryFile cannot be opened by another process
    # while it's still open by the original process. Using mkstemp instead.
    fd, temp_db_path = tempfile.mkstemp()
    os.close(fd)  # Close the file descriptor immediately
    try:
        yield temp_db_path
    finally:
        try:
            os.unlink(temp_db_path)
        except Exception:
            pass


@asynccontextmanager
async def mock_storage() -> AsyncGenerator[None, Any]:
    """Create a mock storage instance."""

    from agent_platform.core.agent import Agent, AgentArchitecture
    from agent_platform.core.runbook import Runbook
    from agent_platform.server.storage import SQLiteStorage

    with ExitStack() as stack:
        if platform.system() == "Windows":
            temp_db_file = stack.enter_context(windows_temporary_file())
        else:
            temp_db_file = stack.enter_context(tempfile.NamedTemporaryFile()).name

        # On Unix-like systems, we can use NamedTemporaryFile as before

        storage = SQLiteStorage(temp_db_file)
        await storage.setup()

        user, _ = await storage.get_or_create_user(MOCK_USER_SUB)

        agent_1_id, agent_2_id = get_agent_ids()

        await storage.upsert_agent(
            user.user_id,
            Agent(
                agent_id=agent_1_id,
                name="Test Agent 1",
                description="Test agent 1",
                version="1.0.0",
                runbook_structured=Runbook(raw_text="You are a helpful assistant.", content=[]),
                platform_configs=[],
                user_id=user.user_id,
                agent_architecture=AgentArchitecture(
                    name="agent_platform.architectures.default",
                    version="0.0.1",
                ),
                observability_configs=[],
            ),
        )

        await storage.upsert_thread(
            user_id=user.user_id,
            thread=Thread(
                user_id=user.user_id,
                agent_id=agent_1_id,
                name="Test Thread 1",
                messages=[
                    ThreadMessage(
                        content=[ThreadTextContent("agent_1_message_1")],
                        commited=True,
                        role="agent",
                    ),
                    ThreadMessage(
                        content=[ThreadTextContent("agent_1_message_2")],
                        commited=True,
                        role="user",
                    ),
                    ThreadMessage(
                        content=[ThreadTextContent("agent_1_message_3")],
                        commited=True,
                        role="agent",
                    ),
                ],
            ),
        )

        await storage.upsert_thread(
            user_id=user.user_id,
            thread=Thread(
                user_id=user.user_id,
                agent_id=agent_1_id,
                name="Test Thread 2",
                messages=[
                    ThreadMessage(
                        content=[ThreadTextContent("agent_1_thread_2_message_1")],
                        commited=True,
                        role="agent",
                    ),
                ],
            ),
        )

        await storage.upsert_agent(
            user.user_id,
            Agent(
                agent_id=agent_2_id,
                name="Test Agent 2",
                description="Test agent 2",
                version="1.0.0",
                runbook_structured=Runbook(raw_text="You are a helpful assistant.", content=[]),
                platform_configs=[],
                user_id=user.user_id,
                agent_architecture=AgentArchitecture(
                    name="agent_platform.architectures.default",
                    version="0.0.1",
                ),
                observability_configs=[],
            ),
        )

        with patch("agent_platform.server.storage.StorageService.get_instance", return_value=storage):
            yield

        await storage.teardown()


def _build_proxy_app() -> Starlette:
    """Build a Starlette app that proxies requests to the local MCP proxy."""

    async def proxy_route(request: Request) -> Response:
        logger.info(f"proxy_route: {request.method} {request.url}")

        cookies = httpx.Cookies(request.cookies)
        cookies.set("agent_server_user_id", request.query_params["api_key"])

        body = await request.body()

        client: httpx.AsyncClient = request.state.http_client
        stream_client = client.stream(
            request.method,
            f"/{request.path_params['target']}",
            params=request.query_params,
            content=body,
            headers=request.headers,
            cookies=cookies,
        )

        server_response = await stream_client.__aenter__()

        async def _stream():
            response_body = b""
            nonlocal server_response, stream_client
            try:
                async for chunk in server_response.aiter_raw():
                    response_body += chunk
                    yield chunk
            finally:
                await stream_client.__aexit__(None, None, None)

        return StreamingResponse(
            content=_stream(),
            status_code=server_response.status_code,
            headers=server_response.headers,
            media_type=server_response.headers.get("content-type"),
        )

    @asynccontextmanager
    async def lifespan(app: Starlette):
        from agent_platform.server.app import create_app

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(mock_storage())
            agent_server_app = create_app()

            client = await stack.enter_async_context(
                httpx.AsyncClient(
                    timeout=None,
                    transport=httpx.ASGITransport(agent_server_app),
                    base_url="http://127.0.0.1:18000",
                )
            )

            await stack.enter_async_context(agent_server_app.router.lifespan_context(agent_server_app))

            yield {
                "http_client": client,
            }

    return Starlette(
        routes=[Route("/{target:path}", proxy_route, methods=list(http.HTTPMethod))],
        lifespan=lifespan,
    )


def _wait_for_port(host: str, port_queue: multiprocessing.Queue, timeout: float = 30.0) -> int:
    """Wait for a server to be available on a specific port.

    Args:
        host: The hostname or IP address where the server is expected to be running.
        port_queue: A multiprocessing Queue that will provide the port number when available.
        timeout: Maximum time in seconds to wait for the port to become available.

    Returns:
        int: The port number that was successfully connected to.

    Raises:
        pytest.fail: If the port doesn't become available within the timeout period,
                     or if any other error occurs during the connection attempt.
    """
    port = None

    try:
        # Get the port number from the queue, waiting up to timeout seconds
        port = port_queue.get(timeout=timeout)
        # Attempt to establish a connection to verify the port is actually available
        with socket.create_connection((host, port), timeout=10):
            return port
    except Exception as e:
        # If the connection fails, mark the test as an expected failure
        pytest.fail(f"Server on {host}:{port} did not start within {timeout} seconds\n{e}")


def _run_proxy_server(port_queue: multiprocessing.Queue) -> None:
    """Run the Starlette proxy on the given *port* inside a fresh uvicorn loop."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # On Windows, we don't set any special socket options to ensure compatibility
        # with all Windows versions, including Windows 2025
        if platform.system() != "Windows":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        s.bind(("127.0.0.1", 0))
        s.listen(100)

        port: int = s.getsockname()[1]

        port_queue.put(port)

        config = uvicorn.Config(_build_proxy_app(), host="127.0.0.1", port=port)
        try:
            uvicorn.Server(config).run(sockets=[s])
        except KeyboardInterrupt:
            pass


@pytest.fixture(scope="session")
def mock_mcp_proxy() -> Generator[str, None, None]:
    """Spin-up the Starlette proxy on a free TCP port and yield its base-URL."""

    port_queue = multiprocessing.Queue()

    p = multiprocessing.Process(target=_run_proxy_server, args=(port_queue,))
    p.start()

    try:
        # Wait for the port to be available
        port = _wait_for_port("127.0.0.1", port_queue)
        yield f"http://127.0.0.1:{port}"
    finally:
        # Process termination for non-Windows platforms
        try:
            p.terminate()
            p.join(timeout=5)
            if p.is_alive():
                logger.warning("Process did not terminate gracefully, killing it")
                p.kill()
                p.join(timeout=2)
        except Exception as e:
            logger.error(f"Error terminating process: {e}")
            # Make a final attempt to kill the process
            try:
                if p.is_alive():
                    p.kill()
            except Exception:
                pass


@pytest.mark.flaky(max_runs=5, min_passes=1)
@pytest.mark.asyncio
async def test_mcp_endpoints(mock_mcp_proxy):
    """Test that the MCPAuthenticationMiddleware authenticates requests."""

    base_url = mock_mcp_proxy
    async with mcp_streamablehttp_client(f"{base_url}/api/v2/public-mcp/mcp/?api_key={MOCK_USER_SUB}") as (
        read_stream,
        write_stream,
        _,
    ):
        # # Create a session using the client streams
        async with MCPClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=30)) as session:
            # Initialize the connection
            await session.initialize()
            assert [t.name for t in (await session.list_tools()).tools] == [
                "list_agents",
                "chat_with_agent",
                "list_threads_for_agent",
            ]

            agent_names = set()
            for item in (await session.call_tool("list_agents")).content:
                assert isinstance(item, TextContent)
                agent = json.loads(item.text)
                agent_names.add(agent["name"])

            assert agent_names == {"Test Agent 1", "Test Agent 2"}


@pytest.mark.flaky(max_runs=5, min_passes=1)
@pytest.mark.asyncio
async def test_mcp_endpoints__random_auth(mock_mcp_proxy):
    base_url = mock_mcp_proxy
    async with mcp_streamablehttp_client(f"{base_url}/api/v2/public-mcp/mcp/?api_key={uuid.uuid4()}") as (
        read_stream,
        write_stream,
        _,
    ):
        # # Create a session using the client streams
        async with MCPClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=30)) as session:
            # Initialize the connection
            await session.initialize()
            assert [t.name for t in (await session.list_tools()).tools] == [
                "list_agents",
                "chat_with_agent",
                "list_threads_for_agent",
            ]

            agent_names = set()
            for item in (await session.call_tool("list_agents")).content:
                assert isinstance(item, TextContent)
                agent = json.loads(item.text)
                agent_names.add(agent["name"])

            assert len(agent_names) == 0


@pytest.mark.flaky(max_runs=5, min_passes=1)
@pytest.mark.asyncio
async def test_agent_as_mcp_endpoints(mock_mcp_proxy):
    """Test that the MCPAuthenticationMiddleware authenticates requests."""

    agent_1_id, _ = get_agent_ids()

    base_url = mock_mcp_proxy
    async with mcp_streamablehttp_client(
        f"{base_url}/api/public/v1/agent-mcp/{agent_1_id}/mcp/?api_key={MOCK_USER_SUB}"
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        # # Create a session using the client streams
        async with MCPClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=30)) as session:
            # Initialize the connection
            await session.initialize()
            assert [t.name for t in (await session.list_tools()).tools] == [
                "message_test_agent_1_agent",
                "list_test_agent_1_agent_threads",
                "get_test_agent_1_agent_thread_messages",
            ]

            list_thread_response = await session.call_tool("list_test_agent_1_agent_threads")

            threads = json.loads(cast(TextContent, list_thread_response.content[0]).text)["threads"]
            assert {t["thread_identifier"] for t in threads} == {"Test Thread 1", "Test Thread 2"}

            test_thread_1 = next(t for t in threads if t["thread_identifier"] == "Test Thread 1")

            list_messages_response = await session.call_tool(
                "get_test_agent_1_agent_thread_messages",
                arguments={"thread_id": test_thread_1["thread_id"]},
            )

            messages = json.loads(cast(TextContent, list_messages_response.content[0]).text)["thread_messages"]
            assert messages == [
                {"role": "agent", "content": [{"kind": "text", "text": "agent_1_message_1"}]},
                {"role": "user", "content": [{"kind": "text", "text": "agent_1_message_2"}]},
                {"role": "agent", "content": [{"kind": "text", "text": "agent_1_message_3"}]},
            ]


@pytest.mark.flaky(max_runs=5, min_passes=1)
@pytest.mark.asyncio
async def test_agent_as_mcp_endpoints__no_auth(mock_mcp_proxy):
    """Test that the MCPAuthenticationMiddleware authenticates requests."""

    agent_1_id, _ = get_agent_ids()

    async def attempt_unauthorized_connection():
        base_url = mock_mcp_proxy
        async with mcp_streamablehttp_client(
            f"{base_url}/api/public/v1/agent-mcp/{agent_1_id}/mcp/?api_key=not_authed"
        ) as (
            read_stream,
            write_stream,
            _,
        ):
            # Create a session using the client streams
            async with MCPClientSession(
                read_stream, write_stream, read_timeout_seconds=timedelta(seconds=2)
            ) as session:
                # The server responds with HTTP 403 which is surfaced as an ExceptionGroup
                # containing a single `httpx.HTTPStatusError`.  Catch the group and verify
                # the wrapped exception.
                await session.initialize()

    # The server responds with HTTP 403 which is surfaced as an ExceptionGroup
    # containing a single `httpx.HTTPStatusError`.  Catch the group and verify
    # the wrapped exception.
    with pytest.raises(ExceptionGroup) as exc_info:
        await attempt_unauthorized_connection()

    assert len(exc_info.value.exceptions) == 1
    inner_exc = exc_info.value.exceptions[0]
    assert isinstance(inner_exc, httpx.HTTPStatusError)
    assert inner_exc.response.status_code == http.HTTPStatus.FORBIDDEN
