import json
from typing import Any, Self

import structlog

from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.base import BasePackageHandler, PackageFileContent, PackageFilePath
from agent_platform.core.agent_package.metadata.agent_metadata import ActionPackageMetadata
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
