import json
from typing import Any

from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.base import BasePackageHandler
from agent_platform.core.agent_package.metadata.agent_metadata import ActionPackageMetadata
from agent_platform.core.agent_package.utils import convert_image_bytes_to_base64
from agent_platform.core.errors import ErrorCode, PlatformHTTPError


class ActionPackageHandler(BasePackageHandler):
    cached_metadata: ActionPackageMetadata | None = None

    async def validate_package_contents(self):
        """
        Checks if the package.yaml file exists in the Package.
        """
        has_spec_file = await self.file_exists(AgentPackageConfig.action_package_spec_filename)

        if not has_spec_file:
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
        return json.loads(metadata_raw.decode())

    async def read_metadata(self) -> ActionPackageMetadata:
        """Read and parse metadata as an ActionPackageMetadata object.
        Does a validation against the ActionPackageMetadata pydantic model.

        Returns:
            ActionPackageMetadata object.
        """
        if self.cached_metadata is not None:
            return self.cached_metadata

        metadata_dict = await self.read_metadata_dict()

        return ActionPackageMetadata.model_validate(metadata_dict)

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
            return convert_image_bytes_to_base64(icon_bytes, icon_filename)
        except Exception:
            return ""
