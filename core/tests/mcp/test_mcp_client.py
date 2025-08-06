import asyncio
import contextlib
import time
from contextlib import asynccontextmanager

import anyio
import anyio.from_thread
import httpx
import mcp.types as mtypes
import pytest
import uvicorn
from mcp import ClientSession
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.logging import configure_logging
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.shared.message import ClientMessageMetadata
from sse_starlette import sse as sse_mod

from agent_platform.core.mcp.mcp_client import MCPClient
from agent_platform.core.mcp.mcp_server import MCPServer


# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True, scope="module")
def quiet_logs():
    # Set to most verbose logging for debugging
    configure_logging("DEBUG")


def _mock_transport(resp_status, resp_ctype):
    def handler(request: httpx.Request):
        headers = {"content-type": resp_ctype}
        return httpx.Response(resp_status, headers=headers)

    return httpx.MockTransport(handler)


async def _make_dummy_server() -> FastMCP:
    srv = FastMCP("dummy")

    @srv.tool()
    async def echo(x: int) -> int:
        return x

    return srv


async def _make_connected_client(server):
    """
    Returns (client, session) where `client` is an MCPClient already bound to the
    in-memory `session` --- no network, no handshake race.
    """
    sess_cm = create_connected_server_and_client_session(server._mcp_server)

    # we hand control of the context-manager to the caller --- yield style
    sess = await sess_cm.__aenter__()

    client = MCPClient(MCPServer("test", "streamable-http", url="http://x"))
    client._session, client._connected = sess, True

    async def _finaliser():
        await client.close()
        await sess_cm.__aexit__(None, None, None)

    return client, sess, _finaliser


async def _wait_until(path: str, *, timeout: float = 5.0) -> None:
    start = time.monotonic()
    while True:
        try:
            async with httpx.AsyncClient() as c:
                # We don't care which status, just that a socket is open
                await c.get(
                    path,
                    headers={
                        "accept": "application/json, text/event-stream",
                    },
                    timeout=0.3,
                )
            return
        except httpx.RequestError:
            pass
        if time.monotonic() - start > timeout:
            raise RuntimeError(f"Server route {path!r} never became ready")
        await anyio.sleep(0.1)


@pytest.fixture
async def live_streamable_server(unused_tcp_port_factory):
    port = unused_tcp_port_factory()
    url = f"http://127.0.0.1:{port}"

    srv = await _make_dummy_server()
    app = srv.streamable_http_app()

    with contextlib.ExitStack() as exit_stack:
        exit_stack.enter_context(contextlib.suppress(anyio.ClosedResourceError))
        portal = exit_stack.enter_context(anyio.from_thread.start_blocking_portal())

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        server = uvicorn.Server(config)
        portal.start_task_soon(server.serve)  # background thread
        await _wait_until(url)
        yield f"{url}/mcp"
        server.should_exit = True


@pytest.fixture
async def live_sse_server(unused_tcp_port_factory):
    port = unused_tcp_port_factory()
    url = f"http://127.0.0.1:{port}"

    srv = await _make_dummy_server()
    app = srv.sse_app()

    with contextlib.ExitStack() as exit_stack:
        exit_stack.enter_context(contextlib.suppress(anyio.ClosedResourceError))
        portal = exit_stack.enter_context(anyio.from_thread.start_blocking_portal())

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        server = uvicorn.Server(config)
        portal.start_task_soon(server.serve)  # background thread
        await _wait_until(url)
        yield f"{url}/sse"
        server.should_exit = True


@pytest.fixture(autouse=True)
def _reset_sse_starlette_between_tests():
    yield
    # give any running servers a chance to stop first
    sse_mod.AppStatus.should_exit = False
    sse_mod.AppStatus.should_exit_event = None


# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_probe_accepts_header_only():
    """
    The probe should succeed for an endless SSE stream (header-only).
    """

    def sse_handler(request: httpx.Request) -> httpx.Response:
        headers = {"content-type": "text/event-stream"}
        return httpx.Response(status_code=200, headers=headers)

    transport = httpx.MockTransport(sse_handler)

    async with httpx.AsyncClient(transport=transport, base_url="http://x") as client:
        client_obj = MCPClient(target_server=MCPServer(name="test", url="http://x"))
        ok = await client_obj._probe_endpoint(client, "http://x/stream", expect_sse=True)
        assert ok


@pytest.mark.flaky(max_runs=5, min_passes=1)
@pytest.mark.asyncio
async def test_connect_streamable_http(live_streamable_server):
    """Connect to explicit streamable-http endpoint."""
    client = MCPClient(
        target_server=MCPServer(
            name="test", url=live_streamable_server, transport="streamable-http"
        )
    )
    await client.connect()

    assert client.is_connected
    assert client.chosen_transport == "streamable"

    await client.close()


@pytest.mark.flaky(max_runs=5, min_passes=1)
@pytest.mark.asyncio
async def test_connect_sse(live_sse_server):
    """Connect to explicit SSE endpoint."""
    client = MCPClient(target_server=MCPServer(name="test", url=live_sse_server, transport="sse"))
    await client.connect()

    assert client.is_connected
    assert client.chosen_transport == "sse"

    await client.close()


@pytest.mark.asyncio
async def test_call_tool_retries(monkeypatch):
    server = await _make_dummy_server()
    client, sess, done = await _make_connected_client(server)

    calls = 0

    real_call_tool = sess.send_request
    real_close = client.close

    async def flaky(name, arguments, *a, **kw):
        nonlocal calls
        calls += 1
        if calls == 1:
            import anyio

            raise anyio.ClosedResourceError  # force retry
        # delegate to the genuine method
        return await real_call_tool(name, arguments, *a, **kw)

    monkeypatch.setattr(sess, "send_request", flaky)

    # async no-ops so awaiting them is safe
    async def _noop(*_a, **_kw):  # <- coroutine!
        return None

    monkeypatch.setattr(client, "close", _noop)
    monkeypatch.setattr(client, "connect", _noop)

    res = await client.call_tool("echo", {"x": 9})
    assert res["content"][0]["text"] == "9"
    assert calls == 2

    monkeypatch.setattr(client, "close", real_close)
    await real_close()

    await done()  # tidy up


@pytest.mark.asyncio
async def test_list_tools_binding():
    server = await _make_dummy_server()
    client, sess, done = await _make_connected_client(server)

    tools = await client.list_tools()
    assert len(tools) == 1
    echo = tools[0]
    assert echo.name == "echo"

    out = await echo.function(x=3)
    assert out["content"][0]["text"] == "3"

    await done()


@pytest.mark.asyncio
async def test_list_tools_default_description(monkeypatch):
    """Test that tools without descriptions get a default description."""
    server = await _make_dummy_server()
    client, sess, done = await _make_connected_client(server)

    # Mock the session's list_tools to return a tool without description
    async def mock_list_tools():
        return mtypes.ListToolsResult(
            tools=[
                mtypes.Tool(
                    name="test_tool",
                    description=None,  # No description provided
                    inputSchema={"type": "object", "properties": {}},
                ),
                mtypes.Tool(
                    name="another_tool",
                    description="",  # Empty description
                    inputSchema={"type": "object", "properties": {}},
                ),
            ]
        )

    monkeypatch.setattr(sess, "list_tools", mock_list_tools)

    tools = await client.list_tools()
    assert len(tools) == 2

    # Check that tools without descriptions get default descriptions
    assert tools[0].name == "test_tool"
    assert tools[0].description == "Tool: test_tool"

    assert tools[1].name == "another_tool"
    assert tools[1].description == "Tool: another_tool"

    await done()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "ctype", "good_for_streamable", "good_for_sse"),
    [
        (200, "application/json", True, True),
        (200, "text/event-stream", True, True),  # GET /mcp returns SSE
        (202, "text/event-stream", True, True),
        (405, "application/json", True, True),  # wrong verb --- still alive
        (404, "text/plain", True, True),
    ],
)
async def test_probe_matrix(status, ctype, good_for_streamable, good_for_sse):
    tr = _mock_transport(status, ctype)
    async with httpx.AsyncClient(transport=tr, base_url="http://x") as client:
        mc = MCPClient(MCPServer("dummy", "streamable-http", "http://x"))
        ok_streamable = await mc._probe_endpoint(client, "http://x/mcp", expect_sse=False)
        ok_sse = await mc._probe_endpoint(client, "http://x/sse", expect_sse=True)

    assert ok_streamable is good_for_streamable
    assert ok_sse is good_for_sse


