import json
from dataclasses import dataclass, field
from typing import Any, Self

import structlog

from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.base import BasePackageHandler, PackageFileContent, PackageFilePath
from agent_platform.core.agent_package.metadata.agent_metadata import ActionPackageMetadata, ExternalEndpoint
from agent_platform.core.agent_package.utils import convert_image_bytes_to_base64
from agent_platform.core.errors import ErrorCode, PlatformHTTPError

logger = structlog.get_logger(__name__)

# ActionPackageMap is a dictionary mapping action package paths to their expanded contents.
# The expanded contents is a dict mapping file paths within the zip to their bytes.
# Example: {"Sema4.ai/browsing": {"package.yaml": b"...", "actions.py": b"...", ...}}
ActionPackageFilePath = PackageFilePath
ActionPackageFileContent = PackageFileContent
ActionPackageContent = dict[ActionPackageFilePath, ActionPackageFileContent]

ActionPackagePath = PackageFilePath
ActionPackageMap = dict[ActionPackagePath, ActionPackageContent]


@dataclass(frozen=True)
class ActionPackageSpecDependencies:
    """Dependencies configuration for an action package."""

    conda_forge: list[str] = field(default_factory=list, metadata={"description": "Conda-forge dependencies."})
    """Conda-forge dependencies."""

    pypi: list[str] = field(default_factory=list, metadata={"description": "PyPI dependencies."})
    """PyPI dependencies."""

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionPackageSpecDependencies":
        """Create from dictionary."""
        if data is None:
            return cls()
        if isinstance(data, cls):
            return data
        return cls(
            conda_forge=data.get("conda-forge", []) or [],
            pypi=data.get("pypi", []) or [],
        )


@dataclass(frozen=True)
class ActionPackageSpecPackaging:
    """Packaging configuration for an action package."""

    exclude: list[str] = field(
        default_factory=list, metadata={"description": "Glob patterns to exclude from packaging."}
    )
    """Glob patterns to exclude from packaging."""

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionPackageSpecPackaging":
        """Create from dictionary."""
        if data is None:
            return cls()
        if isinstance(data, cls):
            return data
        return cls(
            exclude=data.get("exclude", []) or [],
        )


@dataclass(frozen=True)
class ActionPackageSpec:
    """Action package specification from package.yaml.

    This is a permissive model that supports the package.yaml format.
    """

    name: str = field(default="", metadata={"description": "A short name for the action package."})
    """A short name for the action package."""

    description: str = field(default="", metadata={"description": "A description of what's in the action package."})
    """A description of what's in the action package."""

    version: str = field(default="", metadata={"description": "Package version number (recommend semver)."})
    """Package version number (recommend semver)."""

    spec_version: str = field(default="", metadata={"description": "The version of the package.yaml format."})
    """The version of the package.yaml format."""

    dependencies: ActionPackageSpecDependencies = field(
        default_factory=ActionPackageSpecDependencies,
        metadata={"description": "Package dependencies."},
    )
    """Package dependencies."""

    external_endpoints: list[ExternalEndpoint] = field(
        default_factory=list, metadata={"description": "External endpoints the package accesses."}
    )
    """External endpoints the package accesses."""

    packaging: ActionPackageSpecPackaging = field(
        default_factory=ActionPackageSpecPackaging,
        metadata={"description": "Packaging configuration."},
    )
    """Packaging configuration."""

    # Store any extra fields not explicitly defined
    extra: dict[str, Any] = field(
        default_factory=dict, metadata={"description": "Any additional fields not explicitly defined."}
    )
    """Any additional fields not explicitly defined."""

    @classmethod
    def model_validate(cls, data: dict[str, Any] | None) -> "ActionPackageSpec":
        """Create from dictionary (e.g., parsed from package.yaml)."""
        if data is None:
            return cls()
        if isinstance(data, cls):
            return data

        data = data.copy()

        # Handle external-endpoints (with hyphen)
        endpoints_data = data.pop("external-endpoints", []) or []
        external_endpoints = [ExternalEndpoint.model_validate(ep) for ep in endpoints_data]

        # Handle spec-version (with hyphen)
        spec_version = data.pop("spec-version", "")

        # Handle dependencies
        dependencies_data = data.pop("dependencies", None)
        dependencies = ActionPackageSpecDependencies.model_validate(dependencies_data)

        # Handle packaging
        packaging_data = data.pop("packaging", None)
        packaging = ActionPackageSpecPackaging.model_validate(packaging_data)

        # Extract known fields
        name = data.pop("name", "")
        description = data.pop("description", "")
        version = data.pop("version", "")

        # Store remaining fields as extra
        extra = data

        return cls(
            name=name,
            description=description,
            version=version,
            spec_version=spec_version,
            dependencies=dependencies,
            external_endpoints=external_endpoints,
            packaging=packaging,
            extra=extra,
        )


