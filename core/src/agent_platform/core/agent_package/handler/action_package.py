import json

from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.base import BasePackageHandler
from agent_platform.core.agent_package.metadata.agent_metadata import ActionPackageMetadata
from agent_platform.core.errors import ErrorCode, PlatformHTTPError


class ActionPackageHandler(BasePackageHandler):
    cached_metadata: ActionPackageMetadata | None = None

    async def validate_package_contents(self):
        """
        Checks if the package.yaml file exists in the Package.
        """
        has_spec_file = self.file_exists(AgentPackageConfig.action_package_spec_filename)

        if not has_spec_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"{AgentPackageConfig.action_package_spec_filename} is missing "
                "in Action Package",
            )

    async def read_package_spec_raw(self) -> bytes:
        return await self.read_file(AgentPackageConfig.action_package_spec_filename)

    async def read_metadata(self) -> ActionPackageMetadata:
        if self.cached_metadata is not None:
            return self.cached_metadata

        metadata_raw = await self.read_file(AgentPackageConfig.action_package_metadata_filename)
        metadata_dict = json.loads(metadata_raw.decode())

        return ActionPackageMetadata.model_validate(metadata_dict)
