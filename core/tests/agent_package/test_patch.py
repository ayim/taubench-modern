"""Tests for create_agent_project_patch function."""

import zipfile
from io import BytesIO

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.patch import (
    _get_changed_file_categories,
    _get_new_action_packages,
    create_agent_project_patch,
)
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.selected_tools import SelectedTools


def create_minimal_agent(**overrides) -> Agent:
    """Create a minimal Agent instance for testing."""
    from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
    from agent_platform.core.utils.secret_str import SecretString

    defaults = {
        "name": "Test Agent",
        "description": "Test Description",
        "user_id": "test_user",
        "version": "1.0.0",
        "runbook_structured": Runbook(raw_text="# Test Runbook", content=[]),
        "platform_configs": [
            OpenAIPlatformParameters(
                name="test-openai",
                openai_api_key=SecretString("test-key"),
            )
        ],
        "agent_architecture": AgentArchitecture(
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
        "action_packages": [],
        "mcp_servers": [],
        "selected_tools": SelectedTools(),
        "question_groups": [],
        "mode": "conversational",
        "extra": {},
    }
    defaults.update(overrides)
    return Agent(**defaults)


async def create_agent_package_with_files(files: dict[str, bytes]) -> AgentPackageHandler:
    """Create an AgentPackageHandler with the specified files."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    buffer.seek(0)
    return await AgentPackageHandler.from_bytes(buffer.read())


async def read_patch_zip(patch_generator) -> dict[str, bytes]:
    """Read all files from a patch generator into a dict."""
    chunks = []
    async for chunk in patch_generator:
        chunks.append(chunk)

    if not chunks:
        return {}

    buffer = BytesIO(b"".join(chunks))
    result = {}
    with zipfile.ZipFile(buffer, "r") as zf:
        for name in zf.namelist():
            if not name.endswith("/"):
                result[name] = zf.read(name)
    return result


class TestGetChangedFileCategories:
    """Tests for the _get_changed_file_categories helper."""

    def test_spec_field_changes_include_spec_category(self):
        """Test that changes to spec fields result in 'spec' category."""
        from agent_platform.core.agent_package.diff_utils.types import AgentDiffResult, DiffResult
        from agent_platform.core.agent_package.spec import AgentPackageSpecFileFields

        diff_result = AgentDiffResult(
            is_synced=False,
            changes=[
                DiffResult(change="update", field_path="name", deployed_value="Old", package_value="New"),
            ],
        )
        categories = _get_changed_file_categories(diff_result)
        assert AgentPackageSpecFileFields.spec in categories

    def test_runbook_changes_include_runbook_category(self):
        """Test that runbook changes result in 'runbook' category."""
        from agent_platform.core.agent_package.diff_utils.types import AgentDiffResult, DiffResult
        from agent_platform.core.agent_package.spec import AgentPackageSpecFileFields

        diff_result = AgentDiffResult(
            is_synced=False,
            changes=[
                DiffResult(change="update", field_path="runbook", deployed_value="Old", package_value="New"),
            ],
        )
        categories = _get_changed_file_categories(diff_result)
        assert AgentPackageSpecFileFields.runbook in categories

    def test_question_groups_changes_include_conversation_guide_category(self):
        """Test that question_groups changes result in 'conversation_guide' category."""
        from agent_platform.core.agent_package.diff_utils.types import AgentDiffResult, DiffResult
        from agent_platform.core.agent_package.spec import AgentPackageSpecFileFields

        diff_result = AgentDiffResult(
            is_synced=False,
            changes=[
                DiffResult(change="add", field_path="question_groups[0]", deployed_value=None, package_value={}),
            ],
        )
        categories = _get_changed_file_categories(diff_result)
        assert AgentPackageSpecFileFields.conversation_guide in categories

    def test_sdm_changes_include_sdm_category(self):
        """Test that semantic data model changes result in 'semantic_data_models' category."""
        from agent_platform.core.agent_package.diff_utils.types import AgentDiffResult, DiffResult
        from agent_platform.core.agent_package.spec import AgentPackageSpecFileFields

        diff_result = AgentDiffResult(
            is_synced=False,
            changes=[
                DiffResult(
                    change="add", field_path="semantic_data_models.customers", deployed_value=None, package_value="new"
                ),
            ],
        )
        categories = _get_changed_file_categories(diff_result)
        assert AgentPackageSpecFileFields.semantic_data_models in categories

    def test_extra_field_changes_include_spec_category(self):
        """Test that extra.* field changes result in 'spec' category."""
        from agent_platform.core.agent_package.diff_utils.types import AgentDiffResult, DiffResult
        from agent_platform.core.agent_package.spec import AgentPackageSpecFileFields

        diff_result = AgentDiffResult(
            is_synced=False,
            changes=[
                DiffResult(
                    change="update", field_path="extra.welcome_message", deployed_value="Old", package_value="New"
                ),
            ],
        )
        categories = _get_changed_file_categories(diff_result)
        assert AgentPackageSpecFileFields.spec in categories


class TestGetNewActionPackages:
    """Tests for the _get_new_action_packages helper."""

    def test_identifies_new_action_packages(self):
        """Test that new action packages in deployed are identified."""
        from agent_platform.core.actions.action_package import ActionPackage
        from agent_platform.core.agent_package.spec import SpecAgent

        deployed_agent = create_minimal_agent(
            action_packages=[
                ActionPackage(name="action-a", organization="OrgA", version="1.0.0"),
                ActionPackage(name="action-b", organization="OrgB", version="2.0.0"),
            ]
        )

        # spec_agent only has action-a
        spec_agent = SpecAgent.model_validate(
            {
                "name": "Test",
                "description": "Test",
                "version": "1.0.0",
                "action-packages": [{"name": "action-a", "organization": "OrgA", "version": "1.0.0"}],
            }
        )

        new_packages = _get_new_action_packages(deployed_agent, spec_agent)
        assert new_packages == {("OrgB", "action-b", "2.0.0")}

    def test_no_new_packages_when_all_match(self):
        """Test that no new packages are returned when all match."""
        from agent_platform.core.actions.action_package import ActionPackage
        from agent_platform.core.agent_package.spec import SpecAgent

        deployed_agent = create_minimal_agent(
            action_packages=[
                ActionPackage(name="action-a", organization="OrgA", version="1.0.0"),
            ]
        )

        spec_agent = SpecAgent.model_validate(
            {
                "name": "Test",
                "description": "Test",
                "version": "1.0.0",
                "action-packages": [{"name": "action-a", "organization": "OrgA", "version": "1.0.0"}],
            }
        )

        new_packages = _get_new_action_packages(deployed_agent, spec_agent)
        assert new_packages == set()

    def test_version_difference_is_new_package(self):
        """Test that a different version is considered a new package."""
        from agent_platform.core.actions.action_package import ActionPackage
        from agent_platform.core.agent_package.spec import SpecAgent

        deployed_agent = create_minimal_agent(
            action_packages=[
                ActionPackage(name="action-a", organization="OrgA", version="2.0.0"),
            ]
        )

        spec_agent = SpecAgent.model_validate(
            {
                "name": "Test",
                "description": "Test",
                "version": "1.0.0",
                "action-packages": [{"name": "action-a", "organization": "OrgA", "version": "1.0.0"}],
            }
        )

        new_packages = _get_new_action_packages(deployed_agent, spec_agent)
        assert new_packages == {("OrgA", "action-a", "2.0.0")}


class TestCreateAgentProjectPatch:
    """Tests for the create_agent_project_patch function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_models_are_synced(self):
        """Test that None is returned when deployed and incoming models match (no patch needed)."""
        agent = create_minimal_agent()

        # Create incoming package with matching content
        from agent_platform.core.agent_package.spec import AgentSpecGenerator

        agent_spec = AgentSpecGenerator.from_agent(agent, action_package_type="folder")
        spec_yaml = agent_spec.to_yaml().encode("utf-8")

        incoming_files = {
            AgentPackageConfig.agent_spec_filename: spec_yaml,
            AgentPackageConfig.runbook_filename: b"# Test Runbook",
        }
        handler = await create_agent_package_with_files(incoming_files)

        patch_gen = await create_agent_project_patch(
            deployed_agent=agent,
            deployed_sdms=[],
            agent_package_handler=handler,
        )

        assert patch_gen is None

    @pytest.mark.asyncio
    async def test_includes_spec_when_name_changes(self):
        """Test that agent-spec.yaml is included when name differs."""
        agent = create_minimal_agent(name="Deployed Name")

        from agent_platform.core.agent_package.spec import AgentSpecGenerator

        # Create incoming spec with different name
        incoming_agent = create_minimal_agent(name="Incoming Name")
        agent_spec = AgentSpecGenerator.from_agent(incoming_agent, action_package_type="folder")
        spec_yaml = agent_spec.to_yaml().encode("utf-8")

        incoming_files = {
            AgentPackageConfig.agent_spec_filename: spec_yaml,
            AgentPackageConfig.runbook_filename: b"# Test Runbook",
        }
        handler = await create_agent_package_with_files(incoming_files)

        patch_gen = await create_agent_project_patch(
            deployed_agent=agent,
            deployed_sdms=[],
            agent_package_handler=handler,
        )
        patch_files = await read_patch_zip(patch_gen)

        assert AgentPackageConfig.agent_spec_filename in patch_files

    @pytest.mark.asyncio
    async def test_includes_runbook_when_runbook_changes(self):
        """Test that runbook is included when runbook content differs."""
        agent = create_minimal_agent(runbook_structured=Runbook(raw_text="# Deployed Runbook", content=[]))

        from agent_platform.core.agent_package.spec import AgentSpecGenerator

        agent_spec = AgentSpecGenerator.from_agent(agent, action_package_type="folder")
        spec_yaml = agent_spec.to_yaml().encode("utf-8")

        incoming_files = {
            AgentPackageConfig.agent_spec_filename: spec_yaml,
            AgentPackageConfig.runbook_filename: b"# Different Runbook",
        }
        handler = await create_agent_package_with_files(incoming_files)

        patch_gen = await create_agent_project_patch(
            deployed_agent=agent,
            deployed_sdms=[],
            agent_package_handler=handler,
        )
        patch_files = await read_patch_zip(patch_gen)

        assert AgentPackageConfig.runbook_filename in patch_files
        assert patch_files[AgentPackageConfig.runbook_filename] == b"# Deployed Runbook"

    @pytest.mark.asyncio
    async def test_includes_conversation_guide_when_question_groups_differ(self):
        """Test that conversation guide is included when question groups differ."""
        from agent_platform.core.agent.question_group import QuestionGroup

        agent = create_minimal_agent(question_groups=[QuestionGroup(title="Q1", questions=["Question?"])])

        from agent_platform.core.agent_package.spec import AgentSpecGenerator

        agent_spec = AgentSpecGenerator.from_agent(agent, action_package_type="folder")
        spec_yaml = agent_spec.to_yaml().encode("utf-8")

        # Incoming package does NOT have conversation-guide.yaml
        incoming_files = {
            AgentPackageConfig.agent_spec_filename: spec_yaml,
            AgentPackageConfig.runbook_filename: b"# Test Runbook",
        }
        handler = await create_agent_package_with_files(incoming_files)

        patch_gen = await create_agent_project_patch(
            deployed_agent=agent,
            deployed_sdms=[],
            agent_package_handler=handler,
        )
        patch_files = await read_patch_zip(patch_gen)

        # conversation-guide.yaml should be in the patch
        assert AgentPackageConfig.conversation_guide_filename in patch_files

    @pytest.mark.asyncio
    async def test_includes_sdm_when_sdms_differ(self):
        """Test that SDM files are included when semantic data models differ."""
        from agent_platform.core.agent_package.spec import AgentSpecGenerator
        from agent_platform.core.semantic_data_model.types import SemanticDataModel

        agent = create_minimal_agent()
        deployed_sdms = [
            SemanticDataModel(
                name="customers",
                description="Customer data",
                tables=[],
                relationships=[],
                errors=[],
                verified_queries=[],
                metadata=None,
            )
        ]
        # Incoming spec does NOT reference the SDM (no semantic_data_models)
        agent_spec = AgentSpecGenerator.from_agent(agent, semantic_data_models=None, action_package_type="folder")
        spec_yaml = agent_spec.to_yaml().encode("utf-8")

        # Incoming package does NOT have the SDM
        incoming_files = {
            AgentPackageConfig.agent_spec_filename: spec_yaml,
            AgentPackageConfig.runbook_filename: b"# Test Runbook",
        }
        handler = await create_agent_package_with_files(incoming_files)

        patch_gen = await create_agent_project_patch(
            deployed_agent=agent,
            deployed_sdms=deployed_sdms,
            agent_package_handler=handler,
        )
        patch_files = await read_patch_zip(patch_gen)

        # SDM file should be in the patch (filename is just the name, without .yaml extension)
        sdm_path = f"{AgentPackageConfig.semantic_data_models_dirname}/customers"
        assert sdm_path in patch_files


class TestActionPackagePatching:
    """Tests for action package patching based on (org, name, version) identity.

    These tests verify the behavior of _get_new_action_packages and the integration
    with action package URI expansion. Since URI expansion requires real URIs, these
    tests focus on the logic that determines which action packages are new. For
    full integration tests with URIs, see tests in a separate integration test module.
    """

    @pytest.mark.asyncio
    async def test_returns_none_when_all_action_packages_match(self):
        """Test that None is returned when all action packages match (nothing to patch)."""
        from agent_platform.core.actions.action_package import ActionPackage
        from agent_platform.core.agent_package.spec import AgentSpecGenerator

        action_packages = [
            ActionPackage(name="my-action", organization="TestOrg", version="1.0.0"),
        ]
        agent = create_minimal_agent(action_packages=action_packages)

        agent_spec = AgentSpecGenerator.from_agent(agent, action_package_type="folder")
        spec_yaml = agent_spec.to_yaml().encode("utf-8")

        incoming_files = {
            AgentPackageConfig.agent_spec_filename: spec_yaml,
            AgentPackageConfig.runbook_filename: b"# Test Runbook",
            f"{AgentPackageConfig.actions_dirname}/TestOrg/my-action/actions.py": b"def my_action(): pass",
            f"{AgentPackageConfig.actions_dirname}/TestOrg/my-action/package.yaml": b"name: my-action\nversion: 1.0.0",
        }
        handler = await create_agent_package_with_files(incoming_files)

        patch_gen = await create_agent_project_patch(
            deployed_agent=agent,
            deployed_sdms=[],
            agent_package_handler=handler,
        )

        # Everything matches, so None should be returned (204 No Content case)
        assert patch_gen is None

    @pytest.mark.asyncio
    async def test_new_action_packages_detected_without_uris(self):
        """Test that new action packages are detected even without URIs provided.

        When new action packages are detected but no URIs are provided, a patch
        with other changes (like spec) should still be returned. The action packages
        themselves won't be in the patch (no URIs to expand), but the patch is not None.
        """
        from agent_platform.core.actions.action_package import ActionPackage
        from agent_platform.core.agent_package.spec import AgentSpecGenerator

        # Deployed has two action packages
        action_packages = [
            ActionPackage(name="action-a", organization="OrgA", version="1.0.0"),
            ActionPackage(name="action-b", organization="OrgB", version="1.0.0"),
        ]
        agent = create_minimal_agent(action_packages=action_packages)

        # Incoming only has action-a (so action-b is "new" from deployed perspective)
        incoming_action_packages = [
            ActionPackage(name="action-a", organization="OrgA", version="1.0.0"),
        ]
        incoming_agent = create_minimal_agent(action_packages=incoming_action_packages)
        agent_spec = AgentSpecGenerator.from_agent(incoming_agent, action_package_type="folder")
        spec_yaml = agent_spec.to_yaml().encode("utf-8")

        incoming_files = {
            AgentPackageConfig.agent_spec_filename: spec_yaml,
            AgentPackageConfig.runbook_filename: b"# Test Runbook",
            f"{AgentPackageConfig.actions_dirname}/OrgA/action-a/actions.py": b"def action_a(): pass",
            f"{AgentPackageConfig.actions_dirname}/OrgA/action-a/package.yaml": b"name: action-a",
        }
        handler = await create_agent_package_with_files(incoming_files)

        # No URIs provided - should still detect there are differences
        patch_gen = await create_agent_project_patch(
            deployed_agent=agent,
            deployed_sdms=[],
            action_packages_uris=None,
            agent_package_handler=handler,
        )

        # There are differences (action packages differ in spec), so patch should not be None
        # The spec file will be included because action_packages list differs
        patch_files = await read_patch_zip(patch_gen)
        assert AgentPackageConfig.agent_spec_filename in patch_files

        # But without URIs, action packages themselves won't be in the patch
        action_b_path = f"{AgentPackageConfig.actions_dirname}/OrgB/action-b/actions.py"
        assert action_b_path not in patch_files

    def test_get_new_action_packages_identifies_new_packages(self):
        """Test that _get_new_action_packages correctly identifies new packages."""
        from agent_platform.core.actions.action_package import ActionPackage
        from agent_platform.core.agent_package.spec import SpecAgent

        # Deployed has two action packages
        action_packages = [
            ActionPackage(name="action-a", organization="OrgA", version="1.0.0"),
            ActionPackage(name="action-b", organization="OrgB", version="1.0.0"),
        ]
        agent = create_minimal_agent(action_packages=action_packages)

        # Spec (incoming) only has action-a
        spec_agent = SpecAgent.model_validate(
            {
                "name": "Test",
                "description": "Test",
                "version": "1.0.0",
                "action-packages": [{"name": "action-a", "organization": "OrgA", "version": "1.0.0"}],
            }
        )

        new_packages = _get_new_action_packages(agent, spec_agent)
        assert new_packages == {("OrgB", "action-b", "1.0.0")}

    def test_get_new_action_packages_version_difference_is_new(self):
        """Test that different version of same package is considered new."""
        from agent_platform.core.actions.action_package import ActionPackage
        from agent_platform.core.agent_package.spec import SpecAgent

        # Deployed has version 2.0.0
        action_packages = [
            ActionPackage(name="my-action", organization="TestOrg", version="2.0.0"),
        ]
        agent = create_minimal_agent(action_packages=action_packages)

        # Incoming has version 1.0.0
        spec_agent = SpecAgent.model_validate(
            {
                "name": "Test",
                "description": "Test",
                "version": "1.0.0",
                "action-packages": [{"name": "my-action", "organization": "TestOrg", "version": "1.0.0"}],
            }
        )

        new_packages = _get_new_action_packages(agent, spec_agent)
        # Version 2.0.0 is "new" because it doesn't exist in spec
        assert new_packages == {("TestOrg", "my-action", "2.0.0")}
