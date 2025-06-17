import http
import json
import logging
import multiprocessing
import os
import platform
import tempfile
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from datetime import timedelta
from functools import cache
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import uvicorn
from fastapi import Request
from mcp import ClientSession as MCPClientSession
from mcp import McpError
from mcp.client.streamable_http import streamablehttp_client as mcp_streamablehttp_client
from mcp.types import TextContent
from starlette.applications import Starlette
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.server.app import create_app
from agent_platform.server.storage import SQLiteStorage

logger = logging.getLogger(__name__)


if platform.system() == "Darwin":
    multiprocessing.set_start_method("fork")

MOCK_USER_SUB = "test-user-user"


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

        with patch(
            "agent_platform.server.storage.StorageService.get_instance", return_value=storage
        ):
            yield

        await storage.teardown()


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


local_mcp_proxy = Starlette(
    debug=True,
    routes=[Route("/{target:path}", proxy_route, methods=list(http.HTTPMethod))],
    lifespan=lifespan,
)


def _run_proxy_server():
    uvicorn.run(local_mcp_proxy, host="127.0.0.1", port=18000, loop="asyncio")


@pytest.fixture(scope="session")
def mock_mcp_proxy() -> Generator[None, None, None]:
    """Create a FastAPI test app with MCP endpoints."""

    p = multiprocessing.Process(target=_run_proxy_server, daemon=True)
    p.start()
    time.sleep(5)
    try:
        yield
    finally:
        p.terminate()
        p.join(timeout=5)
        if p.is_alive():
            p.kill()


@pytest.mark.asyncio
async def test_mcp_endpoints(mock_mcp_proxy):
    """Test that the MCPAuthenticationMiddleware authenticates requests."""

    async with mcp_streamablehttp_client(
        f"http://127.0.0.1:18000/api/v2/public-mcp/mcp/?api_key={MOCK_USER_SUB}"
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        # # Create a session using the client streams
        async with MCPClientSession(
            read_stream, write_stream, read_timeout_seconds=timedelta(seconds=30)
        ) as session:
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


@pytest.mark.asyncio
async def test_mcp_endpoints__random_auth(mock_mcp_proxy):
    async with mcp_streamablehttp_client(
        f"http://127.0.0.1:18000/api/v2/public-mcp/mcp/?api_key={uuid.uuid4()}"
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        # # Create a session using the client streams
        async with MCPClientSession(
            read_stream, write_stream, read_timeout_seconds=timedelta(seconds=30)
        ) as session:
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


@pytest.mark.asyncio
async def test_mcp_agent_endpoints(mock_mcp_proxy):
    """Test that the MCPAuthenticationMiddleware authenticates requests."""

    agent_1_id, _ = get_agent_ids()

    async with mcp_streamablehttp_client(
        # f"http://127.0.0.1:18000/api/v2/agent-mcp/{agent_1_id}/mcp/?api_key={MOCK_USER_SUB}"
        f"http://127.0.0.1:18000/api/v2/agent-mcp/{agent_1_id}/mcp/?api_key={MOCK_USER_SUB}"
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        # # Create a session using the client streams
        async with MCPClientSession(
            read_stream, write_stream, read_timeout_seconds=timedelta(seconds=30)
        ) as session:
            # Initialize the connection
            await session.initialize()
            assert [t.name for t in (await session.list_tools()).tools] == [
                "message_test_agent_1_agent",
            ]


@pytest.mark.asyncio
async def test_mcp_agent_endpoints_not_auth(mock_mcp_proxy):
    """Test that the MCPAuthenticationMiddleware authenticates requests."""

    agent_1_id, _ = get_agent_ids()

    async with mcp_streamablehttp_client(
        # f"http://127.0.0.1:18000/api/v2/agent-mcp/{agent_1_id}/mcp/?api_key={MOCK_USER_SUB}"
        f"http://127.0.0.1:18000/api/v2/agent-mcp/{agent_1_id}/mcp/?api_key=not_authed"
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        # # Create a session using the client streams
        async with MCPClientSession(
            read_stream, write_stream, read_timeout_seconds=timedelta(seconds=1)
        ) as session:
            # The test is expected to fail
            # since the agent ID is not associated with the authed user.
            with pytest.raises(McpError):
                await session.initialize()
