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
    test_env1: dict[str, MCPUnionOfVariableTypes] = {
        "VAR1": MCPVariableTypeString(value="/data", description="this"),
        "VAR2": "value2",
    }
    srv3 = MCPServer(name="test3", command="python", env=test_env1)
    assert srv3.env == test_env1

    # Test that env is preserved in model_dump
    dumped = srv3.model_dump()
    assert dumped["env"] == {
        "VAR1": {"type": "string", "description": "this", "value": "/data"},
        "VAR2": "value2",
    }

    # Test with populated env dict
    test_env2: dict[str, MCPUnionOfVariableTypes] = {
        "VAR1": MCPVariableTypeSecret(description="this"),
        "VAR2": "value2",
    }
    srv3 = MCPServer(name="test3", command="python", env=test_env2)
    assert srv3.env == test_env2

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
    test_env3: dict[str, MCPUnionOfVariableTypes] = {
        "VAR1": MCPVariableTypeOAuth2Secret(
            scopes=["user.read"], provider="Github", description="this"
        ),
        "VAR2": "value2",
    }
    srv3 = MCPServer(name="test3", command="python", env=test_env3)
    assert srv3.env == test_env3

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
    test_env4: dict[str, MCPUnionOfVariableTypes] = {
        "VAR1": MCPVariableTypeDataServerInfo(),
        "VAR2": "value2",
    }
    srv3 = MCPServer(name="test3", command="python", env=test_env4)
    assert srv3.env == test_env4

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
    assert copied.env == test_env4

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


