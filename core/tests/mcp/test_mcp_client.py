import asyncio
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

    with anyio.from_thread.start_blocking_portal() as portal:
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

    with anyio.from_thread.start_blocking_portal() as portal:
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
