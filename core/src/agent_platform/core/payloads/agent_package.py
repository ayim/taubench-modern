from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class AgentPackagePayload:
    name: str = field(
        metadata={
            "description": ("The name of the agent."),
        },
    )
    """The name of the agent."""

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

    action_servers: list[AgentPackagePayloadActionServer] = field(
        default_factory=list,
        metadata={
            "description": ("The action servers for the agent."),
        },
    )
    """The action servers for the agent."""

    langsmith: AgentPackagePayloadLangsmith | None = field(
        default=None,
        metadata={
            "description": ("The Langsmith configuration for the agent."),
        },
    )
    """The Langsmith configuration for the agent."""

    # TODO: mcp and platform_configs for v2?
