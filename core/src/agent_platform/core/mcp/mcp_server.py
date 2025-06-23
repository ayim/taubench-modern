from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.mcp.mcp_client import MCPClient
from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass(frozen=True)
class MCPServer:
    """Model Context Protocol (MCP) server definition."""

    name: str = field(metadata={"description": "The name of the MCP server."})
    """The name of the MCP server."""

    transport: Literal["auto", "streamable-http", "sse", "stdio"] = field(
        default="auto",
        metadata={
            "description": "Transport protocol to use when connecting to the MCP server. "
            "Auto defaults to streamable-http unless sse is in the url; if there is no url, "
            "defaults to stdio."
        },
    )
    """Transport protocol to use when connecting to the MCP server.
    Auto defaults to streamable-http unless sse is in the url; if there is no url,
    defaults to stdio."""

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

    def __post_init__(self):
        # If neither url nor command are provided, raise an error
        if not self.url and not self.command:
            raise ValueError("Either url or command must be provided")

        # If both url and command are provided, raise an error
        if self.url and self.command:
            raise ValueError("Provide *either* url=* or command=*, but not both")

        # When in auto mode
        if self.transport == "auto":
            if self.url and "/sse" in self.url.lower():
                # If "sse" is in the url, use sse
                object.__setattr__(self, "transport", "sse")
            elif self.url:
                # Otherwise, use streamable-http (default when url set)
                object.__setattr__(self, "transport", "streamable-http")
            elif self.command:
                # Otherwise, use stdio (default when no url or command)
                object.__setattr__(self, "transport", "stdio")

        # If url is provided, we must be sse or streamble-http
        if self.url and self.transport not in ["sse", "streamable-http"]:
            raise ValueError("'url' transport requires transport=sse or transport=streamable-http")

        # If command is provided, we must be stdio
        if self.command and self.transport != "stdio":
            raise ValueError("'command' transport requires transport=stdio")

    @property
    def is_stdio(self) -> bool:
        """Return True if this server uses the stdio transport.

        Historically the decision was based on the internal *kind* attribute,
        but since the transport value is now fully validated during
        ``__post_init__`` we can simply look at the effective ``transport``.
        """
        return self.transport == "stdio"

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
