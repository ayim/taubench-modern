"""Response payloads for MCP server endpoints."""

from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.agent_package.metadata.agent_metadata import AgentPackageMetadata
from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.core.mcp.mcp_types import MCPVariables

MCPServerType = Literal["generic_mcp", "sema4ai_action_server"]
MCPTransport = Literal["auto", "streamable-http", "sse", "stdio"]


@dataclass(frozen=True)
class MCPServerResponse:
    """Response model for MCP server endpoints that includes ID and source."""

    mcp_server_id: str = field(metadata={"description": "The unique identifier of the MCP server."})
    """The unique identifier of the MCP server."""

    source: MCPServerSource = field(metadata={"description": "The source of the MCP server (FILE or API)."})
    """The source of the MCP server (FILE or API)."""

    # MCP Server fields
    name: str = field(metadata={"description": "The name of the MCP server."})
    """The name of the MCP server."""

    transport: MCPTransport = field(
        metadata={"description": "Transport protocol to use when connecting to the MCP server."}
    )
    """Transport protocol to use when connecting to the MCP server."""

    url: str | None = field(default=None, metadata={"description": "The URL of the MCP server."})
    """The URL of the MCP server."""

    headers: MCPVariables | None = field(
        default=None,
        metadata={"description": "Headers used for configuring requests & connections to the MCP server."},
    )
    """Headers used for configuring requests & connections to the MCP server."""

    command: str | None = field(default=None, metadata={"description": "The command to run the MCP server."})
    """The command to run the MCP server."""

    args: list[str] | None = field(
        default=None, metadata={"description": "The arguments to pass to the MCP server command."}
    )
    """The arguments to pass to the MCP server command."""

    env: MCPVariables | None = field(
        default=None,
        metadata={"description": "Environment variables to merge with agent-server's env vars."},
    )
    """Environment variables to merge with agent-server's env vars."""

    cwd: str | None = field(
        default=None,
        metadata={"description": "Working directory to run the MCP server command in."},
    )
    """Working directory to run the MCP server command in."""

    type: MCPServerType = field(
        default="generic_mcp",
        metadata={"description": "The type of MCP server."},
    )
    """The type of MCP server."""

    force_serial_tool_calls: bool = field(
        default=False,
        metadata={"description": "If true, all tool calls are executed under a lock."},
    )
    """If true, all tool calls are executed under a lock."""

    is_hosted: bool = field(
        default=False,
        metadata={
            "description": "Whether this MCP server is hosted on our MCP Runtime. "
            "True for servers deployed via agent package upload."
        },
    )
    """Whether this MCP server is hosted on our MCP Runtime."""

    mcp_server_metadata: AgentPackageMetadata | None = field(
        default=None,
        metadata={
            "description": "Metadata from agent package inspection for hosted MCP servers. "
            "Contains action packages, secrets, and other package information."
        },
    )
    """Metadata from agent package inspection for hosted MCP servers."""

    @classmethod
    def from_mcp_server(
        cls,
        mcp_server_id: str,
        source: MCPServerSource,
        mcp_server: MCPServer,
        is_hosted: bool = False,
    ) -> "MCPServerResponse":
        """Create MCPServerResponse from MCP server data."""
        metadata = None
        if mcp_server.mcp_server_metadata is not None:
            metadata = AgentPackageMetadata.model_validate(mcp_server.mcp_server_metadata)

        return cls(
            mcp_server_id=mcp_server_id,
            source=source,
            name=mcp_server.name,
            transport=mcp_server.transport,
            url=mcp_server.url,
            headers=mcp_server.headers,
            command=mcp_server.command,
            args=mcp_server.args,
            env=mcp_server.env,
            cwd=mcp_server.cwd,
            type=mcp_server.type,
            force_serial_tool_calls=mcp_server.force_serial_tool_calls,
            is_hosted=is_hosted,
            mcp_server_metadata=metadata,
        )
