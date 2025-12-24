import json
from tempfile import SpooledTemporaryFile
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML
from structlog import get_logger

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.base import BasePackageHandler
from agent_platform.core.agent_package.metadata.agent_metadata import AgentPackageMetadata
from agent_platform.core.agent_package.spec import AgentPackageSpec, SpecAgent
from agent_platform.core.agent_package.utils import convert_image_bytes_to_base64
from agent_platform.core.data_frames.semantic_data_model_types import (
    SemanticDataModel,
    model_dump_sdm,
    model_validate_sdm,
)
from agent_platform.core.errors import ErrorCode, PlatformHTTPError

if TYPE_CHECKING:
    from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler

logger = get_logger(__name__)

_yaml = YAML(typ="safe")


class AgentPackageHandler(BasePackageHandler):
    cached_spec: AgentPackageSpec | None = None
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

    async def read_agent_spec(self) -> AgentPackageSpec:
        if self.cached_spec is not None:
            return self.cached_spec

        spec_raw = await self.read_file(AgentPackageConfig.agent_spec_filename)
        spec = AgentPackageSpec.from_yaml(spec_raw)

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

    async def read_conversation_guide(self) -> list[QuestionGroup]:
        from agent_platform.core.agent.question_group import QuestionGroup

        spec_agent = await self.get_spec_agent()
        if not spec_agent.conversation_guide:
            return []

        try:
            guide_bytes = await self.read_conversation_guide_raw()
            if not guide_bytes:
                return []
            guide_yaml = _yaml.load(guide_bytes.decode("utf-8"))

            if not isinstance(guide_yaml, dict):
                return []

            qg_list = guide_yaml.get("question-groups", [])
            return [QuestionGroup.model_validate(qg) for qg in qg_list if isinstance(qg, dict)]
        except Exception as e:
            logger.warning(
                "Failed to read conversation guide",
                path=spec_agent.conversation_guide,
                error=str(e),
            )
            return []

    async def list_action_package_paths(self) -> list[str]:
        """List all Action Package paths from the agent package."""
        spec_agent = await self.get_spec_agent()
        return [ap.path for ap in spec_agent.action_packages if ap.path]

    async def get_action_packages_handlers(self) -> list[tuple[str, "ActionPackageHandler"]]:
        """Get all Action Package handlers from the agent package."""
        from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler

        action_package_paths = await self.list_action_package_paths()
        return [
            (path, await ActionPackageHandler.from_bytes(await self.read_action_package_zip_raw(path)))
            for path in action_package_paths
        ]

    async def read_action_package_zip_raw(self, action_package_zip_path: str) -> bytes:
        path = f"{AgentPackageConfig.actions_dirname}/{action_package_zip_path}"
        return await self.read_file(path)

    async def read_semantic_data_model_raw(self, semantic_data_model_filename: str) -> bytes:
        path = f"{AgentPackageConfig.semantic_data_models_dirname}/{semantic_data_model_filename}"
        return await self.read_file(path)

    async def read_semantic_data_model(self, semantic_data_model_filename: str) -> SemanticDataModel | None:
        try:
            sdm_raw = await self.read_semantic_data_model_raw(semantic_data_model_filename)
            if not sdm_raw:
                return None

            # Parse YAML (Snowflake Cortex Analyst semantic model format)
            sdm_yaml = _yaml.load(sdm_raw.decode("utf-8"))

            if not isinstance(sdm_yaml, dict):
                logger.warning(
                    f"SDM file {semantic_data_model_filename}' does not contain valid YAML dict, skipping",
                )
                return None

            return model_validate_sdm(sdm_yaml)

        except Exception as e:
            logger.warning(
                "Failed to read Semantic Data Model",
                path=semantic_data_model_filename,
                error=str(e),
            )

    async def read_all_semantic_data_models(self) -> dict[str, SemanticDataModel]:
        result: dict[str, SemanticDataModel] = {}

        spec_agent = await self.get_spec_agent()

        sdm_refs = spec_agent.semantic_data_models or []

        if not sdm_refs:
            return result

        for sdm_ref in sdm_refs:
            if not sdm_ref.name:
                logger.warning("SDM reference missing 'name' field, skipping")
                continue

            sdm_filename = sdm_ref.name

            sdm = await self.read_semantic_data_model(sdm_filename)

            if not sdm:
                continue

            result[sdm_filename] = sdm

        return result

    async def load_agent_package_icon(self) -> str:
        """Load and convert the agent package icon to base64.

        Looks for the icon file at the root of the agent package.

        Returns:
            Base64 data URI string if icon exists, empty string otherwise.
        """
        icon_filename = AgentPackageConfig.agent_package_icon_filename

        if not await self.file_exists(icon_filename):
            logger.debug(f"Agent icon not found: {icon_filename}")
            return ""

        try:
            icon_bytes = await self.read_file(icon_filename)
            icon_base64 = convert_image_bytes_to_base64(icon_bytes, icon_filename)
            logger.debug("Agent icon loaded successfully")
            return icon_base64
        except Exception as e:
            logger.warning(
                "Failed to load agent package icon",
                icon_filename=icon_filename,
                error=str(e),
            )
            return ""

    async def load_changelog(self) -> str:
        """Load the changelog file content from the agent package.

        Returns:
            Changelog content as string if exists, empty string otherwise.
        """
        changelog_filename = AgentPackageConfig.agent_package_changelog_filename

        if not await self.file_exists(changelog_filename):
            logger.debug(f"Changelog not found: {changelog_filename}")
            return ""

        try:
            changelog_bytes = await self.read_file(changelog_filename)
            changelog_content = changelog_bytes.decode("utf-8")
            logger.debug("Changelog loaded successfully")
            return changelog_content
        except Exception as e:
            logger.warning(
                "Failed to load changelog",
                changelog_filename=changelog_filename,
                error=str(e),
            )
            return ""

    async def load_readme(self) -> str:
        """Load the readme file content from the agent package.

        Returns:
            Readme content as string if exists, empty string otherwise.
        """
        readme_filename = AgentPackageConfig.agent_package_readme_filename

        if not await self.file_exists(readme_filename):
            logger.debug(f"Readme not found: {readme_filename}")
            return ""

        try:
            readme_bytes = await self.read_file(readme_filename)
            readme_content = readme_bytes.decode("utf-8")
            logger.debug("Readme loaded successfully")
            return readme_content
        except Exception as e:
            logger.warning(
                "Failed to load readme",
                readme_filename=readme_filename,
                error=str(e),
            )
            return ""

    async def write_agent_spec(self, agent_spec: AgentPackageSpec) -> SpooledTemporaryFile:
        spooled_file = self._get_empty_spooled_file()

        buffer = agent_spec.to_yaml()
        spooled_file.write(buffer.encode("utf-8"))

        return spooled_file

    async def write_runbook(self, runbook_text: str) -> SpooledTemporaryFile:
        spooled_file = self._get_empty_spooled_file()
        spooled_file.write(runbook_text.encode("utf-8"))
        return spooled_file

    async def write_conversation_guide(self, question_groups: list[QuestionGroup]) -> SpooledTemporaryFile | None:
        if not question_groups:
            return None

        import io

        spooled_file = self._get_empty_spooled_file()

        yaml_buffer = io.StringIO()
        guide_dict = {
            "question-groups": [qg.model_dump() for qg in question_groups],
        }
        _yaml.dump(guide_dict, yaml_buffer)
        spooled_file.write(yaml_buffer.getvalue().encode("utf-8"))

        return spooled_file

    async def write_metadata(self, metadata: AgentPackageMetadata) -> SpooledTemporaryFile:
        import io

        spooled_file = self._get_empty_spooled_file()

        json_buffer = io.StringIO()
        # Even though agent-spec.yaml supports only one Agent definition, it does it
        # via an array - metadata follows the same pattern, so we need to explicitly
        # cast the metadata to list here, so we can select the first element.
        json.dump([metadata.model_dump()], json_buffer, indent=2)
        spooled_file.write(json_buffer.getvalue().encode("utf-8"))

        return spooled_file

    async def write_semantic_data_model(self, semantic_data_model: SemanticDataModel) -> SpooledTemporaryFile:
        import io

        spooled_file = self._get_empty_spooled_file()

        yaml_buffer = io.StringIO()
        _yaml.dump(model_dump_sdm(semantic_data_model), yaml_buffer)
        spooled_file.write(yaml_buffer.getvalue().encode("utf-8"))

        return spooled_file
