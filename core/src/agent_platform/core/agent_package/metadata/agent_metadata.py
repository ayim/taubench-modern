from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.selected_tools import SelectedTools

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# Type aliases to match Go AgentServer types
AgentArchitecture = Literal["agent", "plan_execute"]
AgentReasoning = Literal["disabled", "enabled", "verbose"]
AgentModelProvider = Literal["OpenAI", "Azure", "Anthropic", "Google", "Amazon", "Ollama"]
MCPTransport = Literal["auto", "streamable-http", "sse", "stdio"]


@dataclass(frozen=True)
class ActionSecretDefinition:
    """Definition of a secret required by an action."""

    type: str = field(metadata={"description": "The type of the secret."})
    """The type of the secret."""

    description: str = field(default="", metadata={"description": "Description of the secret."})
    """Description of the secret."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"type": self.type, "description": self.description}

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionSecretDefinition":
        """Create from dictionary."""
        if data is None:
            return cls(type="", description="")
        return cls(
            type=data.get("type", ""),
            description=data.get("description", ""),
        )


@dataclass(frozen=True)
class ActionSecretsConfig:
    """Configuration of secrets for a specific action."""

    action: str = field(metadata={"description": "The name of the action."})
    """The name of the action."""

    action_package: str = field(default="", metadata={"description": "The name of the action package."})
    """The name of the action package."""

    secrets: dict[str, ActionSecretDefinition] = field(
        default_factory=dict,
        metadata={"description": "Map of secret name to secret definition."},
    )
    """Map of secret name to secret definition."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action": self.action,
            "action_package": self.action_package,
            "secrets": {k: v.model_dump() for k, v in self.secrets.items()},
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionSecretsConfig":
        """Create from dictionary."""
        if data is None:
            return cls(action="", action_package="", secrets={})

        secrets_data = data.get("secrets", {})
        secrets = {k: ActionSecretDefinition.model_validate(v) for k, v in secrets_data.items()}

        return cls(
            action=data.get("action", ""),
            action_package=data.get("actionPackage", data.get("action_package", "")),
            secrets=secrets,
        )


@dataclass(frozen=True)
class SpecAgentModel:
    """Agent model specification matching SpecAgentModel from Go."""

    provider: AgentModelProvider | None = field(default=None, metadata={"description": "The LLM provider."})
    """The LLM provider."""

    name: str | None = field(default=None, metadata={"description": "The LLM model name."})
    """The LLM model name."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "provider": self.provider,
            "name": self.name,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "SpecAgentModel":
        """Create from dictionary or return existing instance."""
        if data is None:
            return cls(provider=None, name=None)

        # If data is already a SpecAgentModel instance, return it as-is
        if isinstance(data, cls):
            return data

        # If data is a dictionary, create a new instance
        if isinstance(data, dict):
            return cls(
                provider=data.get("provider", None),
                name=data.get("name", None),
            )


@dataclass(frozen=True)
class AgentPackageMetadataKnowledge:
    """Knowledge metadata for agent packages."""

    embedded: bool = field(metadata={"description": "Whether the knowledge is embedded."})
    """Whether the knowledge is embedded."""

    name: str = field(metadata={"description": "The name of the knowledge."})
    """The name of the knowledge."""

    digest: str = field(metadata={"description": "The digest of the knowledge."})
    """The digest of the knowledge."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "embedded": self.embedded,
            "name": self.name,
            "digest": self.digest,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageMetadataKnowledge":
        """Create from dictionary or return existing instance."""
        if data is None:
            return cls(embedded=False, name="", digest="")

        # If data is already a AgentPackageMetadataKnowledge instance, return it as-is
        if isinstance(data, cls):
            return data
        return cls(
            embedded=data.get("embedded", False),
            name=data.get("name", ""),
            digest=data.get("digest", ""),
        )


