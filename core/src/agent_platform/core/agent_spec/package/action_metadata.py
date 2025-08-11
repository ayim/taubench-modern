import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from ruamel.yaml import YAML

from agent_platform.core.agent_spec.package.agent_metadata import (
    ExternalEndpoint,
)
from agent_platform.core.agent_spec.utils import read_file_from_zip, read_package_bytes

_yaml = YAML(typ="safe")


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


async def extract_action_package_metadata(
    path: str | Path | None = None,
    url: str | None = None,
    package_base64: str | bytes | None = None,
) -> ActionPackageMetadata:
    """
    Extract the metadata from an action package.

    * Pass **exactly one** of *path*, *url*, *package_base64*.

    FastAPI detail: any failure raises ``HTTPException`` with descriptive text.

    Arguments:
        path: local path to the action package
        url: URL to the action package
        package_base64: base64-encoded action package

    Returns:
        An ActionPackageMetadata instance.
    """

    blob = await read_package_bytes(path, url, package_base64)

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            # Action packages typically use a different metadata filename
            # Based on Go code patterns, likely something like this
            metadata_filename = "__action_server_metadata__.json"
            metadata_raw = read_file_from_zip(zf, metadata_filename)

            # Try JSON first, then YAML as fallback
            try:
                import json

                metadata_dict = json.loads(metadata_raw.decode())
            except json.JSONDecodeError:
                # Fallback to YAML if JSON fails
                metadata_dict = _yaml.load(metadata_raw.decode())

            return ActionPackageMetadata.model_validate(metadata_dict)

    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided bytes are not a valid zip archive",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action package metadata file not found: {exc}",
        ) from exc
