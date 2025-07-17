import pytest

from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.mcp.mcp_types import (
    MCPUnionOfVariableTypes,
    MCPVariableTypeDataServerInfo,
    MCPVariableTypeOAuth2Secret,
    MCPVariableTypeSecret,
    MCPVariableTypeString,
)

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


def test_mcp_server_env_handling():
    """Test that MCPServer properly handles environment variables."""
    # Test with None env
    srv1 = MCPServer(name="test1", command="python", env=None)
    assert srv1.env is None

    # Test with empty env dict
    srv2 = MCPServer(name="test2", command="python", env={})
    assert srv2.env == {}

    # Test with populated env dict
    test_env: dict[str, MCPUnionOfVariableTypes] = {"VAR1": "value1", "VAR2": "value2"}
    srv3 = MCPServer(name="test3", command="python", env=test_env)
    assert srv3.env == test_env

    # Test that env is preserved in model_dump
    dumped = srv3.model_dump()
    assert dumped["env"] == {"VAR1": "value1", "VAR2": "value2"}

    # Test with populated env dict
    test_env: dict[str, MCPUnionOfVariableTypes] = {
        "VAR1": MCPVariableTypeString(default="/data", description="this"),
        "VAR2": "value2",
    }
    srv3 = MCPServer(name="test3", command="python", env=test_env)
    assert srv3.env == test_env

    # Test that env is preserved in model_dump
    dumped = srv3.model_dump()
    assert dumped["env"] == {
        "VAR1": {"type": "string", "description": "this", "default": "/data"},
        "VAR2": "value2",
    }

    # Test with populated env dict
    test_env: dict[str, MCPUnionOfVariableTypes] = {
        "VAR1": MCPVariableTypeSecret(description="this"),
        "VAR2": "value2",
    }
    srv3 = MCPServer(name="test3", command="python", env=test_env)
    assert srv3.env == test_env

    # Test that env is preserved in model_dump
    dumped = srv3.model_dump()
    assert dumped["env"] == {
        "VAR1": {
            "type": "secret",
            "description": "this",
        },
        "VAR2": "value2",
    }

    # Test with populated env dict
    test_env: dict[str, MCPUnionOfVariableTypes] = {
        "VAR1": MCPVariableTypeOAuth2Secret(
            scopes=["user.read"], provider="Github", description="this"
        ),
        "VAR2": "value2",
    }
    srv3 = MCPServer(name="test3", command="python", env=test_env)
    assert srv3.env == test_env

    # Test that env is preserved in model_dump
    dumped = srv3.model_dump()
    assert dumped["env"] == {
        "VAR1": {
            "type": "oauth2-secret",
            "description": "this",
            "provider": "Github",
            "scopes": ["user.read"],
        },
        "VAR2": "value2",
    }

    # Test with populated env dict
    test_env: dict[str, MCPUnionOfVariableTypes] = {
        "VAR1": MCPVariableTypeDataServerInfo(),
        "VAR2": "value2",
    }
    srv3 = MCPServer(name="test3", command="python", env=test_env)
    assert srv3.env == test_env

    # Test that env is preserved in model_dump
    dumped = srv3.model_dump()
    assert dumped["env"] == {
        "VAR1": {
            "type": "data-server-info",
        },
        "VAR2": "value2",
    }

    # Test that env is preserved in copy
    copied = srv3.copy()
    assert copied.env == test_env

    # Test that env is preserved in model_validate
    validated = MCPServer.model_validate(dumped)
    assert validated.env == {
        "VAR1": MCPVariableTypeDataServerInfo(),
        "VAR2": "value2",
    }


def test_mcp_server_cache_key_includes_env():
    """Test that cache key includes environment variables for stdio servers."""
    # Two servers with same command/args but different env should have different cache keys
    srv1 = MCPServer(
        name="test1", command="python", args=["-c", "print('hello')"], env={"VAR1": "value1"}
    )

    srv2 = MCPServer(
        name="test2",
        command="python",
        args=["-c", "print('hello')"],
        env={"VAR1": "value2"},  # Different env value
    )

    srv3 = MCPServer(
        name="test3",
        command="python",
        args=["-c", "print('hello')"],
        env={"VAR2": "value1"},  # Different env key
    )

    srv4 = MCPServer(
        name="test4",
        command="python",
        args=["-c", "print('hello')"],
        env=None,  # No env
    )

    # All should have different cache keys
    cache_keys = [srv1.cache_key, srv2.cache_key, srv3.cache_key, srv4.cache_key]
    assert len(set(cache_keys)) == 4, "All servers should have unique cache keys"

    # Server with same env should have same cache key
    srv5 = MCPServer(
        name="test5",  # Different name shouldn't affect cache key
        command="python",
        args=["-c", "print('hello')"],
        env={"VAR1": "value1"},
    )

    assert srv1.cache_key == srv5.cache_key, "Servers with same config should have same cache key"