@dataclass(frozen=True)
class AgentPackageDatasource:
    """Datasource configuration for agent packages."""

    customer_facing_name: str = field(metadata={"description": "Customer-facing name of the datasource."})
    """Customer-facing name of the datasource."""

    engine: str = field(metadata={"description": "The engine of the datasource."})
    """The engine of the datasource."""

    description: str = field(metadata={"description": "Description of the datasource."})
    """Description of the datasource."""

    configuration: dict[str, Any] = field(
        default_factory=dict, metadata={"description": "Configuration of the datasource."}
    )
    """Configuration of the datasource."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "customer_facing_name": self.customer_facing_name,
            "engine": self.engine,
            "description": self.description,
            "configuration": self.configuration,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageDatasource":
        """Create from dictionary."""
        if data is None:
            return cls(customer_facing_name="", engine="", description="", configuration={})

        if isinstance(data, cls):
            return data

        return cls(
            customer_facing_name=data.get("customer_facing_name", ""),
            engine=data.get("engine", ""),
            description=data.get("description", ""),
            configuration=data.get("configuration", {}),
        )


@dataclass(frozen=True)
class AgentPackageMcpServerVariable:
    """MCP server variable that can be either a simple value or object with metadata."""

    # Simple string value (when it's just a scalar)
    value: str | None = field(default=None, metadata={"description": "Simple string value for the variable."})
    """Simple string value for the variable."""

    # Object form fields
    type: str = field(default="", metadata={"description": "The type of the variable."})
    """The type of the variable."""

    description: str = field(default="", metadata={"description": "Description of the variable."})
    """Description of the variable."""

    provider: str = field(default="", metadata={"description": "OAuth2 provider name."})
    """OAuth2 provider name."""

    scopes: list[str] = field(default_factory=list, metadata={"description": "OAuth2 scopes."})
    """OAuth2 scopes."""

    def has_raw_value(self) -> bool:
        """Check if this should be treated as a raw string value."""
        return (
            self.type == ""
            and self.description == ""
            and self.provider == ""
            and len(self.scopes) == 0
            and self.value is not None
        )

    def model_dump(self) -> dict[str, Any] | str:
        """Serialize to dictionary or string."""
        if self.has_raw_value() and self.value is not None:
            return self.value
        return {
            "type": self.type,
            "description": self.description,
            "provider": self.provider,
            "scopes": self.scopes,
            "value": self.value,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | str | None) -> "AgentPackageMcpServerVariable":
        """Create from dictionary or string."""
        if data is None:
            return cls(value=None, type="", description="", provider="", scopes=[])

        if isinstance(data, str):
            return cls(value=data)
        return cls(
            type=data.get("type", ""),
            description=data.get("description", ""),
            provider=data.get("provider", ""),
            scopes=data.get("scopes", []),
            value=data.get("value", None),
        )


@dataclass(frozen=True)
class AgentPackageMcpServer:
    """MCP server configuration for agent packages."""

    name: str = field(metadata={"description": "The name of the MCP server."})
    """The name of the MCP server."""

    transport: MCPTransport = field(default="auto", metadata={"description": "Transport protocol for the MCP server."})
    """Transport protocol for the MCP server."""

    description: str = field(default="", metadata={"description": "Description of the MCP server."})
    """Description of the MCP server."""

    url: str = field(default="", metadata={"description": "URL of the MCP server."})
    """URL of the MCP server."""

    headers: dict[str, AgentPackageMcpServerVariable] = field(
        default_factory=dict, metadata={"description": "Headers for the MCP server."}
    )
    """Headers for the MCP server."""

    command: str = field(default="", metadata={"description": "Command to run the MCP server."})
    """Command to run the MCP server."""

    arguments: list[str] = field(
        default_factory=list, metadata={"description": "Arguments for the MCP server command."}
    )
    """Arguments for the MCP server command."""

    env: dict[str, AgentPackageMcpServerVariable] = field(
        default_factory=dict, metadata={"description": "Environment variables for the MCP server."}
    )
    """Environment variables for the MCP server."""

    cwd: str = field(default="", metadata={"description": "Working directory for the MCP server."})
    """Working directory for the MCP server."""

    force_serial_tool_calls: bool = field(
        default=False, metadata={"description": "Whether to force serial tool calls."}
    )
    """Whether to force serial tool calls."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "transport": self.transport,
            "description": self.description,
            "url": self.url,
            "headers": {k: v.model_dump() for k, v in self.headers.items()},
            "command": self.command,
            "args": self.arguments,
            "env": {k: v.model_dump() for k, v in self.env.items()},
            "cwd": self.cwd,
            "force_serial_tool_calls": self.force_serial_tool_calls,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageMcpServer":
        """Create from dictionary."""
        if data is None:
            return cls(
                name="",
                transport="auto",
                description="",
                url="",
                headers={},
                command="",
                arguments=[],
                env={},
                cwd="",
                force_serial_tool_calls=False,
            )

        if isinstance(data, cls):
            return data

        data = data.copy()

        # Handle headers
        if "headers" in data:
            headers = {}
            for k, v in data["headers"].items():
                headers[k] = AgentPackageMcpServerVariable.model_validate(v)
            data["headers"] = headers

        # Handle env
        if "env" in data:
            env = {}
            for k, v in data["env"].items():
                env[k] = AgentPackageMcpServerVariable.model_validate(v)
            data["env"] = env

        # Handle args vs arguments naming difference
        if "args" in data:
            data["arguments"] = data.pop("args")

        return cls(
            name=data.get("name", ""),
            transport=data.get("transport", "auto"),
            description=data.get("description", ""),
            url=data.get("url", ""),
            headers=data.get("headers", {}),
        )


