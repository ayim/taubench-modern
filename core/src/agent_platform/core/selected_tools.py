"""SelectedTools: Configuration for tools selected for an agent."""

from dataclasses import dataclass, field


@dataclass
class SelectedToolConfig:
    """Configuration for a single selected tool.

    This structure is designed to be extensible in the future to support
    additional metadata such as tool-specific settings, permissions, or
    MCP server-specific configurations.
    """

    tool_name: str = field(
        metadata={
            "description": "The name of the selected tool.",
        },
    )
    """The name of the selected tool."""

    def model_dump(self) -> dict:
        """Serialize the SelectedToolConfig to a dictionary."""
        return {
            "tool_name": self.tool_name,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "SelectedToolConfig":
        """Create a SelectedToolConfig instance from a dictionary."""
        tool_name = data.get("tool_name", "")
        return cls(tool_name=tool_name)


@dataclass
class SelectedTools:
    """Configuration for tools selected for an agent.

    This structure is designed to be extensible in the future to support
    more complex tool access patterns such as MCP server-specific tool
    mappings or tool-specific configurations.
    """

    tool_names: list[SelectedToolConfig] = field(
        metadata={
            "description": "List of selected tool configurations for this agent.",
        },
        default_factory=list,
    )
    """List of selected tool configurations for this agent."""

    def model_dump(self) -> dict:
        """Serialize the SelectedTools to a dictionary."""
        return {
            "tool_names": [tool.model_dump() for tool in self.tool_names],
        }

    @classmethod
    def model_validate(cls, data: dict) -> "SelectedTools":
        """Create a SelectedTools instance from a dictionary."""
        tool_names_data = data.get("tool_names", [])
        # Handle None values by defaulting to empty list
        if tool_names_data is None:
            tool_names_data = []

        # Handle both old format (list of strings) and new format (list of objects)
        tool_configs = []
        for item in tool_names_data:
            if isinstance(item, str):
                # Legacy format: list of strings
                tool_configs.append(SelectedToolConfig(tool_name=item))
            elif isinstance(item, dict):
                # New format: list of objects
                tool_configs.append(SelectedToolConfig.model_validate(item))
            else:
                # Handle SelectedToolConfig objects directly
                tool_configs.append(item)

        return cls(tool_names=tool_configs)
