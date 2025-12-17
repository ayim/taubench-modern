"""SelectedTools: Configuration for tools selected for an agent."""

from dataclasses import dataclass, field


@dataclass
class SelectedToolConfig:
    """Configuration for a single selected tool.

    This structure is designed to be extensible in the future to support
    additional metadata such as tool-specific settings, permissions, or
    MCP server-specific configurations.
    """

    name: str = field(
        metadata={
            "description": "The name of the selected tool.",
        },
    )
    """The name of the selected tool."""

    def model_dump(self) -> dict:
        """Serialize the SelectedToolConfig to a dictionary."""
        return {
            "name": self.name,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "SelectedToolConfig":
        """Create a SelectedToolConfig instance from a dictionary."""
        name = data.get("name", "")
        return cls(name=name)


@dataclass
class SelectedTools:
    """Configuration for tools selected for an agent.

    This structure is designed to be extensible in the future to support
    more complex tool access patterns such as MCP server-specific tool
    mappings or tool-specific configurations.
    """

    tools: list[SelectedToolConfig] = field(
        metadata={
            "description": "List of selected tool configurations for this agent.",
        },
        default_factory=list,
    )
    """List of selected tool configurations for this agent."""

    def model_dump(self) -> dict:
        """Serialize the SelectedTools to a dictionary."""
        return {
            "tools": [tool.model_dump() for tool in self.tools],
        }

    @classmethod
    def model_validate(cls, data: dict) -> "SelectedTools":
        """Create a SelectedTools instance from a dictionary."""
        tools_data = data.get("tools", [])
        # Handle None values by defaulting to empty list
        if tools_data is None:
            tools_data = []

        # Handle both old format (list of strings) and new format (list of objects)
        tool_configs = []
        for item in tools_data:
            if isinstance(item, str):
                # Legacy format: list of strings
                tool_configs.append(SelectedToolConfig(name=item))
            elif isinstance(item, dict):
                # New format: list of objects
                tool_configs.append(SelectedToolConfig.model_validate(item))
            else:
                # Handle SelectedToolConfig objects directly
                tool_configs.append(item)

        return cls(tools=tool_configs)