@pytest.mark.asyncio
async def test_connect_raises_when_no_transport(tmp_path):
    # use free port but no server running
    url = "http://127.0.0.1:9"  # any closed port
    client = MCPClient(MCPServer("test", "streamable-http", url))
    with pytest.raises(ConnectionError):
        await client.connect()


@pytest.mark.asyncio
async def test_call_tool_autoconnect(monkeypatch):
    server = await _make_dummy_server()
    client, sess, done = await _make_connected_client(server)

    # simulate disconnected state
    client._connected = False

    called = 0

    async def fake_connect():
        nonlocal called
        called += 1
        client._connected = True

    monkeypatch.setattr(client, "connect", fake_connect)

    res = await client.call_tool("echo", {"x": 7}, attempts=1)
    assert res["content"][0]["text"] == "7"
    assert called == 1

    await done()


@pytest.mark.asyncio
async def test_call_tool_propagates_non_transient(monkeypatch):
    server = await _make_dummy_server()
    client, sess, done = await _make_connected_client(server)

    async def boom(*_a, **_kw):
        raise ValueError("boom")

    monkeypatch.setattr(sess, "send_request", boom)

    # Prevent the retry logic from attempting real transport work
    async def _noop(*_a, **_kw):
        return None

    monkeypatch.setattr(client, "close", _noop)
    monkeypatch.setattr(client, "connect", _noop)

    with pytest.raises(ValueError, match="boom"):
        await client.call_tool("echo")

    await done()


def test_normalise_url():
    s, e = MCPClient._normalise("http://example.com/")
    assert s == "http://example.com/mcp"
    assert e == "http://example.com/sse"
    s, e = MCPClient._normalise("http://host/mcp")
    assert s == "http://host/mcp"
    assert e == "http://host/sse"


@pytest.mark.asyncio
async def test_single_transport(monkeypatch):
    """Client only spawns one transport when transport is explicit."""

    async def probe_ok(*_a, **_kw):
        return True

    monkeypatch.setattr(MCPClient, "_probe_endpoint", probe_ok)

    # Dummy transport generating instant handshake
    @asynccontextmanager
    async def dummy_transport():
        # anyio.create_memory_object_stream returns (send, receive)
        # but ClientSession expects (receive, send)
        _send1, _recv1 = anyio.create_memory_object_stream(0)
        _send2, _recv2 = anyio.create_memory_object_stream(0)
        rs, ws = _recv1, _send2

        # Fake initialize(): immediately return valid result
        async def fake_init(self):
            return mtypes.InitializeResult(
                protocolVersion="dummy",
                capabilities=mtypes.ServerCapabilities(),
                serverInfo=mtypes.Implementation(name="dummy", version="0"),
            )

        monkeypatch.setattr(ClientSession, "initialize", fake_init, raising=True)
        yield rs, ws, (lambda: "sid-123")

    monkeypatch.setattr(
        "agent_platform.core.mcp.mcp_client.streamablehttp_client",
        lambda *_a, **_kw: dummy_transport(),
    )

    client = MCPClient(MCPServer("single", url="http://x", transport="streamable-http"))
    await client.connect()
    assert client.chosen_transport == "streamable"
    assert len(client._transport_tasks) == 1
    await client.close()