@dataclass(frozen=True)
class DockerCatalogRegistryEntries:
    """Docker catalog registry entries."""

    tools: list[str] = field(default_factory=list, metadata={"description": "List of tools."})
    """List of tools."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"tools": self.tools}

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "DockerCatalogRegistryEntries":
        """Create from dictionary."""
        if data is None:
            return cls(tools=[])

        if isinstance(data, cls):
            return data

        return cls(**data)


@dataclass(frozen=True)
class AgentPackageDockerMcpGateway:
    """Docker MCP Gateway configuration for agent packages."""

    catalog: str | None = field(default=None, metadata={"description": "Path to the catalog file."})
    """Path to the catalog file."""

    servers: DockerCatalogRegistryEntries = field(
        default_factory=DockerCatalogRegistryEntries,
        metadata={"description": "Server configurations."},
    )
    """Server configurations."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "catalog": self.catalog,
            "servers": self.servers.model_dump(),
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageDockerMcpGateway":
        """Create from dictionary."""
        if data is None:
            return cls(catalog=None, servers=DockerCatalogRegistryEntries())

        if isinstance(data, cls):
            return data

        data = data.copy()
        if "servers" in data:
            data["servers"] = DockerCatalogRegistryEntries.model_validate(data["servers"])
        return cls(
            catalog=data.get("catalog", None),
            servers=data.get("servers", DockerCatalogRegistryEntries()),
        )


@dataclass(frozen=True)
class DockerMcpGatewayChanges:
    """Changes to Docker MCP Gateway configuration."""

    # This is a placeholder - the exact structure would depend on the Go definition
    # which wasn't fully visible in the provided code
    changes: dict[str, Any] = field(
        default_factory=dict, metadata={"description": "Changes to the Docker MCP Gateway."}
    )
    """Changes to the Docker MCP Gateway."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return self.changes

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "DockerMcpGatewayChanges":
        """Create from dictionary."""
        if data is None:
            return cls(changes={})

        if isinstance(data, cls):
            return data

        return cls(changes=data.get("changes", {}))


@dataclass(frozen=True)
class ExternalEndpointRule:
    """External endpoint rule configuration."""

    host: str = field(metadata={"description": "The host for the rule."})
    """The host for the rule."""

    port: int = field(metadata={"description": "The port for the rule."})
    """The port for the rule."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ExternalEndpointRule":
        """Create from dictionary."""
        if data is None:
            return cls(host="", port=0)

        if isinstance(data, cls):
            return data

        return cls(
            host=data.get("host", ""),
            port=data.get("port", 0),
        )


@dataclass(frozen=True)
class ExternalEndpoint:
    """External endpoint configuration."""

    name: str = field(metadata={"description": "The name of the endpoint."})
    """The name of the endpoint."""

    description: str = field(metadata={"description": "Description of the endpoint."})
    """Description of the endpoint."""

    additional_info_link: str = field(metadata={"description": "Additional information link."})
    """Additional information link."""

    rules: list[ExternalEndpointRule] = field(default_factory=list, metadata={"description": "Rules for the endpoint."})
    """Rules for the endpoint."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "additional-info-link": self.additional_info_link,
            "rules": [rule.model_dump() for rule in self.rules],
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ExternalEndpoint":
        """Create from dictionary."""
        if data is None:
            return cls(name="", description="", additional_info_link="", rules=[])

        if isinstance(data, cls):
            return data

        data = data.copy()

        # Handle rules
        if "rules" in data:
            rules = [ExternalEndpointRule.model_validate(rule) for rule in data["rules"]]
            data["rules"] = rules

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            additional_info_link=data.get("additional-info-link", ""),
            rules=data.get("rules", []),
        )


@dataclass(frozen=True)
class ActionPackageMetadataAction:
    """Action metadata within an action package."""

    description: str = field(metadata={"description": "Description of the action."})
    """Description of the action."""

    name: str = field(metadata={"description": "Name of the action."})
    """Name of the action."""

    summary: str = field(metadata={"description": "Summary of the action."})
    """Summary of the action."""

    operation_kind: str = field(metadata={"description": "Operation kind of the action."})
    """Operation kind of the action."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "description": self.description,
            "name": self.name,
            "summary": self.summary,
            "operation_kind": self.operation_kind,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionPackageMetadataAction":
        """Create from dictionary."""
        if data is None:
            return cls(description="", name="", summary="", operation_kind="")

        if isinstance(data, cls):
            return data

        return cls(
            description=data.get("description", ""),
            name=data.get("name", ""),
            summary=data.get("summary", ""),
            operation_kind=data.get("operation_kind", ""),
        )


