from dataclasses import dataclass, field

from agent_platform.core.mcp.mcp_client import MCPClient
from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass(frozen=True)
class MCPServer:
    """Model Context Protocol (MCP) server definition."""

    name: str = field(metadata={"description": "The name of the MCP server."})
    """The name of the MCP server."""

    url: str = field(
        metadata={
            "description": "The URL of the MCP server. Prefer to NOT "
            "include the /mcp or /sse suffixes as the client will try "
            "to negotiate the transport automatically."
        }
    )
    """The URL of the MCP server. Prefer to NOT include the /mcp or /sse
    suffixes as the client will try to negotiate the transport automatically."""

    # TODO: what all do we need here? Auth/transport/etc?

    def copy(self) -> "MCPServer":
        """Returns a deep copy of the MCP server."""
        return MCPServer(
            name=self.name,
            url=self.url,
        )

    def model_dump(self) -> dict:
        """Serializes the MCP server to a dictionary.
        Useful for JSON serialization."""
        return {
            "name": self.name,
            "url": self.url,
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
            tools = await client.list_tools(additional_headers)
        return tools

    @classmethod
    def model_validate(cls, data: dict) -> "MCPServer":
        """Deserializes the MCP server from a dictionary.
        Useful for JSON deserialization."""
        return cls(**data)
