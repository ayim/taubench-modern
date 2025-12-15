import asyncio
import contextlib
import time
from contextlib import asynccontextmanager

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


@pytest.fixture(scope="session")
async def live_custom_mcp_server_with_auth(unused_tcp_port_factory):
    import io
    import sys

    from core.tests.mcp import custom_mcp

    port = unused_tcp_port_factory()
    from sema4ai.common.process import Process

    custom_mcp_file = custom_mcp.__file__
    process = Process([sys.executable, custom_mcp_file, str(port), "dummy-token"])
    stream = io.StringIO()
    process.stream_to(stream)
    process.start()
    url = f"http://127.0.0.1:{port}"

    # Wait until the server is ready
    timeout = 30.0
    try:
        await _wait_until(url, timeout=timeout)
    except Exception as e:
        process.stop()
        raise RuntimeError(
            f"Server didn't become ready after {timeout} seconds.\nProcess output:\n{stream.getvalue()}"
        ) from e

    yield url
    process.stop()


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
    client = MCPClient(target_server=MCPServer(name="test", url=live_streamable_server, transport="streamable-http"))
    await client.connect()

    assert client.is_connected
    assert client.chosen_transport == "streamable"

    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "auth-failure",
        "success",
        "wrong-url",
    ],
)
async def test_connect_custom_mcp(live_custom_mcp_server_with_auth, scenario):
    """Connect to explicit streamable-http endpoint."""
    from httpx._exceptions import HTTPStatusError

    client = MCPClient(
        target_server=MCPServer(
            name="test",
            url=(
                live_custom_mcp_server_with_auth + "/mcp"
                if scenario != "wrong-url"
                else live_custom_mcp_server_with_auth  # use base url for 404
            ),
            transport="streamable-http",
            headers={"Authorization": "Bearer dummy-token"} if scenario != "auth-failure" else None,
        )
    )
    if scenario == "auth-failure":
        with pytest.raises(HTTPStatusError) as e:
            await client.connect()
        assert "401" in str(e.value)

    elif scenario == "wrong-url":
        with pytest.raises(ConnectionError) as e:
            await client.connect()
        assert "MCP session 'initialize' failed" in str(e.value)

    elif scenario == "success":
        await client.connect()

        assert client.is_connected
        assert client.chosen_transport == "streamable"

        await client.close()

    else:
        raise ValueError(f"Unknown scenario: {scenario}")


def test_convert_exception_group_to_single_exception():
    from agent_platform.core.mcp.mcp_client import _convert_exception_group_to_single_exception

    exc = ExceptionGroup("test", [Exception("test1"), Exception("test2")])
    assert isinstance(exc, ExceptionGroup)
    assert isinstance(_convert_exception_group_to_single_exception(exc), Exception)
    assert str(_convert_exception_group_to_single_exception(exc)) == "Multiple exceptions occurred: test1, test2"

    # Test with a single exception
    exc = Exception("test1")
    assert isinstance(exc, Exception)
    assert isinstance(_convert_exception_group_to_single_exception(exc), Exception)
    assert str(_convert_exception_group_to_single_exception(exc)) == "test1"


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
    async def mock_sse_client(url, headers=None, **_kw):
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
    assert captured_headers == expected_headers, f"Expected {expected_headers}, but got {captured_headers}"

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
    server = MCPServer(name="test-stdio-none", command="python", args=["-c", "print('test')"], env=None)

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
    server = MCPServer(name="test-stdio-empty", command="python", args=["-c", "print('test')"], env={})

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