@dataclass(frozen=True)
class ActionPackageMetadata:
    """Action package metadata."""

    name: str = field(metadata={"description": "Name of the action package."})
    """Name of the action package."""

    description: str = field(metadata={"description": "Description of the action package."})
    """Description of the action package."""

    version: str = field(metadata={"description": "Version of the action package."})
    """Version of the action package."""

    secrets: dict[str, ActionSecretsConfig] = field(
        default_factory=dict,
        metadata={"description": "Secrets configuration per action."},
    )
    """Secrets configuration per action."""

    actions: list[ActionPackageMetadataAction] = field(
        default_factory=list, metadata={"description": "Actions in the package."}
    )
    """Actions in the package."""

    external_endpoints: list[ExternalEndpoint] = field(
        default_factory=list, metadata={"description": "External endpoints."}
    )
    """External endpoints."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "secrets": {k: v.model_dump() for k, v in self.secrets.items()},
            "action_package_version": self.version,
            "actions": [action.model_dump() for action in self.actions],
            "external-endpoints": [endpoint.model_dump() for endpoint in self.external_endpoints],
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionPackageMetadata":
        """Create from dictionary."""
        if data is None:
            return cls(name="", description="", version="", secrets={}, actions=[], external_endpoints=[])

        if isinstance(data, cls):
            return data

        data = data.copy()

        # Handle version field naming
        if "action_package_version" in data:
            data["version"] = data.pop("action_package_version")

        # Handle external endpoints naming
        if "external-endpoints" in data:
            endpoints = [ExternalEndpoint.model_validate(ep) for ep in data["external-endpoints"]]
            data["external_endpoints"] = endpoints
            del data["external-endpoints"]

        # Handle actions
        if "actions" in data:
            actions = [ActionPackageMetadataAction.model_validate(action) for action in data["actions"]]
            data["actions"] = actions

        # Handle secrets
        secrets_data = data.get("secrets", {})
        secrets = {k: ActionSecretsConfig.model_validate(v) for k, v in secrets_data.items()}

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", ""),
            secrets=secrets,
            actions=data.get("actions", []),
            external_endpoints=data.get("external-endpoints", []),
        )


@dataclass(frozen=True)
class AgentPackageActionPackageMetadata:
    """Extended action package metadata for agent packages."""

    # Include all fields from ActionPackageMetadata
    name: str = field(metadata={"description": "Name of the action package."})
    """Name of the action package."""

    description: str = field(metadata={"description": "Description of the action package."})
    """Description of the action package."""

    version: str = field(metadata={"description": "Version of the action package."})
    """Version of the action package."""

    secrets: dict[str, ActionSecretsConfig] = field(
        default_factory=dict,
        metadata={"description": "Secrets configuration per action."},
    )
    """Secrets configuration per action."""

    actions: list[ActionPackageMetadataAction] = field(
        default_factory=list, metadata={"description": "Actions in the package."}
    )
    """Actions in the package."""

    external_endpoints: list[ExternalEndpoint] = field(
        default_factory=list, metadata={"description": "External endpoints."}
    )
    """External endpoints."""

    # Additional fields specific to agent package context
    whitelist: str = field(default="", metadata={"description": "Whitelist of allowed actions."})
    """Whitelist of allowed actions."""

    icon: str = field(default="", metadata={"description": "Icon for the action package."})
    """Icon for the action package."""

    path: str = field(default="", metadata={"description": "Path to the action package."})
    """Path to the action package."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "secrets": {k: v.model_dump() for k, v in self.secrets.items()},
            "action_package_version": self.version,
            "actions": [action.model_dump() for action in self.actions],
            "external-endpoints": [endpoint.model_dump() for endpoint in self.external_endpoints],
            "whitelist": self.whitelist,
            "icon": self.icon,
            "path": self.path,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageActionPackageMetadata":
        """Create from dictionary."""
        if data is None:
            return cls(name="", description="", version="", secrets={}, actions=[], external_endpoints=[])

        if isinstance(data, cls):
            return data

        data = data.copy()

        # Handle version field naming
        if "action_package_version" in data:
            data["version"] = data.pop("action_package_version")

        # Handle external endpoints naming
        if "external-endpoints" in data:
            endpoints = [ExternalEndpoint.model_validate(ep) for ep in data["external-endpoints"]]
            data["external_endpoints"] = endpoints
            del data["external-endpoints"]

        # Handle actions
        if "actions" in data:
            actions = [ActionPackageMetadataAction.model_validate(action) for action in data["actions"]]
            data["actions"] = actions

        # Handle secrets
        secrets_data = data.get("secrets", {})
        secrets = {k: ActionSecretsConfig.model_validate(v) for k, v in secrets_data.items()}

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", ""),
            secrets=secrets,
            actions=data.get("actions", []),
            external_endpoints=data.get("external-endpoints", []),
            whitelist=data.get("whitelist", ""),
            icon=data.get("icon", ""),
            path=data.get("path", ""),
        )