@pytest.mark.asyncio
async def test_winner_failure_unblocks_close(monkeypatch):
    """
    The winning transport throws after victory; close() still returns.
    """

    async def probe_ok(*_a, **_kw):
        return True

    monkeypatch.setattr(MCPClient, "_probe_endpoint", probe_ok)

    @asynccontextmanager
    async def flaky_transport():
        _send1, _recv1 = anyio.create_memory_object_stream(0)
        _send2, _recv2 = anyio.create_memory_object_stream(0)
        rs, ws = _recv1, _send2

        async def fake_init(self):
            return mtypes.InitializeResult(
                protocolVersion="dummy",
                capabilities=mtypes.ServerCapabilities(),
                serverInfo=mtypes.Implementation(name="dummy", version="0"),
            )

        monkeypatch.setattr(ClientSession, "initialize", fake_init, raising=True)
        yield rs, ws, (lambda: "sid")
        # Simulate crash **after** victory
        raise RuntimeError("oops")

    monkeypatch.setattr(
        "agent_platform.core.mcp.mcp_client.streamablehttp_client",
        lambda *_a, **_kw: flaky_transport(),
    )

    client = MCPClient(MCPServer("flaky", url="http://x", transport="streamable-http"))
    await client.connect()
    # winner has crashed; close() must complete quickly
    await asyncio.wait_for(client.close(), timeout=2.0)


@pytest.mark.asyncio
async def test_resumption_token_retry(monkeypatch):
    """A failed call is retried with the SSE resumption token from the first attempt."""

    # Minimal in-memory session
    _send1, _recv1 = anyio.create_memory_object_stream(0)
    _send2, _recv2 = anyio.create_memory_object_stream(0)
    rs, ws = _recv1, _send2
    session = ClientSession(rs, ws)

    client = MCPClient(MCPServer("mem", "streamable-http", url="http://x"))
    client._session = session  # type: ignore[attr-defined]
    client._connected = True  # type: ignore[attr-defined]

    sent_metadata: list[ClientMessageMetadata | None] = []

    async def fake_send_request(*_a, metadata: ClientMessageMetadata | None = None, **_kw):
        sent_metadata.append(metadata)
        # first attempt: give the token then fail
        if len(sent_metadata) == 1:
            # simulate server streaming first chunk with token "tok-1"
            if metadata and metadata.on_resumption_token_update:
                await metadata.on_resumption_token_update("tok-1")
            raise anyio.ClosedResourceError()

        # second attempt succeeds
        return mtypes.CallToolResult(  # type: ignore[return-value,arg-type]
            content=[mtypes.TextContent(type="text", text="ok")]
        )

    monkeypatch.setattr(session, "send_request", fake_send_request, raising=True)

    # Prevent real transport work during retries
    async def _noop(*_a, **_kw):
        return None

    monkeypatch.setattr(client, "connect", _noop)
    monkeypatch.setattr(client, "close", _noop)

    result = await client.call_tool("dummy", attempts=2)
    assert result["content"][0]["text"] == "ok"

    assert len(sent_metadata) == 2
    # First attempt had no token
    assert sent_metadata[0]
    assert sent_metadata[0].resumption_token is None
    # Second attempt re-used the token captured from callback
    assert sent_metadata[1]
    assert sent_metadata[1].resumption_token == "tok-1"


@pytest.mark.asyncio
async def test_bad_url_scheme_rejected():
    bad = MCPClient(MCPServer("bad", url="ftp://example.com"))
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        await bad.connect()


