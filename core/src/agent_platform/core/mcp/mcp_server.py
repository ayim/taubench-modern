from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.mcp.mcp_client import MCPClient
from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass(frozen=True)
class MCPServer:
    """Model Context Protocol (MCP) server definition."""

    name: str = field(metadata={"description": "The name of the MCP server."})
    """The name of the MCP server."""

    transport: Literal["streamable-http", "sse", "stdio"] = field(
        default="streamable-http",
        metadata={"description": "Transport protocol to use when connecting to the MCP server."},
    )

    # Remote transports
    url: str | None = field(
        default=None,
        metadata={
            "description": "The URL of the MCP server. This should point directly"
            " to the transport endpoint to use."
        },
    )
    """The URL of the MCP server."""

    # Stdio transports
    command: str | None = field(
        default=None,
        metadata={
            "description": "The command to run the MCP server. "
            "If not provided, the MCP server will be assumed to be running "
            "on the local machine."
        },
    )
    """The command to run the MCP server. If not provided, the MCP server will
    be assumed to be running on the local machine."""

    args: list[str] | None = field(
        default=None, metadata={"description": "The arguments to pass to the MCP server command."}
    )
    """The arguments to pass to the MCP server command."""

    env: dict[str, str] | None = field(
        default=None,
        metadata={"description": "The environment variables to set for the MCP server command."},
    )
    """The environment variables to set for the MCP server command."""

    cwd: str | None = field(
        default=None,
        metadata={"description": "The working directory to run the MCP server command in."},
    )
    """The working directory to run the MCP server command in."""

    force_serial_tool_calls: bool = field(
        default=False,
        metadata={
            "description": "If True, all tool calls are executed under a lock "
            "to support servers that cannot interleave multiple requests."
        },
    )
    """If True, all tool calls are executed under a lock to support servers
    that cannot interleave multiple requests."""

    kind: Literal["stdio", "remote", "unknown"] = field(
        default="unknown",
        metadata={"description": "The kind of MCP server."},
        init=False,
    )
    """The kind of MCP server."""

    def __post_init__(self):
        if self.url is None and self.command is None:
            raise ValueError("Either url or command must be provided")

        have_url = self.url is not None
        have_cmd = self.command is not None
        if have_url == have_cmd:
            raise ValueError("Provide *either* url=* or command=*, but not both")

        # Force set kind based on presence of url or command
        if have_url:
            object.__setattr__(self, "kind", "remote")
        elif have_cmd:
            object.__setattr__(self, "kind", "stdio")
            if self.transport != "stdio":
                object.__setattr__(self, "transport", "stdio")
        if have_url and self.transport == "stdio":
            raise ValueError("'stdio' transport requires command=")

    @property
    def is_stdio(self) -> bool:
        return self.kind == "stdio"

    @property
    def cache_key(self) -> str:
        if self.url:
            return self.url
        if self.command:
            env_part = tuple(sorted((self.env or {}).items()))
            cwd_part = self.cwd or ""
            args_part = " ".join(self.args or [])
            return f"{self.command}|{args_part}|{cwd_part}|{env_part}"
        raise ValueError("No cache key for MCP server")

    def copy(self) -> "MCPServer":
        """Returns a deep copy of the MCP server."""
        return MCPServer(
            name=self.name,
            url=self.url,
            command=self.command,
            args=self.args,
            env=self.env,
            cwd=self.cwd,
            force_serial_tool_calls=self.force_serial_tool_calls,
            transport=self.transport,
        )

    def model_dump(self) -> dict:
        """Serializes the MCP server to a dictionary.
        Useful for JSON serialization."""
        return {
            "name": self.name,
            "url": self.url,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "cwd": self.cwd,
            "force_serial_tool_calls": self.force_serial_tool_calls,
            "transport": self.transport,
        }

    async def to_tool_definitions(
        self,
        # Additional headers to be added to the request at
        # tool definition time
        # NOTE: MCP doesn't really seem to support this at the moment...
        additional_headers: dict | None = None,
    ) -> list[ToolDefinition]:
        """Converts the MCP server to a list of tool definitions."""
        async with MCPClient(self) as client:
            tools = await client.list_tools()
        return tools

    @classmethod
    def model_validate(cls, data: dict) -> "MCPServer":
        """Deserializes the MCP server from a dictionary.
        Useful for JSON deserialization."""
        return cls(**data)