@dataclass(frozen=True)
class AgentPackageMetadata:
    """Main agent package metadata that mimics the Go AgentPackageMetadata struct."""

    release_note: str = field(metadata={"description": "Release notes for the agent package."})
    """Release notes for the agent package."""

    version: str = field(metadata={"description": "Version of the agent package."})
    """Version of the agent package."""

    icon: str = field(metadata={"description": "Icon for the agent package."})
    """Icon for the agent package."""

    name: str = field(metadata={"description": "Name of the agent package."})
    """Name of the agent package."""

    description: str = field(metadata={"description": "Description of the agent package."})
    """Description of the agent package."""

    model: SpecAgentModel = field(metadata={"description": "Model configuration for the agent."})
    """Model configuration for the agent."""

    architecture: AgentArchitecture = field(metadata={"description": "Architecture type of the agent."})
    """Architecture type of the agent."""

    reasoning: AgentReasoning = field(metadata={"description": "Reasoning level of the agent."})
    """Reasoning level of the agent."""

    knowledge: list[AgentPackageMetadataKnowledge] = field(
        default_factory=list, metadata={"description": "Knowledge configurations."}
    )
    """Knowledge configurations."""

    datasources: list[AgentPackageDatasource] = field(
        default_factory=list, metadata={"description": "Datasource configurations."}
    )
    """Datasource configurations."""

    question_groups: list[QuestionGroup] = field(
        default_factory=list, metadata={"description": "Question groups for the agent."}
    )
    """Question groups for the agent."""

    conversation_starter: str = field(default="", metadata={"description": "Conversation starter message."})
    """Conversation starter message."""

    welcome_message: str = field(default="", metadata={"description": "Welcome message for users."})
    """Welcome message for users."""

    metadata: dict[str, Any] = field(default_factory=dict, metadata={"description": "Agent metadata configuration."})
    """Agent metadata configuration."""

    action_packages: list[AgentPackageActionPackageMetadata] = field(
        default_factory=list, metadata={"description": "Action packages used by the agent."}
    )
    """Action packages used by the agent."""

    mcp_servers: list[AgentPackageMcpServer] = field(
        default_factory=list, metadata={"description": "MCP servers used by the agent."}
    )
    """MCP servers used by the agent."""

    docker_mcp_gateway: AgentPackageDockerMcpGateway | None = field(
        default=None, metadata={"description": "Docker MCP Gateway configuration."}
    )
    """Docker MCP Gateway configuration."""

    docker_mcp_gateway_changes: DockerMcpGatewayChanges = field(
        default_factory=DockerMcpGatewayChanges,
        metadata={"description": "Changes to Docker MCP Gateway."},
    )
    """Changes to Docker MCP Gateway."""

    agent_settings: dict[str, Any] | None = field(default_factory=dict, metadata={"description": "Agent settings."})
    """Agent settings."""

    document_intelligence: Literal["v2"] | None = field(
        default=None, metadata={"description": "The document intelligence version to use."}
    )
    """The document intelligence version to use."""

    selected_tools: SelectedTools = field(
        default_factory=SelectedTools,
        metadata={"description": "Configuration for tools selected for this agent."},
    )
    """Configuration for tools selected for this agent."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "release_note": self.release_note,
            "version": self.version,
            "icon": self.icon,
            "name": self.name,
            "description": self.description,
            "model": self.model.model_dump(),
            "architecture": self.architecture,
            "reasoning": self.reasoning,
            "knowledge": [k.model_dump() for k in self.knowledge],
            "datasources": [d.model_dump() for d in self.datasources],
            "metadata": self.metadata,
            "action_packages": [ap.model_dump() for ap in self.action_packages],
            "docker_mcp_gateway": self.docker_mcp_gateway.model_dump() if self.docker_mcp_gateway else None,
            "docker_mcp_gateway_changes": self.docker_mcp_gateway_changes.model_dump(),
            "agent_settings": self.agent_settings,
            "document_intelligence": self.document_intelligence,
            "selected_tools": self.selected_tools.model_dump(),
        }

        # Handle optional fields
        if self.question_groups:
            result["question_groups"] = [qg.model_dump() for qg in self.question_groups]

        if self.conversation_starter:
            result["conversation_starter"] = self.conversation_starter

        if self.welcome_message:
            result["welcome_message"] = self.welcome_message

        if self.mcp_servers:
            result["mcp_servers"] = [mcp.model_dump() for mcp in self.mcp_servers]

        if self.docker_mcp_gateway:
            result["docker_mcp_gateway"] = self.docker_mcp_gateway.model_dump()

        return result

    @classmethod
    def _validate_nested_objects(cls, data: dict[str, Any]) -> None:
        """Validate and convert nested objects in the data dictionary."""
        if "model" in data:
            data["model"] = SpecAgentModel.model_validate(data["model"])

        if "knowledge" in data:
            data["knowledge"] = [AgentPackageMetadataKnowledge.model_validate(k) for k in data["knowledge"]]

        if "datasources" in data:
            data["datasources"] = [AgentPackageDatasource.model_validate(d) for d in data["datasources"]]

        if "question_groups" in data:
            data["question_groups"] = [QuestionGroup.model_validate(qg) for qg in data["question_groups"]]

        if "action_packages" in data:
            data["action_packages"] = [
                AgentPackageActionPackageMetadata.model_validate(ap) for ap in data["action_packages"]
            ]

        if "mcp_servers" in data:
            data["mcp_servers"] = [AgentPackageMcpServer.model_validate(mcp) for mcp in data["mcp_servers"]]

        if "docker_mcp_gateway" in data and data["docker_mcp_gateway"] is not None:
            data["docker_mcp_gateway"] = AgentPackageDockerMcpGateway.model_validate(data["docker_mcp_gateway"])

        if "docker_mcp_gateway_changes" in data:
            data["docker_mcp_gateway_changes"] = DockerMcpGatewayChanges.model_validate(
                data["docker_mcp_gateway_changes"]
            )

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageMetadata":
        """Create from dictionary."""
        if data is None:
            return cls(
                release_note="",
                version="",
                icon="",
                name="",
                description="",
                model=SpecAgentModel(),
                architecture="agent",
                reasoning="disabled",
                knowledge=[],
                datasources=[],
                question_groups=[],
                conversation_starter="",
                welcome_message="",
                metadata={},
                action_packages=[],
                mcp_servers=[],
                docker_mcp_gateway=None,
                docker_mcp_gateway_changes=DockerMcpGatewayChanges(),
                agent_settings=None,
                document_intelligence=None,
                selected_tools=SelectedTools(),
            )

        if isinstance(data, cls):
            return data

        data = data.copy()
        cls._validate_nested_objects(data)

        return cls(
            release_note=data.get("release_note", ""),
            version=data.get("version", ""),
            icon=data.get("icon", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            model=SpecAgentModel.model_validate(data.get("model", {})),
            architecture=data.get("architecture", ""),
            reasoning=data.get("reasoning", ""),
            knowledge=data.get("knowledge", []),
            datasources=data.get("datasources", []),
            question_groups=data.get("question_groups", []),
            conversation_starter=data.get("conversation_starter", ""),
            welcome_message=data.get("welcome_message", ""),
            metadata=data.get("metadata", {}),
            action_packages=data.get("action_packages", []),
            mcp_servers=data.get("mcp_servers", []),
            docker_mcp_gateway=data.get("docker_mcp_gateway", None),
            docker_mcp_gateway_changes=data.get("docker_mcp_gateway_changes", DockerMcpGatewayChanges()),
            agent_settings=data.get("agent_settings", None),
            document_intelligence=data.get("document_intelligence", None),
            selected_tools=SelectedTools.model_validate(data.get("selected_tools", {})),
        )
