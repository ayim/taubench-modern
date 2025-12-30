import json
from typing import TYPE_CHECKING, Any

from structlog import get_logger

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.base import BasePackageHandler, YAMLHandler
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
    from agent_platform.core.agent_package.handler.action_package import (
        ActionPackageContent,
        ActionPackageHandler,
        ActionPackagePath,
    )

logger = get_logger(__name__)


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
            logger.warning(
                "Agent spec file missing from package",
                expected_file=AgentPackageConfig.agent_spec_filename,
            )
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
        agent = spec.agent_package.agents[0]
        return agent

    async def read_metadata(self) -> AgentPackageMetadata:
        if self.cached_metadata is not None:
            return self.cached_metadata

        metadata_raw = await self.read_file(AgentPackageConfig.metadata_filename)
        # Even though agent-spec.yaml supports only one Agent definition, it does it
        # via an array - metadata follows the same pattern, so we need to explicitly
        # cast the metadata to list here, so we can select the first element.
        metadata_parsed: list[dict[str, Any]] = json.loads(metadata_raw.decode())

        metadata = AgentPackageMetadata.model_validate(metadata_parsed[0])
        return metadata

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
            guide_yaml = YAMLHandler().reader.load(guide_bytes.decode("utf-8"))

            if not isinstance(guide_yaml, dict):
                logger.warning("Conversation guide is not a valid YAML dictionary")
                return []

            qg_list = guide_yaml.get("question-groups", [])
            question_groups = [QuestionGroup.model_validate(qg) for qg in qg_list if isinstance(qg, dict)]
            return question_groups
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
        paths = [ap.path for ap in spec_agent.action_packages if ap.path]
        return paths

    async def get_action_packages_handlers(self) -> list[tuple[str, "ActionPackageHandler"]]:
        """Get all Action Package handlers from the agent package."""
        from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler

        action_package_paths = await self.list_action_package_paths()
        handlers = [
            (path, await ActionPackageHandler.from_bytes(await self.read_action_package_zip_raw(path)))
            for path in action_package_paths
        ]
        return handlers

    async def read_action_package_zip_raw(self, action_package_zip_path: str) -> bytes:
        path = f"{AgentPackageConfig.actions_dirname}/{action_package_zip_path}"
        data = await self.read_file(path)
        return data

    async def read_semantic_data_model_raw(self, semantic_data_model_filename: str) -> bytes:
        path = f"{AgentPackageConfig.semantic_data_models_dirname}/{semantic_data_model_filename}"
        return await self.read_file(path)

    async def read_semantic_data_model(self, semantic_data_model_filename: str) -> SemanticDataModel | None:
        try:
            sdm_raw = await self.read_semantic_data_model_raw(semantic_data_model_filename)
            if not sdm_raw:
                return None

            # Parse YAML (Snowflake Cortex Analyst semantic model format)
            sdm_yaml = YAMLHandler().reader.load(sdm_raw.decode("utf-8"))

            if not isinstance(sdm_yaml, dict):
                logger.warning(
                    "SDM file does not contain valid YAML dict, skipping",
                    sdm_filename=semantic_data_model_filename,
                )
                return None

            sdm = model_validate_sdm(sdm_yaml)
            return sdm

        except Exception as e:
            logger.warning(
                "Failed to read Semantic Data Model",
                path=semantic_data_model_filename,
                error=str(e),
            )
            return None

    async def read_all_semantic_data_models(self) -> dict[str, SemanticDataModel]:
        result: dict[str, SemanticDataModel] = {}

        spec_agent = await self.get_spec_agent()

        sdm_refs = spec_agent.semantic_data_models or []

        if not sdm_refs:
            return result

        for sdm_ref in sdm_refs:
            if not sdm_ref.name:
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
            return ""

        try:
            icon_bytes = await self.read_file(icon_filename)
            icon_base64 = convert_image_bytes_to_base64(icon_bytes, icon_filename)
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
            return ""

        try:
            changelog_bytes = await self.read_file(changelog_filename)
            changelog_content = changelog_bytes.decode("utf-8")
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
            return ""

        try:
            readme_bytes = await self.read_file(readme_filename)
            readme_content = readme_bytes.decode("utf-8")
            return readme_content
        except Exception as e:
            logger.warning(
                "Failed to load readme",
                readme_filename=readme_filename,
                error=str(e),
            )
            return ""

    async def write_agent_spec(self, agent_spec: AgentPackageSpec) -> None:
        """Write the agent spec to the zip file.

        Args:
            agent_spec: The agent spec to write.
        """
        spec_yaml = agent_spec.to_yaml()
        await self.write_file(AgentPackageConfig.agent_spec_filename, spec_yaml.encode("utf-8"))

    async def write_runbook(self, runbook_text: str) -> None:
        """Write the runbook to the zip file.

        Args:
            runbook_text: The runbook text to write.
        """
        await self.write_file(AgentPackageConfig.runbook_filename, runbook_text.encode("utf-8"))

    async def write_conversation_guide(self, question_groups: list[QuestionGroup]) -> None:
        """Write the conversation guide to the zip file.

        Args:
            question_groups: The question groups to write.
        """
        if not question_groups:
            return

        import io

        yaml_buffer = io.StringIO()
        guide_dict = {
            "question-groups": [qg.model_dump() for qg in question_groups],
        }

        YAMLHandler().writer.dump(guide_dict, yaml_buffer)
        await self.write_file(AgentPackageConfig.conversation_guide_filename, yaml_buffer.getvalue().encode("utf-8"))

    async def write_metadata(self, metadata: AgentPackageMetadata) -> None:
        """Write the metadata to the zip file.

        Args:
            metadata: The metadata to write.
        """
        import io

        json_buffer = io.StringIO()
        # Even though agent-spec.yaml supports only one Agent definition, it does it
        # via an array - metadata follows the same pattern, so we need to explicitly
        # cast the metadata to list here, so we can select the first element.
        json.dump([metadata.model_dump()], json_buffer, indent=2)
        await self.write_file(AgentPackageConfig.metadata_filename, json_buffer.getvalue().encode("utf-8"))

    async def write_semantic_data_model(self, semantic_data_model: SemanticDataModel, filename: str) -> None:
        """Write a semantic data model to the zip file.

        Args:
            semantic_data_model: The semantic data model to write.
            filename: The filename for the semantic data model.
        """
        import io

        yaml_buffer = io.StringIO()
        YAMLHandler().writer.dump(model_dump_sdm(semantic_data_model), yaml_buffer)
        await self.write_file(
            f"{AgentPackageConfig.semantic_data_models_dirname}/{filename}", yaml_buffer.getvalue().encode("utf-8")
        )

    async def write_action_package(
        self, action_package_path: "ActionPackagePath", action_package_content: "ActionPackageContent"
    ) -> None:
        """Write the action packages to the zip file.

        Args:
            action_packages: The action packages to write.
        """
        for file_path, file_content in action_package_content.items():
            full_path = f"{AgentPackageConfig.actions_dirname}/{action_package_path}/{file_path}"
            await self.write_file(full_path, file_content)
