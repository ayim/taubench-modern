from dataclasses import dataclass, field
from typing import Any

from agent_platform.core.agent_package.metadata.agent_metadata import (
    ExternalEndpoint,
)


@dataclass(frozen=True)
class ActionPackageMetadataInfo:
    """Basic metadata information for an action package."""

    name: str = field(metadata={"description": "Name of the action package."})
    """Name of the action package."""

    description: str = field(metadata={"description": "Description of the action package."})
    """Description of the action package."""

    secrets: dict[str, Any] = field(
        default_factory=dict, metadata={"description": "Secrets configuration."}
    )
    """Secrets configuration."""

    action_package_version: str = field(
        default="0.0.1", metadata={"description": "Version of the action package."}
    )
    """Version of the action package."""

    metadata_version: int = field(
        default=2, metadata={"description": "Version of the metadata format."}
    )
    """Version of the metadata format."""

    external_endpoints: list[ExternalEndpoint] = field(
        default_factory=list, metadata={"description": "External endpoints."}
    )
    """External endpoints."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "secrets": self.secrets,
            "action_package_version": self.action_package_version,
            "metadata_version": self.metadata_version,
            "external-endpoints": [endpoint.model_dump() for endpoint in self.external_endpoints],
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionPackageMetadataInfo":
        """Create from dictionary."""
        if data is None:
            return cls(
                name="",
                description="",
                secrets={},
                action_package_version="0.0.1",
                metadata_version=2,
                external_endpoints=[],
            )

        if isinstance(data, cls):
            return data

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            secrets=data.get("secrets", {}),
            action_package_version=data.get("action_package_version", "0.0.1"),
            metadata_version=data.get("metadata_version", 2),
            external_endpoints=[
                ExternalEndpoint.model_validate(ep) for ep in data.get("external-endpoints", [])
            ],
        )


@dataclass(frozen=True)
class OpenAPIInfo:
    """OpenAPI info section."""

    title: str = field(metadata={"description": "The title of the API."})
    """The title of the API."""

    version: str = field(metadata={"description": "The version of the API."})
    """The version of the API."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "title": self.title,
            "version": self.version,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "OpenAPIInfo":
        """Create from dictionary."""
        if data is None:
            return cls(title="Action Server", version="1.0.0")

        if isinstance(data, cls):
            return data

        return cls(
            title=data.get("title", ""),
            version=data.get("version", ""),
        )


@dataclass(frozen=True)
class OpenAPIServer:
    """OpenAPI server configuration."""

    url: str = field(metadata={"description": "The server URL."})
    """The server URL."""

    description: str = field(default="", metadata={"description": "Optional server description."})
    """Optional server description."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result = {"url": self.url}
        if self.description:
            result["description"] = self.description
        return result

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "OpenAPIServer":
        """Create from dictionary."""
        if data is None:
            return cls(url="")

        if isinstance(data, cls):
            return data

        return cls(
            url=data.get("url", ""),
            description=data.get("description", ""),
        )


@dataclass(frozen=True)
class OpenAPISpecification:
    """OpenAPI specification structure."""

    openapi: str = field(metadata={"description": "OpenAPI version."})
    """OpenAPI version."""

    info: OpenAPIInfo = field(metadata={"description": "API information."})
    """API information."""

    servers: list[OpenAPIServer] = field(
        default_factory=list, metadata={"description": "Server configurations."}
    )
    """Server configurations."""

    paths: dict[str, Any] = field(
        default_factory=dict, metadata={"description": "API paths and operations."}
    )
    """API paths and operations."""

    components: dict[str, Any] = field(
        default_factory=dict, metadata={"description": "Reusable components."}
    )
    """Reusable components."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "openapi": self.openapi,
            "info": self.info.model_dump(),
            "servers": [server.model_dump() for server in self.servers],
            "paths": self.paths,
            "components": self.components,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "OpenAPISpecification":
        """Create from dictionary."""
        if data is None:
            return cls(
                openapi="3.1.0",
                info=OpenAPIInfo(title="Action Server", version="1.0.0"),
                servers=[],
                paths={},
                components={},
            )

        if isinstance(data, cls):
            return data

        data = data.copy()

        # Handle nested objects
        if "info" in data:
            data["info"] = OpenAPIInfo.model_validate(data["info"])

        if "servers" in data:
            servers = [OpenAPIServer.model_validate(server) for server in data["servers"]]
            data["servers"] = servers

        return cls(**data)


@dataclass(frozen=True)
class ActionPackageMetadata:
    """Action package metadata that matches the real JSON structure.

    Structure:
    {
        "metadata": { ... },
        "openapi.json": { ... }
    }
    """

    metadata: ActionPackageMetadataInfo = field(
        metadata={"description": "Package metadata information."}
    )
    """Package metadata information."""

    openapi_json: OpenAPISpecification = field(
        metadata={"description": "OpenAPI specification.", "export_name": "openapi.json"}
    )
    """OpenAPI specification."""

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "metadata": self.metadata.model_dump(),
            "openapi.json": self.openapi_json.model_dump(),
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionPackageMetadata":
        """Create from dictionary."""
        if data is None:
            return cls(
                metadata=ActionPackageMetadataInfo(
                    name="", description="", action_package_version="0.0.1"
                ),
                openapi_json=OpenAPISpecification(
                    openapi="3.1.0", info=OpenAPIInfo(title="Action Server", version="1.0.0")
                ),
            )

        if isinstance(data, cls):
            return data

        data = data.copy()

        # Handle metadata section
        metadata_data = data.get("metadata", {})
        metadata = ActionPackageMetadataInfo.model_validate(metadata_data)

        # Handle openapi.json section
        openapi_data = data.get("openapi.json", {})
        openapi_json = OpenAPISpecification.model_validate(openapi_data)

        return cls(
            metadata=metadata,
            openapi_json=openapi_json,
        )

    def get_actions(self) -> list[dict[str, Any]]:
        """Extract action information from OpenAPI paths.

        Returns a list of action dictionaries with basic info extracted
        from the OpenAPI specification.
        """
        actions = []

        for path, path_info in self.openapi_json.paths.items():
            for method, operation in path_info.items():
                if method.lower() == "post" and isinstance(operation, dict):
                    # Extract operation ID as action name
                    operation_id = operation.get("operationId", "")
                    summary = operation.get("summary", "")
                    description = operation.get("description", "")

                    actions.append(
                        {
                            "name": operation_id,
                            "summary": summary,
                            "description": description,
                            "path": path,
                            "method": method.upper(),
                        }
                    )

        return actions