@pytest.mark.asyncio
async def test_call_tool_retries_on_http_429(monkeypatch):
    """
    If a tool call hits a rate limit (HTTP 429), the client should retry.
    Also verify that the resumption token from the first attempt is reused.
    """
    server = await _make_dummy_server()
    client, sess, done = await _make_connected_client(server)

    sent_metadata: list[ClientMessageMetadata | None] = []
    calls = 0

    async def fake_send_request(*_a, metadata: ClientMessageMetadata | None = None, **_kw):
        nonlocal calls
        calls += 1
        sent_metadata.append(metadata)

        if calls == 1:
            # Simulate the server emitting a token before failing
            if metadata and metadata.on_resumption_token_update:
                await metadata.on_resumption_token_update("tok-429")

            # Raise a 429 as an httpx HTTPStatusError
            req = httpx.Request("POST", "http://x/mcp")
            resp = httpx.Response(429, request=req)
            raise httpx.HTTPStatusError("rate limited", request=req, response=resp)

        # Second attempt succeeds
        return mtypes.CallToolResult(content=[mtypes.TextContent(type="text", text="ok")])

    monkeypatch.setattr(sess, "send_request", fake_send_request, raising=True)

    # Prevent real transport activity during retry
    async def _noop(*_a, **_kw):  # <- coroutine!
        return None

    monkeypatch.setattr(client, "connect", _noop)
    monkeypatch.setattr(client, "close", _noop)

    # Call with 2 attempts and no backoff to keep the test snappy
    out = await client.call_tool("dummy", attempts=2, base_backoff=0)
    assert out["content"][0]["text"] == "ok"
    assert calls == 2  # we actually retried

    # Verify resumption-token behavior
    assert sent_metadata[0] is not None
    assert sent_metadata[0].resumption_token is None
    assert sent_metadata[1] is not None
    assert sent_metadata[1].resumption_token == "tok-429"

    await done()


@pytest.mark.asyncio
async def test_call_tool_429_exhausts_attempts(monkeypatch):
    server = await _make_dummy_server()
    client, sess, done = await _make_connected_client(server)

    async def always_429(*_a, **_kw):
        req = httpx.Request("POST", "http://x/mcp")
        resp = httpx.Response(429, request=req)
        raise httpx.HTTPStatusError("rate limited", request=req, response=resp)

    monkeypatch.setattr(sess, "send_request", always_429, raising=True)

    async def _noop(*_a, **_kw):
        return None

    monkeypatch.setattr(client, "connect", _noop)
    monkeypatch.setattr(client, "close", _noop)

    with pytest.raises(httpx.HTTPStatusError):
        await client.call_tool("dummy", attempts=1, base_backoff=0)

    await done()


@pytest.mark.asyncio
async def test_call_tool_does_not_retry_on_400(monkeypatch):
    server = await _make_dummy_server()
    client, sess, done = await _make_connected_client(server)

    calls = 0

    async def once_400(*_a, **_kw):
        nonlocal calls
        calls += 1
        req = httpx.Request("POST", "http://x/mcp")
        resp = httpx.Response(400, request=req)
        raise httpx.HTTPStatusError("bad request", request=req, response=resp)

    monkeypatch.setattr(sess, "send_request", once_400, raising=True)

    async def _noop(*_a, **_kw):
        return None

    monkeypatch.setattr(client, "connect", _noop)
    monkeypatch.setattr(client, "close", _noop)

    with pytest.raises(httpx.HTTPStatusError):
        await client.call_tool("dummy", attempts=5, base_backoff=0)
    assert calls == 1  # no retry
    await done()


@pytest.mark.asyncio
async def test_ensure_action_context_header_creates_header_when_not_present():
    """
    Test that _ensure_action_context_header creates X-Action-Context header
    when it doesn't already exist and there are MCP secret type headers to process.
    """
    from agent_platform.core.mcp.mcp_types import MCPVariableTypeOAuth2Secret, MCPVariableTypeSecret

    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={
            "X-API-Key": MCPVariableTypeSecret(value="api-key-value", description="API key"),
            "X-OAuth-Token": MCPVariableTypeOAuth2Secret(
                provider="google", scopes=["read"], value="oauth-token", description="OAuth token"
            ),
            "Content-Type": "application/json",
        },
        type="sema4ai_action_server",
    )
    client = MCPClient(target_server=server)
    assert "X-Action-Context" in client._headers

    import base64
    import json

    x_action_context_value = client._headers["X-Action-Context"]
    decoded_value = base64.b64decode(x_action_context_value).decode("utf-8")
    action_context = json.loads(decoded_value)

    assert "secrets" in action_context
    assert "X-API-Key" in action_context["secrets"]
    assert "X-OAuth-Token" in action_context["secrets"]
    assert "Content-Type" not in action_context["secrets"]

    assert action_context["secrets"]["X-API-Key"] == "api-key-value"
    assert action_context["secrets"]["X-OAuth-Token"] == "oauth-token"


