from dataclasses import dataclass, field
from typing import Self

from agent_platform.core.mcp.mcp_client import MCPClient
from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass(frozen=True)
class MCPServer:
    """Model Context Protocol (MCP) server definition."""

    name: str = field(metadata={"description": "The name of the MCP server."})
    """The name of the MCP server."""

    url: str = field(metadata={"description": "The URL of the MCP server."})
    """The URL of the MCP server."""

    # TODO: what all do we need here? Auth/transport/etc?

    def copy(self) -> Self:
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

    async def to_tool_definitions(self) -> list[ToolDefinition]:
        """Converts the MCP server to a list of tool definitions."""
        client = MCPClient(self)
        await client.connect()
        tools = await client.list_tools()
        await client.close()
        return tools

    @classmethod
    def model_validate(cls, data: dict) -> "MCPServer":
        """Deserializes the MCP server from a dictionary.
        Useful for JSON deserialization."""
        return cls(**data)