def test_mcp_server_model_dump_and_validate_roundtrip():
    """
    Test that model_dump and model_validate are inverse operations for MCPServer,
    including all header/env types.
    """
    from agent_platform.core.mcp.mcp_types import (
        MCPVariableTypeDataServerInfo,
        MCPVariableTypeOAuth2Secret,
        MCPVariableTypeSecret,
        MCPVariableTypeString,
    )

    # Compose headers/env with all types
    all_types = {
        "KEY_WITH_VALUE": "value",
        "KEY_STRING_OBJECT": MCPVariableTypeString(value="v", description="desc"),
        "KEY_SECRET_OBJECT": MCPVariableTypeSecret(description="sdesc"),
        "KEY_OAUTH2_OBJECT": MCPVariableTypeOAuth2Secret(
            scopes=["scope1"], provider="prov", description="odesc"
        ),
        "KEY_DATA_OBJECT": MCPVariableTypeDataServerInfo(),
    }

    # URL-based server
    srv_url = MCPServer(
        name="remote-server",
        url="https://api.example.com/MCP",
        headers=all_types,
        force_serial_tool_calls=True,
        transport="streamable-http",
    )
    dumped_url = srv_url.model_dump()

    # Validate dumped_url structure and content
    assert set(dumped_url.keys()) == {
        "name",
        "transport",
        "url",
        "headers",
        "command",
        "args",
        "env",
        "cwd",
        "force_serial_tool_calls",
        "type",
        "mcp_server_metadata",
    }
    assert dumped_url["headers"] == {
        "KEY_WITH_VALUE": "value",
        "KEY_STRING_OBJECT": {"type": "string", "description": "desc", "value": "v"},
        "KEY_SECRET_OBJECT": {"type": "secret", "description": "sdesc"},
        "KEY_OAUTH2_OBJECT": {
            "type": "oauth2-secret",
            "scopes": ["scope1"],
            "provider": "prov",
            "description": "odesc",
        },
        "KEY_DATA_OBJECT": {"type": "data-server-info"},
    }
    assert dumped_url["env"] is None
    assert dumped_url["command"] is None
    assert dumped_url["args"] is None
    assert dumped_url["cwd"] is None
    assert dumped_url["url"] == "https://api.example.com/MCP"
    assert dumped_url["name"] == "remote-server"
    assert dumped_url["transport"] == "streamable-http"
    assert dumped_url["force_serial_tool_calls"] is True

    # Model validate dumped_url
    validated_url = MCPServer.model_validate(dumped_url)
    assert validated_url.name == srv_url.name
    assert validated_url.url == srv_url.url
    assert validated_url.headers == srv_url.headers
    assert validated_url.force_serial_tool_calls == srv_url.force_serial_tool_calls
    assert validated_url.transport == srv_url.transport
    assert validated_url.command is None
    assert validated_url.args is None
    assert validated_url.env is None
    assert validated_url.cwd is None

    # Command-based server
    srv_cmd = MCPServer(
        name="local-server",
        command="run-local-server",
        args=["--port", "8080"],
        env=all_types,
        cwd="/tmp",
        force_serial_tool_calls=False,
        transport="stdio",
    )
    dumped_cmd = srv_cmd.model_dump()

    # Validate dumped_cmd structure and content
    assert set(dumped_cmd.keys()) == {
        "name",
        "transport",
        "url",
        "headers",
        "command",
        "args",
        "env",
        "cwd",
        "force_serial_tool_calls",
        "type",
        "mcp_server_metadata",
    }
    assert dumped_cmd["env"] == {
        "KEY_WITH_VALUE": "value",
        "KEY_STRING_OBJECT": {"type": "string", "description": "desc", "value": "v"},
        "KEY_SECRET_OBJECT": {"type": "secret", "description": "sdesc"},
        "KEY_OAUTH2_OBJECT": {
            "type": "oauth2-secret",
            "scopes": ["scope1"],
            "provider": "prov",
            "description": "odesc",
        },
        "KEY_DATA_OBJECT": {"type": "data-server-info"},
    }
    assert dumped_cmd["headers"] is None
    assert dumped_cmd["url"] is None
    assert dumped_cmd["command"] == "run-local-server"
    assert dumped_cmd["args"] == ["--port", "8080"]
    assert dumped_cmd["cwd"] == "/tmp"
    assert dumped_cmd["name"] == "local-server"
    assert dumped_cmd["transport"] == "stdio"
    assert dumped_cmd["force_serial_tool_calls"] is False

    # Model validate dumped_cmd
    validated_cmd = MCPServer.model_validate(dumped_cmd)
    assert validated_cmd.name == srv_cmd.name
    assert validated_cmd.command == srv_cmd.command
    assert validated_cmd.args == srv_cmd.args
    assert validated_cmd.env == srv_cmd.env
    assert validated_cmd.cwd == srv_cmd.cwd
    assert validated_cmd.force_serial_tool_calls == srv_cmd.force_serial_tool_calls
    assert validated_cmd.transport == srv_cmd.transport
    assert validated_cmd.url is None
    assert validated_cmd.headers is None


