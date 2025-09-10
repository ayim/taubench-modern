from urllib.parse import urlparse

import pytest
from starlette.requests import Request


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
