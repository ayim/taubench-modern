import json
from typing import Any

from structlog import get_logger

from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.base import BasePackageHandler
from agent_platform.core.agent_package.metadata.agent_metadata import AgentPackageMetadata
from agent_platform.core.agent_package.spec import AgentSpec, SpecAgent
from agent_platform.core.errors import ErrorCode, PlatformHTTPError

logger = get_logger(__name__)


class AgentPackageHandler(BasePackageHandler):
    cached_spec: AgentSpec | None = None
    cached_metadata: AgentPackageMetadata | None = None

    async def validate_package_contents(self):
        """
        Checks if agent-spec.yaml is present in the Package and runs AgentSpec pydantic
        Model validation against its contents.
        """
        has_spec_file = await self.file_exists(AgentPackageConfig.agent_spec_filename)

        if not has_spec_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"{AgentPackageConfig.agent_spec_filename} is missing in Agent Package",
            )

        # Runs validation against agent-spec.yaml and caches the result if successful.
        # If not, ValidationError will be raised.
        await self.read_agent_spec()

    async def read_agent_spec(self) -> AgentSpec:
        if self.cached_spec is not None:
            return self.cached_spec

        spec_raw = await self.read_file(AgentPackageConfig.agent_spec_filename)
        spec = AgentSpec.from_yaml(spec_raw)

        # agent-spec.yaml is typically not very big, so we are caching it
        # for future references.
        self.cached_spec = spec

        return self.cached_spec

    async def get_spec_agent(self) -> SpecAgent:
        """
        Returns the first agent defined in the agent-spec.yaml file.
        While technically, agent-spec.yaml v1 and v2 allow for multiple agents,
        we only support a single agent per package.

        Future spec versions will most likely drop the array support.
        """
        spec = await self.read_agent_spec()

        # At this point, the spec file has been validated - if it didn't contain exactly
        # one Agent definition, an error would have been raised.
        return spec.agent_package.agents[0]

    async def read_metadata(self) -> AgentPackageMetadata:
        if self.cached_metadata is not None:
            return self.cached_metadata

        metadata_raw = await self.read_file(AgentPackageConfig.metadata_filename)
        # Even though agent-spec.yaml supports only one Agent definition, it does it
        # via an array - metadata follows the same pattern, so we need to explicitly
        # cast the metadata to list here, so we can select the first element.
        metadata_parsed: list[dict[str, Any]] = json.loads(metadata_raw.decode())

        return AgentPackageMetadata.model_validate(metadata_parsed[0])

    async def read_runbook(self):
        spec_agent = await self.get_spec_agent()

        # TODO:
        # Add check for runbook file existence in the Package.
        runbook_filename = spec_agent.runbook or AgentPackageConfig.runbook_filename

        runbook_raw = await self.read_file(runbook_filename)

        return runbook_raw.decode("utf-8", errors="replace")

    async def read_conversation_guide_raw(self) -> bytes | None:
        spec_agent = await self.get_spec_agent()

        if not spec_agent.conversation_guide:
            return None

        return await self.read_file(spec_agent.conversation_guide)

    async def read_action_package_zip_raw(self, action_package_zip_path: str) -> bytes:
        path = f"{AgentPackageConfig.actions_dirname}/{action_package_zip_path}"
        return await self.read_file(path)

    async def read_semantic_data_model_raw(self, semantic_data_model_filename: str) -> bytes:
        path = f"{AgentPackageConfig.semantic_data_models_dirname}/{semantic_data_model_filename}"
        return await self.read_file(path)