def test_mcp_server_model_dump_and_validate_roundtrip_with_secrets():
    """
    Test that model_dump and model_validate are inverse operations for MCPServer,
    including all header/env types.
    """
    # Import here to avoid heavy module imports during normal use/testing
    from agent_platform.core.mcp.mcp_types import (
        MCPVariableTypeDataServerInfo,
        MCPVariableTypeOAuth2Secret,
        MCPVariableTypeSecret,
        MCPVariableTypeString,
    )

    # Compose headers/env with all types
    all_types = {
        "KEY_WITH_VALUE": "value",
        "KEY_STRING_OBJECT": MCPVariableTypeString(value="v", description="desc"),
        "KEY_SECRET_OBJECT": MCPVariableTypeSecret(description="sdesc", value="svalue"),
        "KEY_OAUTH2_OBJECT": MCPVariableTypeOAuth2Secret(
            scopes=["scope1"], provider="prov", description="odesc", value="oauth2value"
        ),
        "KEY_DATA_OBJECT": MCPVariableTypeDataServerInfo(value="datavalue"),
    }

    # URL-based server
    srv_url = MCPServer(
        name="remote-server",
        url="https://api.example.com/MCP",
        headers=all_types,
        force_serial_tool_calls=True,
        transport="streamable-http",
    )
    dumped_url = srv_url.model_dump()

    # Validate dumped_url structure and content
    assert set(dumped_url.keys()) == {
        "name",
        "transport",
        "url",
        "headers",
        "command",
        "args",
        "env",
        "cwd",
        "force_serial_tool_calls",
        "type",
        "mcp_server_metadata",
    }
    assert dumped_url["headers"] == {
        "KEY_WITH_VALUE": "value",
        "KEY_STRING_OBJECT": {"type": "string", "description": "desc", "value": "v"},
        "KEY_SECRET_OBJECT": {"type": "secret", "description": "sdesc", "value": "svalue"},
        "KEY_OAUTH2_OBJECT": {
            "type": "oauth2-secret",
            "scopes": ["scope1"],
            "provider": "prov",
            "description": "odesc",
            "value": "oauth2value",
        },
        "KEY_DATA_OBJECT": {"type": "data-server-info", "value": "datavalue"},
    }
    assert dumped_url["env"] is None
    assert dumped_url["command"] is None
    assert dumped_url["args"] is None
    assert dumped_url["cwd"] is None
    assert dumped_url["url"] == "https://api.example.com/MCP"
    assert dumped_url["name"] == "remote-server"
    assert dumped_url["transport"] == "streamable-http"
    assert dumped_url["force_serial_tool_calls"] is True

    # Model validate dumped_url
    validated_url = MCPServer.model_validate(dumped_url)
    assert validated_url.name == srv_url.name
    assert validated_url.url == srv_url.url
    assert validated_url.headers == srv_url.headers
    assert validated_url.force_serial_tool_calls == srv_url.force_serial_tool_calls
    assert validated_url.transport == srv_url.transport
    assert validated_url.command is None
    assert validated_url.args is None
    assert validated_url.env is None
    assert validated_url.cwd is None

    # Command-based server
    srv_cmd = MCPServer(
        name="local-server",
        command="run-local-server",
        args=["--port", "8080"],
        env=all_types,
        cwd="/tmp",
        force_serial_tool_calls=False,
        transport="stdio",
    )
    dumped_cmd = srv_cmd.model_dump()

    # Validate dumped_cmd structure and content
    assert set(dumped_cmd.keys()) == {
        "name",
        "transport",
        "url",
        "headers",
        "command",
        "args",
        "env",
        "cwd",
        "force_serial_tool_calls",
        "type",
        "mcp_server_metadata",
    }
    assert dumped_cmd["env"] == {
        "KEY_WITH_VALUE": "value",
        "KEY_STRING_OBJECT": {"type": "string", "description": "desc", "value": "v"},
        "KEY_SECRET_OBJECT": {"type": "secret", "description": "sdesc", "value": "svalue"},
        "KEY_OAUTH2_OBJECT": {
            "type": "oauth2-secret",
            "scopes": ["scope1"],
            "provider": "prov",
            "description": "odesc",
            "value": "oauth2value",
        },
        "KEY_DATA_OBJECT": {"type": "data-server-info", "value": "datavalue"},
    }
    assert dumped_cmd["headers"] is None
    assert dumped_cmd["url"] is None
    assert dumped_cmd["command"] == "run-local-server"
    assert dumped_cmd["args"] == ["--port", "8080"]
    assert dumped_cmd["cwd"] == "/tmp"
    assert dumped_cmd["name"] == "local-server"
    assert dumped_cmd["transport"] == "stdio"
    assert dumped_cmd["force_serial_tool_calls"] is False

    # Model validate dumped_cmd
    validated_cmd = MCPServer.model_validate(dumped_cmd)
    assert validated_cmd.name == srv_cmd.name
    assert validated_cmd.command == srv_cmd.command
    assert validated_cmd.args == srv_cmd.args
    assert validated_cmd.env == srv_cmd.env
    assert validated_cmd.cwd == srv_cmd.cwd
    assert validated_cmd.force_serial_tool_calls == srv_cmd.force_serial_tool_calls
    assert validated_cmd.transport == srv_cmd.transport
    assert validated_cmd.url is None
    assert validated_cmd.headers is None
