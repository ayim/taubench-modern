"""Tests for calculate_agent_diff function."""

import pytest

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_package.diff import AgentDiffResult, calculate_agent_diff
from agent_platform.core.agent_package.diff_utils.types import DiffResult
from agent_platform.core.agent_package.spec import SpecAgent
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.selected_tools import SelectedToolConfig, SelectedTools


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


def create_minimal_spec_agent(**overrides) -> SpecAgent:
    """Create a minimal SpecAgent instance for testing."""
    defaults = {
        "name": "Test Agent",
        "description": "Test Description",
        "version": "1.0.0",
        "action-packages": [],
    }
    defaults.update(overrides)
    return SpecAgent.model_validate(defaults)


def find_change(changes: list[DiffResult], field_path: str, exact: bool = False) -> DiffResult | None:
    """Find a change by field_path.

    Args:
        changes: List of DiffResult objects.
        field_path: The field path to search for.
        exact: If True, match exactly. If False, match as substring.
    """
    for change in changes:
        if exact:
            if change.field_path == field_path:
                return change
        elif (
            change.field_path == field_path
            # this is for nested fields - extra.welcome_message, etc.
            # example: extra.welcome_message
            or change.field_path.startswith(f"{field_path}.")
            # this is for array fields - action_packages, mcp_servers, etc.
            # example: action_packages[0].name
            or change.field_path.startswith(f"{field_path}[")
        ):
            return change
    return None