class ActionPackageHandler(BasePackageHandler):
    cached_metadata: ActionPackageMetadata | None = None

    async def validate_package_contents(self):
        """
        Checks if the package.yaml file exists in the Package.
        """
        has_spec_file = await self.file_exists(AgentPackageConfig.action_package_spec_filename)

        if not has_spec_file:
            logger.warning(
                "Action package spec file missing",
                expected_file=AgentPackageConfig.action_package_spec_filename,
            )
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"{AgentPackageConfig.action_package_spec_filename} is missing in Action Package",
            )

    async def read_package_spec_raw(self) -> bytes:
        return await self.read_file(AgentPackageConfig.action_package_spec_filename)

    async def read_package_spec(self) -> ActionPackageSpec:
        """Read and parse package.yaml as an ActionPackageSpec object.

        Returns:
            ActionPackageSpec object containing package.yaml contents.
        """
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        spec_raw = await self.read_package_spec_raw()
        spec_dict = yaml.load(spec_raw)
        return ActionPackageSpec.model_validate(spec_dict)

    async def read_metadata_raw(self) -> bytes:
        """Read raw metadata bytes from the action package.

        Returns:
            Raw bytes of the __action_server_metadata__.json file.
        """
        return await self.read_file(AgentPackageConfig.action_package_metadata_filename)

    async def read_metadata_dict(self) -> dict[str, Any]:
        """Read and parse metadata as a dictionary.

        Returns the full raw metadata dictionary including openapi.json etc.

        Returns:
            Full metadata dictionary from __action_server_metadata__.json.
        """
        metadata_raw = await self.read_metadata_raw()
        metadata_dict = json.loads(metadata_raw.decode())
        return metadata_dict

    async def read_metadata(self) -> ActionPackageMetadata:
        """Read and parse metadata as an ActionPackageMetadata object.
        Does a validation against the ActionPackageMetadata pydantic model.

        Returns:
            ActionPackageMetadata object.
        """
        if self.cached_metadata is not None:
            return self.cached_metadata

        metadata_dict = await self.read_metadata_dict()
        # Extract from nested "metadata" section if present, otherwise try top-level
        nested_metadata = metadata_dict.get("metadata", metadata_dict)

        return ActionPackageMetadata.model_validate(nested_metadata)

    async def load_icon(
        self,
    ) -> str:
        """Load and convert the action package icon to base64.

        This handler is already operating on a specific action package (zip or folder),
        so the icon is read from the root of this package.

        Args:
            ap_path: Action package path (unused, kept for compatibility).

        Returns:
            Base64 data URI string if icon exists, empty string otherwise.
        """
        icon_filename = AgentPackageConfig.action_package_icon_filename

        if not await self.file_exists(icon_filename):
            return ""

        try:
            icon_bytes = await self.read_file(icon_filename)
            icon_base64 = convert_image_bytes_to_base64(icon_bytes, icon_filename)
            return icon_base64
        except Exception as e:
            logger.warning("Failed to load action package icon", error=str(e))
            return ""

    async def write_package_contents(self, action_package_files: ActionPackageContent) -> Self:
        """Write the contents of the action package to the handler.

        Args:
            action_package_files: The files to write.

        Returns:
            The handler instance.
        """
        for file_path, file_content in action_package_files.items():
            await self.write_file(file_path, file_content)
        return self
