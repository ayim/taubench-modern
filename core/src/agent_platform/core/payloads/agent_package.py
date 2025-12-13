from dataclasses import dataclass, field

from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.selected_tools import SelectedTools
from agent_platform.core.utils import SecretString


@dataclass(frozen=True)
class AgentPackagePayloadActionServer:
    url: str = field(
        metadata={
            "description": ("The URL of the action server."),
        },
    )
    """The URL of the action server."""

    api_key: str | SecretString = field(
        metadata={
            "description": ("The API key of the action server."),
        },
    )
    """The API key of the action server."""


@dataclass(frozen=True)
class AgentPackagePayloadLangsmith:
    api_key: str | SecretString = field(
        metadata={
            "description": ("The API key of the Langsmith."),
        },
    )
    """The API key of the Langsmith."""

    api_url: str = field(
        metadata={
            "description": ("The API URL of the Langsmith."),
        },
    )
    """The API URL of the Langsmith."""

    project_name: str = field(
        metadata={
            "description": ("The project name of the Langsmith."),
        },
    )
    """The project name of the Langsmith."""

    def model_dump(self) -> dict:
        return {
            "api_key": (self.api_key if isinstance(self.api_key, str) else self.api_key.get_secret_value()),
            "api_url": self.api_url,
            "project_name": self.project_name,
        }


@dataclass(frozen=True)
class AgentPackagePayload:
    name: str = field(
        metadata={
            "description": ("The name of the agent."),
        },
    )
    """The name of the agent."""

    description: str | None = field(
        default=None,
        metadata={
            "description": ("The description of the agent."),
        },
    )
    """The description of the agent."""

    public: bool = field(
        default=True,
        metadata={
            "description": ("Whether the agent is public. (Legacy, ignored.)"),
        },
    )
    """Whether the agent is public. (Legacy, ignored.)"""

    agent_package_url: str | None = field(
        default=None,
        metadata={
            "description": ("The URL of the agent package."),
        },
    )
    """The URL of the agent package."""

    agent_package_base64: str | None = field(
        default=None,
        metadata={
            "description": ("The base64 encoded agent package."),
        },
    )
    """The base64 encoded agent package."""

    # This is for backwards compatibility with existing (v1) apis.
    model: dict = field(
        default_factory=dict,
        metadata={
            "description": ("The model configuration for the agent. (Legacy field.)"),
        },
    )
    """The model configuration for the agent. (Legacy field.)"""

    platform_params_ids: list[str] = field(
        metadata={
            "description": "The IDs of platform params this agent uses.",
        },
        default_factory=list,
    )
    """The IDs of platform params this agent uses."""

    action_servers: list[AgentPackagePayloadActionServer] = field(
        default_factory=list,
        metadata={
            "description": ("The action servers for the agent."),
        },
    )
    """The action servers for the agent."""

    mcp_servers: list[MCPServer] = field(
        metadata={
            "description": "The Model Context Protocol (MCP) servers this agent uses.",
        },
        default_factory=list,
    )
    """The Model Context Protocol (MCP) servers this agent uses."""

    mcp_server_ids: list[str] = field(
        default_factory=list,
        metadata={
            "description": (
                "Global MCP server IDs to associate with the agent. If provided, "
                "they are used in addition to any inline mcp_servers."
            ),
        },
    )
    """Global MCP server IDs to associate with the agent."""

    langsmith: AgentPackagePayloadLangsmith | None = field(
        default=None,
        metadata={
            "description": ("The Langsmith configuration for the agent."),
        },
    )
    """The Langsmith configuration for the agent."""

    selected_tools: SelectedTools = field(
        metadata={
            "description": "Configuration for tools selected for this agent.",
        },
        default_factory=SelectedTools,
    )
    """Configuration for tools selected for this agent."""

    # TODO: platform_configs for v2?