@pytest.mark.asyncio
async def test_client_additional_headers_override():
    """
    `additional_headers` supplied to `MCPClient` should overwrite duplicates
    coming from the `MCPServer.headers` mapping.
    """
    # Create an MCPServer with some headers
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={
            "Authorization": "Bearer server-token",
            "X-Server-Header": "server-value",
            "Content-Type": "application/json",
        },
    )

    # Create additional headers that overlap with server headers
    additional_headers = {
        "Authorization": "Bearer client-token",  # Should override server header
        "X-Client-Header": "client-value",  # Should be added
        "Content-Type": "application/xml",  # Should override server header
    }

    # Create MCPClient with both server headers and additional headers
    client = MCPClient(target_server=server, additional_headers=additional_headers)

    # Verify that additional_headers override server headers for duplicates
    expected_headers = {
        "Authorization": "Bearer client-token",  # Overridden by additional_headers
        "X-Server-Header": "server-value",  # Preserved from server
        "Content-Type": "application/xml",  # Overridden by additional_headers
        "X-Client-Header": "client-value",  # Added from additional_headers
    }

    assert client._headers == expected_headers

    # Verify that original server headers are unchanged
    assert server.headers == {
        "Authorization": "Bearer server-token",
        "X-Server-Header": "server-value",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_client_sse_headers_propagated(monkeypatch):
    """
    Ensure headers (server + additional) are forwarded to `sse_client`.
    """
    # Create an MCPServer with SSE transport and headers
    server = MCPServer(
        name="sse-server",
        url="https://api.example.com/sse",
        transport="sse",
        headers={"Authorization": "Bearer server-token", "X-Server-Header": "server-value"},
    )

    # Additional headers to be merged
    additional_headers = {
        "Authorization": "Bearer client-token",  # Should override server header
        "X-Client-Header": "client-value",  # Should be added
    }

    # Expected merged headers
    expected_headers = {
        "Authorization": "Bearer client-token",
        "X-Server-Header": "server-value",
        "X-Client-Header": "client-value",
    }

    # Mock the probe to return success
    async def probe_ok(*_a, **_kw):
        return True

    monkeypatch.setattr(MCPClient, "_probe_endpoint", probe_ok)

    # Capture the headers passed to sse_client
    captured_headers = None

    @asynccontextmanager
    async def mock_sse_client(url, headers=None):
        nonlocal captured_headers
        captured_headers = headers

        # Create minimal mock transport that satisfies the connection process
        _send1, _recv1 = anyio.create_memory_object_stream(0)
        _send2, _recv2 = anyio.create_memory_object_stream(0)
        rs, ws = _recv1, _send2

        # Mock successful initialization
        async def fake_init(self):
            return mtypes.InitializeResult(
                protocolVersion="2025-03-26",
                capabilities=mtypes.ServerCapabilities(),
                serverInfo=mtypes.Implementation(name="test-sse", version="1.0"),
            )

        monkeypatch.setattr(ClientSession, "initialize", fake_init, raising=True)

        # Return only the streams as expected by the transport
        yield rs, ws

    # Replace the real sse_client with our mock
    monkeypatch.setattr("agent_platform.core.mcp.mcp_client.sse_client", mock_sse_client)

    # Create MCPClient with both server and additional headers
    client = MCPClient(target_server=server, additional_headers=additional_headers)

    # Connect to trigger the sse_client call
    await client.connect()

    # Verify the headers were passed correctly to sse_client
    assert captured_headers == expected_headers, (
        f"Expected {expected_headers}, but got {captured_headers}"
    )

    # Verify connection was successful
    assert client.is_connected
    assert client.chosen_transport == "sse"

    # Note: Skipping cleanup to avoid asyncio transport issues similar to other tests


@pytest.mark.asyncio
async def test_client_headers_edge_cases():
    """Test various edge cases for header values and types."""

    # Test case 1: headers: None
    server1 = MCPServer(
        name="test-server-none",
        url="https://api.example.com/mcp",
        headers=None,
    )
    client1 = MCPClient(target_server=server1)
    assert client1._headers == {}

    # Test case 2: headers: {} (empty dict)
    server2 = MCPServer(
        name="test-server-empty",
        url="https://api.example.com/mcp",
        headers={},
    )
    client2 = MCPClient(target_server=server2)
    assert client2._headers == {}

    # Test case 3: headers: {"":""} (empty key and value)
    server3 = MCPServer(
        name="test-server-empty-key-value",
        url="https://api.example.com/mcp",
        headers={"": ""},
    )
    client3 = MCPClient(target_server=server3)
    assert client3._headers == {"": ""}

    # Test case 4: headers: {"test":""} (empty value)
    server4 = MCPServer(
        name="test-server-empty-value",
        url="https://api.example.com/mcp",
        headers={"test": ""},
    )
    client4 = MCPClient(target_server=server4)
    assert client4._headers == {"test": ""}

    # Test case 5: headers: {"": "test"} (empty key)
    server5 = MCPServer(
        name="test-server-empty-key",
        url="https://api.example.com/mcp",
        headers={"": "test"},
    )
    client5 = MCPClient(target_server=server5)
    assert client5._headers == {"": "test"}


@pytest.mark.asyncio
async def test_client_headers_with_additional_headers_edge_cases():
    """Test edge cases when combining server headers with additional headers."""

    # Test case 1: Server has None headers, additional headers provided
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers=None,
    )
    additional_headers = {"Authorization": "Bearer token"}
    client = MCPClient(target_server=server, additional_headers=additional_headers)
    assert client._headers == {"Authorization": "Bearer token"}

    # Test case 2: Server has empty headers, additional headers provided
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={},
    )
    additional_headers = {"Authorization": "Bearer token"}
    client = MCPClient(target_server=server, additional_headers=additional_headers)
    assert client._headers == {"Authorization": "Bearer token"}

    # Test case 3: Both server and additional headers have empty keys
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={"": "server-value"},
    )
    additional_headers = {"": "client-value"}  # Should override
    client = MCPClient(target_server=server, additional_headers=additional_headers)
    assert client._headers == {"": "client-value"}

    # Test case 4: None additional headers
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={"Authorization": "Bearer server-token"},
    )
    client = MCPClient(target_server=server, additional_headers=None)
    assert client._headers == {"Authorization": "Bearer server-token"}

    # Test case 5: Empty additional headers
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={"Authorization": "Bearer server-token"},
    )
    client = MCPClient(target_server=server, additional_headers={})
    assert client._headers == {"Authorization": "Bearer server-token"}