@pytest.mark.asyncio
async def test_no_action_context_header_when_type_generic_mcp():
    """
    Test that Generic MCP Servers get secret headers directly (not in X-Action-Context)
    and don't get the X-Action-Context header.
    """
    from agent_platform.core.mcp.mcp_types import MCPVariableTypeOAuth2Secret, MCPVariableTypeSecret

    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={
            "Authorization": MCPVariableTypeSecret(value="gh-token-value", description="GitHub token"),
            "X-Custom-Auth": MCPVariableTypeOAuth2Secret(
                provider="github",
                scopes=["repo"],
                value="custom-oauth-token",
                description="Custom OAuth token",
            ),
            "Content-Type": "application/json",
        },
    )
    client = MCPClient(target_server=server)
    assert "X-Action-Context" not in client._headers

    # But they SHOULD get secret headers directly
    assert "Authorization" in client._headers
    assert client._headers["Authorization"] == "gh-token-value"
    assert "X-Custom-Auth" in client._headers
    assert client._headers["X-Custom-Auth"] == "custom-oauth-token"
    assert "Content-Type" in client._headers
    assert client._headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_ensure_action_context_header_does_not_override_existing():
    """
    Test that _ensure_action_context_header does not override existing
    X-Action-Context header.
    """
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={
            "Authorization": "Bearer server-token",
            "X-Action-Context": "existing-base64-encoded-value",
            "Content-Type": "application/json",
        },
        type="sema4ai_action_server",
    )

    client = MCPClient(target_server=server)

    assert client._headers["X-Action-Context"] == "existing-base64-encoded-value"
    assert client._headers["Authorization"] == "Bearer server-token"
    assert client._headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_ensure_action_context_header_no_secrets_no_header():
    """
    Test that _ensure_action_context_header does not create X-Action-Context header
    when there are no MCP secret type headers.
    """
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        headers={
            "Authorization": "Bearer server-token",
            "Content-Type": "application/json",
        },
        type="sema4ai_action_server",
    )

    client = MCPClient(target_server=server)

    assert "X-Action-Context" not in client._headers

    assert client._headers["Authorization"] == "Bearer server-token"
    assert client._headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_ensure_data_context_header_creates_header_when_data_server_details_present():
    """
    Test that _ensure_data_context_header creates X-Data-Context header
    when data server details are present with both HTTP and MySQL endpoints.
    """
    from agent_platform.core.data_server.data_server import (
        DataServerDetails,
        DataServerEndpoint,
        DataServerEndpointKind,
    )

    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        type="sema4ai_action_server",
    )

    data_server_details = DataServerDetails(
        username="testuser",
        password="testpass",
        data_server_endpoints=[
            DataServerEndpoint(host="localhost", port=8080, kind=DataServerEndpointKind.HTTP),
            DataServerEndpoint(host="db.example.com", port=3306, kind=DataServerEndpointKind.MYSQL),
        ],
    )

    client = MCPClient(target_server=server, data_server_details=data_server_details)
    assert "X-Data-Context" in client._headers

    import base64
    import json

    x_data_context_value = client._headers["X-Data-Context"]
    decoded_value = base64.b64decode(x_data_context_value).decode("utf-8")
    data_context = json.loads(decoded_value)

    assert "data-server" in data_context
    assert "http" in data_context["data-server"]
    assert "mysql" in data_context["data-server"]
    assert data_context["data-server"]["http"]["url"] == "http://localhost:8080"
    assert data_context["data-server"]["http"]["user"] == "testuser"
    assert data_context["data-server"]["http"]["password"] == "testpass"
    assert data_context["data-server"]["mysql"]["host"] == "db.example.com"
    assert data_context["data-server"]["mysql"]["port"] == 3306
    assert data_context["data-server"]["mysql"]["user"] == "testuser"
    assert data_context["data-server"]["mysql"]["password"] == "testpass"


