from dataclasses import dataclass, field
from typing import Any

import structlog
from pydantic import BaseModel

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_package.spec import (
    SpecAgentModel,
    SpecAgentReasoning,
    SpecDockerMcpGateway,
    SpecDocumentIntelligence,
    SpecKnowledge,
    SpecMCPServer,
    SpecMCPTransport,
)
from agent_platform.core.mcp.mcp_types import (
    MCPVariableTypeOAuth2Secret,
    MCPVariableTypeSecret,
    MCPVariableTypeString,
)
from agent_platform.core.selected_tools import SelectedTools

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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

    @classmethod
    def from_spec(cls, spec: SpecKnowledge) -> "AgentPackageMetadataKnowledge":
        """Create from SpecKnowledge."""
        return cls(
            embedded=spec.embedded,
            name=spec.name,
            digest=spec.digest or "",
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

    transport: SpecMCPTransport = field(
        default="auto", metadata={"description": "Transport protocol for the MCP server."}
    )
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

    @classmethod
    def from_spec(cls, spec: SpecMCPServer) -> "AgentPackageMcpServer":
        """Generate metadata for an MCP server from spec.

        Translates MCP server specification from agent-spec.yaml into
        AgentPackageMcpServer. Handles transport type detection and
        validation for URL vs stdio transports.

        Args:
            mcp_spec: MCP server specification from agent spec.

        Returns:
            AgentPackageMcpServer with processed configuration.

        Raises:
            ValueError: If both URL and command are set, or transport doesn't match config.
        """
        name = spec.name
        description = spec.description or ""
        transport: SpecMCPTransport = spec.transport or "auto"
        url = spec.url or ""
        command_line = spec.command_line or []
        cwd = spec.cwd or ""
        force_serial_tool_calls = spec.force_serial_tool_calls or False

        # Calculate the transport type based on the url and command line
        is_url_transport = transport in ("streamable-http", "sse")

        # Split the command line into command + arguments
        command = command_line[0] if command_line else ""

        if transport == "auto":
            if url:
                is_url_transport = True
            elif command:
                is_url_transport = False

        if is_url_transport:
            # Process headers for URL-based transport
            headers: dict[str, AgentPackageMcpServerVariable] = {}
            raw_headers = spec.headers or {}
            for key, value in raw_headers.items():
                headers[key] = cls._build_mcp_server_variable(value)

            return cls(
                name=name,
                description=description,
                transport=transport,
                url=url,
                headers=headers,
                command="",
                arguments=[],
                env={},
                cwd="",
                force_serial_tool_calls=force_serial_tool_calls,
            )

        # STDIO transport
        args = command_line[1:] if len(command_line) > 1 else []

        # Process environment variables
        env: dict[str, AgentPackageMcpServerVariable] = {}
        raw_env = spec.env or {}
        for key, value in raw_env.items():
            env[key] = cls._build_mcp_server_variable(value)

        return cls(
            name=name,
            description=description,
            transport=transport,
            url="",
            headers={},
            command=command,
            arguments=args,
            env=env,
            cwd=cwd,
            force_serial_tool_calls=force_serial_tool_calls,
        )

    @classmethod
    def _build_mcp_server_variable(
        cls,
        value: str | BaseModel | dict[str, Any],
    ) -> AgentPackageMcpServerVariable:
        """Build an AgentPackageMcpServerVariable from spec value.

        Handles both scalar string values and object values with type/description/etc.

        Args:
            value: Either a string value, a Pydantic model, or dict with type/description.

        Returns:
            AgentPackageMcpServerVariable instance.
        """
        if isinstance(value, str):
            return AgentPackageMcpServerVariable(value=value)

        # Handle Pydantic MCP variable types
        if isinstance(value, MCPVariableTypeOAuth2Secret):
            return AgentPackageMcpServerVariable(
                value=value.value,
                type=value.type,
                description=value.description or "",
                provider=value.provider,
                scopes=value.scopes,
            )

        if isinstance(value, MCPVariableTypeString | MCPVariableTypeSecret):
            return AgentPackageMcpServerVariable(
                value=value.value,
                type=value.type,
                description=value.description or "",
                provider="",
                scopes=[],
            )

        # Handle other Pydantic BaseModel types
        if isinstance(value, BaseModel):
            data = value.model_dump()
            return AgentPackageMcpServerVariable(
                value=data.get("value"),
                type=data.get("type", ""),
                description=data.get("description", ""),
                provider=data.get("provider", ""),
                scopes=data.get("scopes", []),
            )

        # Handle dict fallback
        return AgentPackageMcpServerVariable(
            value=value.get("value"),
            type=value.get("type", ""),
            description=value.get("description", ""),
            provider=value.get("provider", ""),
            scopes=value.get("scopes", []),
        )


@dataclass(frozen=True)
class AgentPackageDockerMcpGateway:
    """Docker MCP Gateway configuration for agent packages."""

    catalog: str | None = field(default=None, metadata={"description": "Path to the catalog file."})
    """Path to the catalog file."""

    servers: dict[str, dict] = field(
        default_factory=dict,
        metadata={"description": "Server configurations."},
    )
    """Server configurations. Kept loose because the servers should borrow from the catalog entries."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "catalog": self.catalog,
            "servers": self.servers,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageDockerMcpGateway":
        """Create from dictionary."""
        if data is None:
            return cls(catalog=None, servers={})

        if isinstance(data, cls):
            return data

        data = data.copy()
        return cls(
            catalog=data.get("catalog", None),
            servers=data.get("servers", {}),
        )

    @classmethod
    def from_spec(cls, spec: SpecDockerMcpGateway | None) -> "AgentPackageDockerMcpGateway | None":
        """Create from spec."""
        if spec is None:
            return None

        return cls(
            catalog=spec.catalog,
            servers=spec.servers,
        )


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

    action_package_version: str = field(
        default="",
        metadata={"description": "Version of the action package (for backwards compatibility)."},
    )
    """Version of the action package (for backwards compatibility)."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        # Use action_package_version if set, otherwise fall back to version
        effective_version = self.action_package_version or self.version
        return {
            "name": self.name,
            "description": self.description,
            "secrets": {k: v.model_dump() for k, v in self.secrets.items()},
            "version": effective_version,
            "action_package_version": effective_version,  # Kept for backwards compatibility
            "actions": [action.model_dump() for action in self.actions],
            "external-endpoints": [endpoint.model_dump() for endpoint in self.external_endpoints],
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionPackageMetadata":
        """Create from dictionary."""
        if data is None:
            return cls(
                name="",
                description="",
                version="",
                secrets={},
                actions=[],
                external_endpoints=[],
                action_package_version="",
            )

        if isinstance(data, cls):
            return data

        data = data.copy()

        # Extract version fields before any modifications
        version = data.get("action_package_version", data.get("version", ""))

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
            version=version,
            secrets=secrets,
            actions=data.get("actions", []),
            external_endpoints=data.get("external_endpoints", []),
            action_package_version=version,
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

    full_path: str = field(default="", metadata={"description": "Full path to the action package."})
    """Full path to the action package, including the package name - for the zip file."""

    action_package_version: str = field(
        default="",
        metadata={"description": "Version of the action package (for backwards compatibility)."},
    )
    """Version of the action package (for backwards compatibility)."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        # Use action_package_version if set, otherwise fall back to version
        effective_version = self.action_package_version or self.version
        return {
            "name": self.name,
            "description": self.description,
            "secrets": {k: v.model_dump() for k, v in self.secrets.items()},
            "version": effective_version,
            "action_package_version": effective_version,
            "actions": [action.model_dump() for action in self.actions],
            "external-endpoints": [endpoint.model_dump() for endpoint in self.external_endpoints],
            "whitelist": self.whitelist,
            "icon": self.icon,
            "path": self.path,
            "full_path": self.full_path,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageActionPackageMetadata":
        """Create from dictionary."""
        if data is None:
            return cls(
                name="",
                description="",
                version="",
                secrets={},
                actions=[],
                external_endpoints=[],
                action_package_version="",
            )

        if isinstance(data, cls):
            return data

        data = data.copy()

        # Extract version fields before any modifications
        version = data.get("version", "")
        action_package_version = data.get("action_package_version", "")

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
            version=version,
            secrets=secrets,
            actions=data.get("actions", []),
            external_endpoints=data.get("external_endpoints", []),
            whitelist=data.get("whitelist", ""),
            icon=data.get("icon", ""),
            path=data.get("path", ""),
            full_path=data.get("full_path", ""),
            action_package_version=action_package_version,
        )


@dataclass(frozen=True)
class AgentPackageMetadata:
    """Main agent package metadata that mimics the Go AgentPackageMetadata struct."""

    release_note: str = field(metadata={"description": "Release notes for the agent package."})
    """Release notes for the agent package."""

    version: str = field(metadata={"description": "Version of the agent package."})
    """Version of the agent package."""

    name: str = field(metadata={"description": "Name of the agent package."})
    """Name of the agent package."""

    description: str = field(metadata={"description": "Description of the agent package."})
    """Description of the agent package."""

    reasoning: SpecAgentReasoning = field(metadata={"description": "Reasoning level of the agent."})
    """Reasoning level of the agent."""

    # --- Fields with defaults must come after fields without defaults ---

    model: SpecAgentModel | None = field(default=None, metadata={"description": "Model configuration for the agent."})
    """Model configuration for the agent."""

    architecture: str | None = field(default=None, metadata={"description": "Architecture type of the agent."})
    """Architecture type of the agent."""

    icon: str = field(default="", metadata={"description": "Icon for the agent package."})
    """Icon for the agent package."""

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

    agent_settings: dict[str, Any] | None = field(default_factory=dict, metadata={"description": "Agent settings."})
    """Agent settings."""

    document_intelligence: SpecDocumentIntelligence | None = field(
        default=None, metadata={"description": "The document intelligence version to use."}
    )
    """The document intelligence version to use."""

    selected_tools: SelectedTools = field(
        default_factory=SelectedTools,
        metadata={"description": "Configuration for tools selected for this agent."},
    )
    """Configuration for tools selected for this agent."""

    changelog: str = field(default="", metadata={"description": "Changelog for the agent package."})
    """Changelog for the agent package."""

    readme: str = field(default="", metadata={"description": "Readme for the agent package."})
    """Readme for the agent package."""

    agent_platform_version: str = field(
        default="",
        metadata={"description": "Version of the agent platform with which the metadata was generated."},
    )
    """Version of the agent platform with which the metadata was generated."""

    created_at: int = field(default=0, metadata={"description": "Timestamp of when the metadata was created."})
    """Timestamp of when the metadata was created."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "release_note": self.release_note,
            "version": self.version,
            "icon": self.icon,
            "name": self.name,
            "description": self.description,
            "model": self.model.model_dump() if self.model else None,
            "architecture": self.architecture if self.architecture else None,
            "reasoning": self.reasoning,
            "knowledge": [k.model_dump() for k in self.knowledge],
            "datasources": [d.model_dump() for d in self.datasources],
            "metadata": self.metadata,
            "action_packages": [ap.model_dump() for ap in self.action_packages],
            "docker_mcp_gateway": self.docker_mcp_gateway.model_dump() if self.docker_mcp_gateway else None,
            "agent_settings": self.agent_settings,
            "document_intelligence": self.document_intelligence,
            "selected_tools": self.selected_tools.model_dump(),
            "agent_platform_version": self.agent_platform_version,
            "created_at": self.created_at,
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

        if self.changelog:
            result["changelog"] = self.changelog

        if self.readme:
            result["readme"] = self.readme

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

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "AgentPackageMetadata":
        """Create from dictionary."""

        if data is None:
            default_empty_model = SpecAgentModel(name="", provider="")
            return cls(
                release_note="",
                version="",
                icon="",
                name="",
                description="",
                model=default_empty_model,
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
                agent_settings=None,
                document_intelligence=None,
                selected_tools=SelectedTools(),
                changelog="",
                readme="",
                agent_platform_version="",
                created_at=0,
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
            agent_settings=data.get("agent_settings", None),
            document_intelligence=data.get("document_intelligence", None),
            selected_tools=SelectedTools.model_validate(data.get("selected_tools", {})),
            changelog=data.get("changelog", ""),
            readme=data.get("readme", ""),
            agent_platform_version=data.get("agent_platform_version", ""),
            created_at=data.get("created_at", 0),
        )