@pytest.mark.asyncio
async def test_stdio_env_merging(monkeypatch):
    """Test that stdio transport properly merges environment variables."""
    import os

    # Mock the stdio environment variable to allow stdio first
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO", "1")

    # Mock os.environ to have some base environment variables
    mock_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
        "EXISTING_VAR": "original_value",
        "SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO": "1",
    }
    monkeypatch.setattr(os, "environ", mock_env)

    # Create a server with some environment variables
    server = MCPServer(
        name="test-stdio",
        command="python",
        args=["-c", "print('test')"],
        env={
            "NEW_VAR": "new_value",
            "EXISTING_VAR": "overridden_value",  # This should override the original
        },
    )

    client = MCPClient(target_server=server)

    # Mock the StdioServerParameters to capture the env that gets passed
    captured_params = None

    def mock_stdio_client(params):
        nonlocal captured_params
        captured_params = params
        # Return a mock context manager that doesn't actually run anything
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def dummy_context():
            yield None, None

        return dummy_context()

    monkeypatch.setattr("agent_platform.core.mcp.mcp_client.stdio_client", mock_stdio_client)

    # Create the stdio factory (this is what we're testing)
    client._stdio_factory()

    # The factory should have been called with merged environment
    assert captured_params is not None
    merged_env = captured_params.env

    # Verify that the environment was properly merged
    assert merged_env["PATH"] == "/usr/bin:/bin"  # From original env
    assert merged_env["HOME"] == "/home/user"  # From original env
    assert merged_env["NEW_VAR"] == "new_value"  # From server env
    assert merged_env["EXISTING_VAR"] == "overridden_value"  # Server env overrides original
    assert merged_env["SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO"] == "1"  # From env


