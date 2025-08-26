from urllib.parse import urlparse

import pytest
from sema4ai.actions._action import get_current_requests_contexts
from starlette.requests import Request

from agent_platform.server.api.dependencies import _set_actions_context


@pytest.fixture
def mock_request(
    base_url: str = "http://localhost:8000",
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 80)

    raw_headers: list[tuple[bytes, bytes]] = []
    hdrs = {"host": f"{host}:{port}", **(headers or {})}
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        hdrs["cookie"] = cookie_header
    for k, v in hdrs.items():
        raw_headers.append((k.lower().encode("utf-8"), str(v).encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("testclient", 50000),
        "server": (host, port),
        "app": object(),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_get_agent_server_client_stub(mock_request: Request):
    """Stub test for get_agent_server_client."""
    agent_id = "test-agent"
    thread_id = None
    await _set_actions_context(agent_id, mock_request, thread_id)

    # Test correctness by evaluating what was set as the current_requests_contexts
    ctx = get_current_requests_contexts()
    assert ctx is not None
    assert ctx.invocation_context is not None
    assert isinstance(ctx.invocation_context.value, dict)
    assert "agent_id" in ctx.invocation_context.value
    assert ctx.invocation_context.value["agent_id"] == agent_id