@pytest.mark.asyncio
async def test_ensure_data_context_header_no_header_when_missing_credentials():
    """
    Test that _ensure_data_context_header does not create X-Data-Context header
    when data server details are missing username, password, or endpoints.
    """
    from agent_platform.core.data_server.data_server import (
        DataServerDetails,
        DataServerEndpoint,
        DataServerEndpointKind,
    )

    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        type="sema4ai_action_server",
    )

    # Test missing username
    data_server_details1 = DataServerDetails(
        username=None,
        password="testpass",
        data_server_endpoints=[DataServerEndpoint(host="localhost", port=8080, kind=DataServerEndpointKind.HTTP)],
    )

    client1 = MCPClient(target_server=server, data_server_details=data_server_details1)
    assert "X-Data-Context" not in client1._headers

    # Test missing password
    data_server_details2 = DataServerDetails(
        username="testuser",
        password=None,
        data_server_endpoints=[DataServerEndpoint(host="localhost", port=8080, kind=DataServerEndpointKind.HTTP)],
    )

    client2 = MCPClient(target_server=server, data_server_details=data_server_details2)
    assert "X-Data-Context" not in client2._headers

    # Test missing endpoints
    data_server_details3 = DataServerDetails(username="testuser", password="testpass", data_server_endpoints=[])

    client3 = MCPClient(target_server=server, data_server_details=data_server_details3)
    assert "X-Data-Context" not in client3._headers


@pytest.mark.asyncio
async def test_ensure_data_context_header_no_header_when_not_action_server_or_no_details():
    """
    Test that _ensure_data_context_header does not create X-Data-Context header
    when server type is not sema4ai_action_server or no data server details provided.
    """
    from agent_platform.core.data_server.data_server import (
        DataServerDetails,
        DataServerEndpoint,
        DataServerEndpointKind,
    )

    # Test not action server
    server1 = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        type="generic_mcp",
    )

    data_server_details = DataServerDetails(
        username="testuser",
        password="testpass",
        data_server_endpoints=[DataServerEndpoint(host="localhost", port=8080, kind=DataServerEndpointKind.HTTP)],
    )

    client1 = MCPClient(target_server=server1, data_server_details=data_server_details)
    assert "X-Data-Context" not in client1._headers

    # Test no data server details
    server2 = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        type="sema4ai_action_server",
    )

    client2 = MCPClient(target_server=server2)
    assert "X-Data-Context" not in client2._headers


@pytest.mark.asyncio
async def test_ensure_action_invocation_header_creates_header_with_valid_context():
    """
    Test that _ensure_action_invocation_header creates X-Action-Invocation-Context header
    when valid action_invocation_context is provided.
    """
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        type="sema4ai_action_server",
    )
    client = MCPClient(target_server=server)

    action_invocation_context = {
        "agent_id": "test-agent-123",
        "invoked_on_behalf_of_user_id": "user-456",
        "thread_id": "thread-789",
        "tenant_id": "tenant-abc",
    }

    client._ensure_action_invocation_header(action_invocation_context)

    assert "X-Action-Invocation-Context" in client._headers

    import base64
    import json

    x_action_invocation_context_value = client._headers["X-Action-Invocation-Context"]
    decoded_value = base64.b64decode(x_action_invocation_context_value).decode("utf-8")
    action_invocation_data = json.loads(decoded_value)

    assert action_invocation_data["agent_id"] == "test-agent-123"
    assert action_invocation_data["invoked_on_behalf_of_user_id"] == "user-456"
    assert action_invocation_data["thread_id"] == "thread-789"
    assert action_invocation_data["tenant_id"] == "tenant-abc"
    assert "action_invocation_id" in action_invocation_data
    assert len(action_invocation_data["action_invocation_id"]) == 36


@pytest.mark.asyncio
async def test_ensure_action_invocation_header_no_header():
    """
    Test that _ensure_action_invocation_header does not create X-Action-Invocation-Context header
    when action_invocation_context is None.
    """
    # Test no header when sema4ai action server
    server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        type="sema4ai_action_server",
    )
    client = MCPClient(target_server=server)

    client._ensure_action_invocation_header(None)

    assert "X-Action-Invocation-Context" not in client._headers

    # Test no header when generic MCP server
    generic_mcp_server = MCPServer(
        name="test-server",
        url="https://api.example.com/mcp",
        type="generic_mcp",
    )
    client = MCPClient(target_server=generic_mcp_server)
    client._ensure_action_invocation_header(None)
    assert "X-Action-Invocation-Context" not in client._headers
