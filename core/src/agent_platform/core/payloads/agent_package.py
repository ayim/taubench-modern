from dataclasses import dataclass, field
from typing import Any, Self

from agent_platform.core.mcp.mcp_server import MCPServer
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

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Self:
        if isinstance(data, cls):
            return data

        return cls(
            url=data.get("url", ""),
            api_key=data.get("api_key", ""),
        )


# @TODO:
# deprecate AgentPackagePayloadLangsmith on AgentPackagePayload.
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

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Self:
        if isinstance(data, cls):
            return data

        return cls(
            api_key=data.get("api_key", ""),
            api_url=data.get("api_url", ""),
            project_name=data.get("project_name", ""),
        )


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
    model: dict | None = field(
        default=None,
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

    # TODO: platform_configs for v2?

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Self:
        if isinstance(data, cls):
            return data

        action_servers_raw = data.get("action_servers", [])
        mcp_servers_raw = data.get("mcp_servers", [])
        langsmith_raw: dict[str, Any] | None = data.get("langsmith", None)

        action_servers = []
        mcp_servers = []
        if action_servers_raw:
            action_servers = [
                AgentPackagePayloadActionServer.model_validate(action_server) for action_server in action_servers_raw
            ]

        if mcp_servers_raw:
            mcp_servers = [MCPServer.model_validate(mcp_server) for mcp_server in mcp_servers_raw]

        langsmith = AgentPackagePayloadLangsmith.model_validate(langsmith_raw) if langsmith_raw is not None else None

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            public=data.get("public", True),
            agent_package_url=data.get("agent_package_url", None),
            agent_package_base64=data.get("agent_package_base64", None),
            model=data.get("model", None),
            platform_params_ids=data.get("platform_params_ids", []),
            mcp_server_ids=data.get("mcp_server_ids", []),
            action_servers=action_servers,
            mcp_servers=mcp_servers,
            langsmith=langsmith,
        )
