import pytest

from agent_platform.core.mcp.mcp_server import MCPServer

# ---------------------------------------------------------------------------
#  Error cases
# ---------------------------------------------------------------------------


def test_missing_url_and_command_raises() -> None:
    """Neither *url* nor *command* supplied --> ValueError."""
    with pytest.raises(ValueError, match="Either url or command must be provided"):
        MCPServer(name="missing")  # type: ignore[arg-type]


def test_both_url_and_command_raises() -> None:
    """Supplying both *url* and *command* is invalid."""
    with pytest.raises(ValueError, match="Provide \\*either\\* url=.* or command=.*"):
        MCPServer(name="both", url="http://x", command="foo")


def test_invalid_transport_for_url() -> None:
    """A remote URL cannot use the *stdio* transport."""
    with pytest.raises(ValueError, match="requires transport=sse or transport=streamable-http"):
        MCPServer(name="bad", url="http://x", transport="stdio")  # type: ignore[arg-type]


def test_invalid_transport_for_command() -> None:
    """A local command must use the *stdio* transport."""
    with pytest.raises(ValueError, match="requires transport=stdio"):
        MCPServer(name="bad", command="foo", transport="sse")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
#  Auto-detection matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected_transport"),
    [
        ("http://host/sse", "sse"),  # explicit /sse endpoint --> SSE
        ("https://api.example.com/MCP", "streamable-http"),  # any other path --> streamable
        ("HTTP://HOST/SSE", "sse"),  # case-insensitive suffix check
    ],
)
def test_auto_transport_remote(url: str, expected_transport: str) -> None:
    srv = MCPServer(name="remote", url=url)  # default transport="auto"
    assert srv.transport == expected_transport
    # Remote endpoints are never stdio
    assert not srv.is_stdio


def test_auto_transport_stdio() -> None:
    srv = MCPServer(name="local", command="run")  # auto transport
    assert srv.transport == "stdio"
    assert srv.is_stdio


# ---------------------------------------------------------------------------
#  Explicit happy paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "expected_transport", "expects_stdio"),
    [
        ({"url": "http://x", "transport": "streamable-http"}, "streamable-http", False),
        ({"url": "http://x/sse", "transport": "sse"}, "sse", False),
        ({"command": "run", "transport": "stdio"}, "stdio", True),
    ],
)
def test_explicit_valid_combinations(kwargs, expected_transport, expects_stdio):
    srv = MCPServer(name="explicit", **kwargs)
    assert srv.transport == expected_transport
    assert srv.is_stdio is expects_stdio