@pytest.mark.asyncio
async def test_stdio_env_none_handling(monkeypatch):
    """Test that stdio transport handles None env gracefully."""
    import os

    # Mock the stdio environment variable to allow stdio first
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO", "1")

    # Mock os.environ (this should include the env var set above)
    mock_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
        "SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO": "1",
    }
    monkeypatch.setattr(os, "environ", mock_env)

    # Create a server with no environment variables (None)
    server = MCPServer(
        name="test-stdio-none", command="python", args=["-c", "print('test')"], env=None
    )

    client = MCPClient(target_server=server)

    # Mock the StdioServerParameters to capture the env that gets passed
    captured_params = None

    def mock_stdio_client(params):
        nonlocal captured_params
        captured_params = params
        # Return a mock context manager that doesn't actually run anything
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def dummy_context():
            yield None, None

        return dummy_context()

    monkeypatch.setattr("agent_platform.core.mcp.mcp_client.stdio_client", mock_stdio_client)

    # Create the stdio factory
    client._stdio_factory()

    # The factory should have been called with only the current environment
    assert captured_params is not None
    merged_env = captured_params.env

    # Verify that only the current environment is used
    assert merged_env["PATH"] == "/usr/bin:/bin"
    assert merged_env["HOME"] == "/home/user"
    assert merged_env["SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO"] == "1"
    assert len(merged_env) == 3  # Only the original env vars


@pytest.mark.asyncio
async def test_stdio_env_empty_handling(monkeypatch):
    """Test that stdio transport handles empty env dict gracefully."""
    import os

    # Mock the stdio environment variable to allow stdio first
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO", "1")

    # Mock os.environ (this should include the env var set above)
    mock_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
        "SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO": "1",
    }
    monkeypatch.setattr(os, "environ", mock_env)

    # Create a server with empty environment variables
    server = MCPServer(
        name="test-stdio-empty", command="python", args=["-c", "print('test')"], env={}
    )

    client = MCPClient(target_server=server)

    # Mock the StdioServerParameters to capture the env that gets passed
    captured_params = None

    def mock_stdio_client(params):
        nonlocal captured_params
        captured_params = params
        # Return a mock context manager that doesn't actually run anything
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def dummy_context():
            yield None, None

        return dummy_context()

    monkeypatch.setattr("agent_platform.core.mcp.mcp_client.stdio_client", mock_stdio_client)

    # Create the stdio factory
    client._stdio_factory()

    # The factory should have been called with only the current environment
    assert captured_params is not None
    merged_env = captured_params.env

    # Verify that only the current environment is used
    assert merged_env["PATH"] == "/usr/bin:/bin"
    assert merged_env["HOME"] == "/home/user"
    assert merged_env["SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO"] == "1"
    assert len(merged_env) == 3  # Only the original env vars


@pytest.mark.asyncio
async def test_stdio_env_merging_preserves_current_env(monkeypatch):
    """Test that stdio transport preserves all current environment variables."""
    import os

    # Mock the stdio environment variable to allow stdio first
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO", "1")

    # Mock os.environ with many variables
    mock_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
        "LANG": "en_US.UTF-8",
        "USER": "testuser",
        "SHELL": "/bin/bash",
        "TERM": "xterm-256color",
        "SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO": "1",
    }
    monkeypatch.setattr(os, "environ", mock_env)

    # Create a server with just one additional environment variable
    server = MCPServer(
        name="test-stdio-preserve",
        command="python",
        args=["-c", "print('test')"],
        env={"CUSTOM_VAR": "custom_value"},
    )

    client = MCPClient(target_server=server)

    # Mock the StdioServerParameters to capture the env that gets passed
    captured_params = None

    def mock_stdio_client(params):
        nonlocal captured_params
        captured_params = params
        # Return a mock context manager that doesn't actually run anything
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def dummy_context():
            yield None, None

        return dummy_context()

    monkeypatch.setattr("agent_platform.core.mcp.mcp_client.stdio_client", mock_stdio_client)

    # Create the stdio factory
    client._stdio_factory()

    # The factory should have been called with merged environment
    assert captured_params is not None
    merged_env = captured_params.env

    # Verify that all current environment variables are preserved
    for key, value in mock_env.items():
        assert merged_env[key] == value

    # Verify that the custom variable was added
    assert merged_env["CUSTOM_VAR"] == "custom_value"

    # Verify the total count
    assert len(merged_env) == len(mock_env) + 1