class TestCalculateAgentDiff:
    """Tests for the calculate_agent_diff function."""

    @pytest.mark.asyncio
    async def test_no_changes_when_synced(self):
        """Test that no changes are detected for equivalent agents."""
        agent = create_minimal_agent(
            name="Test Agent",
            description="Test Description",
            version="1.0.0",
        )
        spec = create_minimal_spec_agent(
            name="Test Agent",
            description="Test Description",
            version="1.0.0",
        )

        result = await calculate_agent_diff(
            deployed_agent=agent,
            spec_agent=spec,
            spec_runbook="# Test Runbook",
        )

        # Assert AgentDiffResult structure
        assert isinstance(result, AgentDiffResult)
        assert result.is_synced is True
        assert isinstance(result.changes, list)
        assert len(result.changes) == 0

        # Assert model_dump works correctly
        dumped = result.model_dump()
        assert dumped == {"is_synced": True, "changes": []}

    @pytest.mark.asyncio
    async def test_detects_name_change(self):
        """Test that name changes are detected."""
        agent = create_minimal_agent(name="Old Name")
        spec = create_minimal_spec_agent(name="New Name")

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        # Assert AgentDiffResult
        assert isinstance(result, AgentDiffResult)
        assert result.is_synced is False

        # Assert specific change (use exact=True for top-level field)
        name_change = find_change(result.changes, "name", exact=True)
        assert name_change is not None
        assert isinstance(name_change, DiffResult)
        assert name_change.change == "update"
        assert name_change.deployed_value == "Old Name"
        assert name_change.package_value == "New Name"

    @pytest.mark.asyncio
    async def test_detects_version_change(self):
        """Test that version changes are detected."""
        agent = create_minimal_agent(version="1.0.0")
        spec = create_minimal_spec_agent(version="2.0.0")

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        version_change = find_change(result.changes, "version", exact=True)
        assert version_change is not None
        assert version_change.change == "update"
        assert version_change.deployed_value == "1.0.0"
        assert version_change.package_value == "2.0.0"

    @pytest.mark.asyncio
    async def test_detects_action_package_added(self):
        """Test that added action packages are detected."""
        agent = create_minimal_agent(action_packages=[])
        spec = create_minimal_spec_agent(
            **{"action-packages": [{"name": "new-pkg", "organization": "Org", "version": "1.0"}]}
        )

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        ap_change = find_change(result.changes, "action_packages")
        assert ap_change is not None
        assert ap_change.change == "add"
        assert ap_change.deployed_value is None
        assert ap_change.package_value is not None
        # The package_value should contain the action package data
        assert ap_change.package_value["name"] == "new-pkg"

    @pytest.mark.asyncio
    async def test_detects_action_package_removed(self):
        """Test that removed action packages are detected."""
        agent = create_minimal_agent(action_packages=[ActionPackage(name="old-pkg", organization="Org", version="1.0")])
        spec = create_minimal_spec_agent(**{"action-packages": []})

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        ap_change = find_change(result.changes, "action_packages")
        assert ap_change is not None
        assert ap_change.change == "delete"
        assert ap_change.deployed_value is not None
        assert ap_change.deployed_value["name"] == "old-pkg"
        assert ap_change.package_value is None

    @pytest.mark.asyncio
    async def test_detects_mcp_server_changes(self):
        """Test that MCP server changes are detected."""
        agent = create_minimal_agent(mcp_servers=[MCPServer(name="server1", url="http://localhost:8080")])
        spec = create_minimal_spec_agent(**{"mcp-servers": [{"name": "server2", "url": "http://localhost:9090"}]})

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        mcp_changes = [c for c in result.changes if "mcp_servers" in c.field_path]
        assert len(mcp_changes) >= 1

        # Verify the MCP server change is detected
        # server1 -> server2 means we should see either:
        # - An update at mcp_servers[0].name
        # - Or delete server1 + add server2
        deployed_servers = {c.deployed_value for c in mcp_changes if c.deployed_value}
        package_servers = {c.package_value for c in mcp_changes if c.package_value}

        # The deployed value should reference server1, package value should reference server2
        assert any("server1" in str(v) for v in deployed_servers) or any(
            isinstance(c.deployed_value, dict) and c.deployed_value.get("name") == "server1" for c in mcp_changes
        )
        assert any("server2" in str(v) for v in package_servers) or any(
            isinstance(c.package_value, dict) and c.package_value.get("name") == "server2" for c in mcp_changes
        )

    @pytest.mark.asyncio
    async def test_detects_selected_tools_changes(self):
        """Test that selected tools changes are detected."""
        agent = create_minimal_agent(selected_tools=SelectedTools(tools=[SelectedToolConfig(name="tool1")]))
        spec = create_minimal_spec_agent(**{"selected-tools": {"tools": [{"name": "tool2"}]}})

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        tool_changes = [c for c in result.changes if "selected_tools" in c.field_path]
        assert len(tool_changes) >= 1

        # Verify the tool name change is detected
        # tool1 -> tool2 means we should see either:
        # - An update at selected_tools.tools[0].name
        # - Or delete tool1 + add tool2
        deployed_tools = {c.deployed_value for c in tool_changes if c.deployed_value}
        package_tools = {c.package_value for c in tool_changes if c.package_value}

        # The deployed value should reference tool1, package value should reference tool2
        assert any("tool1" in str(v) for v in deployed_tools) or any(
            c.deployed_value == {"name": "tool1"} for c in tool_changes
        )
        assert any("tool2" in str(v) for v in package_tools) or any(
            c.package_value == {"name": "tool2"} for c in tool_changes
        )

    @pytest.mark.asyncio
    async def test_detects_runbook_change(self):
        """Test that runbook changes are detected."""
        agent = create_minimal_agent(runbook_structured=Runbook(raw_text="# Old Runbook", content=[]))
        spec = create_minimal_spec_agent()

        result = await calculate_agent_diff(
            deployed_agent=agent,
            spec_agent=spec,
            spec_runbook="# New Runbook",
        )

        assert result.is_synced is False

        runbook_change = find_change(result.changes, "runbook", exact=True)
        assert runbook_change is not None
        assert runbook_change.change == "update"
        assert runbook_change.deployed_value == "# Old Runbook"
        assert runbook_change.package_value == "# New Runbook"

    @pytest.mark.asyncio
    async def test_detects_question_groups_added(self):
        """Test that added question groups are detected."""
        agent = create_minimal_agent(question_groups=[])
        spec = create_minimal_spec_agent()
        groups = [QuestionGroup(title="Q1", questions=["Question?"])]

        result = await calculate_agent_diff(
            deployed_agent=agent,
            spec_agent=spec,
            spec_question_groups=groups,
        )

        assert result.is_synced is False

        qg_change = find_change(result.changes, "question_groups")
        assert qg_change is not None
        assert qg_change.change == "add"
        assert qg_change.deployed_value is None
        assert qg_change.package_value is not None
        assert qg_change.package_value["title"] == "Q1"

    @pytest.mark.asyncio
    async def test_detects_question_groups_updated(self):
        """Test that updated question groups are detected."""
        agent = create_minimal_agent(question_groups=[QuestionGroup(title="Q1", questions=["Old question?"])])
        spec = create_minimal_spec_agent()
        groups = [QuestionGroup(title="Q1", questions=["New question?"])]

        result = await calculate_agent_diff(
            deployed_agent=agent,
            spec_agent=spec,
            spec_question_groups=groups,
        )

        assert result.is_synced is False

        qg_changes = [c for c in result.changes if "question_groups" in c.field_path]
        assert len(qg_changes) >= 1

        # add+delete pairs at the same path are consolidated into an update
        update_change = next((c for c in qg_changes if c.change == "update"), None)

        assert update_change is not None
        assert update_change.field_path == "question_groups[0].questions[0]"
        assert update_change.deployed_value == "Old question?"
        assert update_change.package_value == "New question?"

    @pytest.mark.asyncio
    async def test_detects_conversation_starter_change(self):
        """Test that conversation starter changes are detected."""
        agent = create_minimal_agent(extra={"conversation_starter": "Hello there!"})
        spec = create_minimal_spec_agent(**{"conversation-starter": "Welcome aboard!"})

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        # conversation_starter is in extra dict, so field path is extra.conversation_starter
        cs_change = find_change(result.changes, "extra.conversation_starter", exact=True)
        assert cs_change is not None
        assert cs_change.change == "update"
        assert cs_change.deployed_value == "Hello there!"
        assert cs_change.package_value == "Welcome aboard!"

    @pytest.mark.asyncio
    async def test_detects_agent_settings_change(self):
        """Test that agent settings changes are detected."""
        agent = create_minimal_agent(extra={"agent_settings": {"key1": "value1"}})
        spec = create_minimal_spec_agent(**{"agent-settings": {"key2": "value2"}})

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        # agent_settings is in extra dict, changes are at extra.agent_settings.key1, etc.
        settings_changes = [c for c in result.changes if "extra.agent_settings" in c.field_path]
        assert len(settings_changes) >= 2  # delete key1, add key2

        # Should detect both the removal of key1 and addition of key2
        change_types = {c.change for c in settings_changes}
        assert "delete" in change_types
        assert "add" in change_types

        # Verify specific changes
        key1_change = find_change(result.changes, "extra.agent_settings.key1", exact=True)
        assert key1_change is not None
        assert key1_change.change == "delete"
        assert key1_change.deployed_value == "value1"
        assert key1_change.package_value is None

        key2_change = find_change(result.changes, "extra.agent_settings.key2", exact=True)
        assert key2_change is not None
        assert key2_change.change == "add"
        assert key2_change.deployed_value is None
        assert key2_change.package_value == "value2"

    @pytest.mark.asyncio
    async def test_detects_document_intelligence_change(self):
        """Test that document intelligence changes are detected."""
        agent = create_minimal_agent(extra={"document_intelligence": "v2"})
        spec = create_minimal_spec_agent(**{"document-intelligence": "v2.1"})

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        di_change = find_change(result.changes, "extra.document_intelligence", exact=True)
        assert di_change is not None
        assert di_change.change == "update"
        assert di_change.deployed_value == "v2"
        assert di_change.package_value == "v2.1"

    @pytest.mark.asyncio
    async def test_detects_docker_mcp_gateway_change(self):
        """Test that docker MCP gateway changes are detected."""
        agent = create_minimal_agent(
            extra={"docker_mcp_gateway": {"catalog": "old-catalog", "servers": {"postgres": {"env": "prod"}}}}
        )
        spec = create_minimal_spec_agent(
            **{"docker-mcp-gateway": {"catalog": "new-catalog", "servers": {"postgres": {"env": "prod"}}}}
        )

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        # Should detect the catalog change
        catalog_change = find_change(result.changes, "extra.docker_mcp_gateway.catalog", exact=True)
        assert catalog_change is not None
        assert catalog_change.change == "update"
        assert catalog_change.deployed_value == "old-catalog"
        assert catalog_change.package_value == "new-catalog"

    @pytest.mark.asyncio
    async def test_detects_docker_mcp_gateway_removed(self):
        """Test that removing docker MCP gateway is detected."""
        agent = create_minimal_agent(
            extra={"docker_mcp_gateway": {"catalog": "my-catalog", "servers": {"postgres": {"env": "prod"}}}}
        )
        spec = create_minimal_spec_agent()  # No docker-mcp-gateway

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        assert result.is_synced is False

        gateway_change = find_change(result.changes, "extra.docker_mcp_gateway")
        assert gateway_change is not None
        assert gateway_change.change == "delete"
        assert gateway_change.deployed_value is not None
        assert gateway_change.package_value is None

    @pytest.mark.asyncio
    async def test_multiple_changes_detected(self):
        """Test a scenario with multiple changes across different fields."""
        agent = create_minimal_agent(
            name="Old Agent",
            version="1.0.0",
            action_packages=[ActionPackage(name="pkg1", organization="Org", version="1.0")],
            mcp_servers=[MCPServer(name="server1", url="http://localhost:8080")],
        )

        spec = create_minimal_spec_agent(
            name="New Agent",
            version="2.0.0",
            **{
                "action-packages": [{"name": "pkg2", "organization": "Org", "version": "1.0"}],
                "mcp-servers": [{"name": "server2", "url": "http://localhost:9090"}],
            },
        )

        result = await calculate_agent_diff(deployed_agent=agent, spec_agent=spec)

        # Assert overall result
        assert isinstance(result, AgentDiffResult)
        assert result.is_synced is False
        assert len(result.changes) >= 4  # At least name, version, action_packages, mcp_servers

        # Assert each change type (use exact=True for top-level fields to avoid matching nested fields)
        name_change = find_change(result.changes, "name", exact=True)
        assert name_change is not None
        assert name_change.change == "update"
        assert name_change.deployed_value == "Old Agent"
        assert name_change.package_value == "New Agent"

        version_change = find_change(result.changes, "version", exact=True)
        assert version_change is not None
        assert version_change.change == "update"
        assert version_change.deployed_value == "1.0.0"
        assert version_change.package_value == "2.0.0"

        # Verify action_packages and mcp_servers have changes
        ap_changes = [c for c in result.changes if "action_packages" in c.field_path]
        assert len(ap_changes) >= 1

        mcp_changes = [c for c in result.changes if "mcp_servers" in c.field_path]
        assert len(mcp_changes) >= 1

        # Assert model_dump produces valid output
        dumped = result.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["is_synced"] is False
        assert isinstance(dumped["changes"], list)
        assert len(dumped["changes"]) == len(result.changes)

        # Each dumped change should have the expected keys
        for change_dict in dumped["changes"]:
            assert "change" in change_dict
            assert "field_path" in change_dict
            assert "deployed_value" in change_dict
            assert "package_value" in change_dict
            assert change_dict["change"] in ("add", "update", "delete")

        # Verify expected changes are present in dumped output
        dumped_by_path = {c["field_path"]: c for c in dumped["changes"]}

        # Name change
        assert "name" in dumped_by_path
        assert dumped_by_path["name"]["change"] == "update"
        assert dumped_by_path["name"]["deployed_value"] == "Old Agent"
        assert dumped_by_path["name"]["package_value"] == "New Agent"

        # Version change
        assert "version" in dumped_by_path
        assert dumped_by_path["version"]["change"] == "update"
        assert dumped_by_path["version"]["deployed_value"] == "1.0.0"
        assert dumped_by_path["version"]["package_value"] == "2.0.0"

        # Action packages changes (pkg1 -> pkg2 at index 0)
        ap_dumped = [c for c in dumped["changes"] if "action_packages" in c["field_path"]]
        assert len(ap_dumped) >= 1
        # Should have action_packages[0].name update
        ap_name_change = next((c for c in ap_dumped if c["field_path"] == "action_packages[0].name"), None)
        assert ap_name_change is not None
        assert ap_name_change["change"] == "update"
        assert ap_name_change["deployed_value"] == "pkg1"
        assert ap_name_change["package_value"] == "pkg2"

        # MCP servers changes (server1 -> server2 at index 0)
        mcp_dumped = [c for c in dumped["changes"] if "mcp_servers" in c["field_path"]]
        assert len(mcp_dumped) >= 1
        # Should have mcp_servers[0].name update
        mcp_name_change = next((c for c in mcp_dumped if c["field_path"] == "mcp_servers[0].name"), None)
        assert mcp_name_change is not None
        assert mcp_name_change["change"] == "update"
        assert mcp_name_change["deployed_value"] == "server1"
        assert mcp_name_change["package_value"] == "server2"
        # Should have mcp_servers[0].url update
        mcp_url_change = next((c for c in mcp_dumped if c["field_path"] == "mcp_servers[0].url"), None)
        assert mcp_url_change is not None
        assert mcp_url_change["change"] == "update"
        assert mcp_url_change["deployed_value"] == "http://localhost:8080"
        assert mcp_url_change["package_value"] == "http://localhost:9090"

    @pytest.mark.asyncio
    async def test_agent_architecture_version_ignored_in_comparison(self):
        """Test that agent_architecture.version is not compared.

        The architecture version is not part of the spec (always defaults to 1.0.0),
        so differences in version should not cause a diff.
        """
        # Deployed agent has a different architecture version
        agent = create_minimal_agent(
            agent_architecture=AgentArchitecture(
                name="agent_platform.architectures.default",
                version="2.5.0",  # Different from the 1.0.0 default in spec
            ),
        )
        spec = create_minimal_spec_agent()

        result = await calculate_agent_diff(
            deployed_agent=agent,
            spec_agent=spec,
            spec_runbook="# Test Runbook",
        )

        # Should be synced - architecture version difference should be ignored
        assert result.is_synced is True
        assert len(result.changes) == 0

        # Verify no agent_architecture changes are reported
        arch_changes = [c for c in result.changes if "agent_architecture" in c.field_path]
        assert len(arch_changes) == 0

    @pytest.mark.asyncio
    async def test_extra_empty_string_equivalent_to_none(self):
        """Test that empty strings in extra dict are equivalent to None.

        Deployed state may store empty strings, while spec state stores None
        for optional fields. These should be treated as equivalent.
        """
        # Deployed agent has empty strings in extra
        agent = create_minimal_agent(
            extra={
                "welcome_message": "",
                "conversation_starter": "",
                "document_intelligence": "",
            },
        )
        # Spec agent has no values for these fields (will be None)
        spec = create_minimal_spec_agent()

        result = await calculate_agent_diff(
            deployed_agent=agent,
            spec_agent=spec,
            spec_runbook="# Test Runbook",
        )

        # Should be synced - empty strings and None should be equivalent
        assert result.is_synced is True
        assert len(result.changes) == 0

        # Verify no extra field changes are reported
        extra_changes = [c for c in result.changes if "extra" in c.field_path]
        assert len(extra_changes) == 0

    @pytest.mark.asyncio
    async def test_extra_non_empty_string_still_detected(self):
        """Test that non-empty strings in extra dict are still detected as different."""
        # Deployed agent has actual values in extra
        agent = create_minimal_agent(
            extra={
                "welcome_message": "Hello!",
            },
        )
        # Spec agent has no values for these fields
        spec = create_minimal_spec_agent()

        result = await calculate_agent_diff(
            deployed_agent=agent,
            spec_agent=spec,
            spec_runbook="# Test Runbook",
        )

        # Should not be synced - non-empty string is different from None
        assert result.is_synced is False

        # Should detect the welcome_message difference
        wm_change = find_change(result.changes, "extra.welcome_message", exact=True)
        assert wm_change is not None
        assert wm_change.change == "delete"
        assert wm_change.deployed_value == "Hello!"
        assert wm_change.package_value is None
