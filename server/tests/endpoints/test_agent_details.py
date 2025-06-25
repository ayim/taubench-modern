from unittest.mock import AsyncMock, patch

import pytest

from agent_platform.core.actions.action_package import ActionPackage, SecretString
from agent_platform.core.agent import Agent, AgentArchitecture
from agent_platform.core.runbook import Runbook
from agent_platform.core.user import User
from agent_platform.server.api.private_v2.agents import get_agent_details


@pytest.fixture
def mock_user():
    """Mock authenticated user for testing."""
    return User(user_id="test-user-123", sub="tenant:test-tenant:user:test-user")


@pytest.fixture
def mock_storage():
    return AsyncMock()


def create_test_agent(action_packages=None):
    """Helper function to create a test agent with given action packages."""
    return Agent(
        name="Test Agent",
        description="Test Description",
        user_id="test_user",
        version="1.0.0",
        action_packages=action_packages or [],
        runbook_structured=Runbook(raw_text="test runbook", content=[]),
        platform_configs=[],
        agent_architecture=AgentArchitecture(
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
    )


async def test_agent_details_no_action_packages(mock_user, mock_storage):
    """Test getting agent details for an agent with no action packages."""
    agent = create_test_agent()
    mock_storage.get_agent.return_value = agent

    result = await get_agent_details(
        user=mock_user,
        aid="test_agent",
        storage=mock_storage,
    )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 0


async def test_agent_details_one_action_package_online(mock_user, mock_storage):
    """Test getting agent details for an agent with one online action package."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
    )
    agent = create_test_agent(action_packages=[action_package])

    with patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions",
        return_value=[AsyncMock(name="test_action")],
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "test_package"
    assert result.action_packages[0].version == "1.0.0"
    assert result.action_packages[0].status == "online"
    assert len(result.action_packages[0].actions) == 1


async def test_agent_details_one_action_package_offline(mock_user, mock_storage):
    """Test getting agent details for an agent with one offline action package."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
    )
    agent = create_test_agent(action_packages=[action_package])

    with patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions",
        side_effect=Exception("Failed to get tool definitions"),
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "test_package"
    assert result.action_packages[0].version == "1.0.0"
    assert result.action_packages[0].status == "offline"
    assert len(result.action_packages[0].actions) == 0


async def test_agent_details_two_action_packages_both_online(mock_user, mock_storage):
    """Test getting agent details for an agent with two online action packages."""
    action_packages = [
        ActionPackage(
            name=f"test_package_{i}",
            organization="test_org",
            version="1.0.0",
            url="http://test.com",
            api_key=SecretString("test_key"),
        )
        for i in range(2)
    ]
    agent = create_test_agent(action_packages=action_packages)

    with patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions",
        return_value=[AsyncMock(name="test_action")],
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 2
    for i, package in enumerate(result.action_packages):
        assert package.name == f"test_package_{i}"
        assert package.version == "1.0.0"
        assert package.status == "online"
        assert len(package.actions) == 1


async def test_agent_details_two_action_packages_both_offline(mock_user, mock_storage):
    """Test getting agent details for an agent with two offline action packages."""
    action_packages = [
        ActionPackage(
            name=f"test_package_{i}",
            organization="test_org",
            version="1.0.0",
            url="http://test.com",
            api_key=SecretString("test_key"),
        )
        for i in range(2)
    ]
    agent = create_test_agent(action_packages=action_packages)

    with patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions",
        side_effect=Exception("Failed to get tool definitions"),
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 2
    for i, package in enumerate(result.action_packages):
        assert package.name == f"test_package_{i}"
        assert package.version == "1.0.0"
        assert package.status == "offline"
        assert len(package.actions) == 0


async def test_agent_details_two_action_packages_mixed_status(mock_user, mock_storage):
    """Test getting agent details for an agent with one online and one offline action package."""
    action_packages = [
        ActionPackage(
            name=f"test_package_{i}",
            organization="test_org",
            version="1.0.0",
            url="http://test.com",
            api_key=SecretString(f"test_key_{i}"),  # Different keys for each package
        )
        for i in range(2)
    ]
    agent = create_test_agent(action_packages=action_packages)

    async def mock_get_tool_defs(url, api_key, allowed_actions, additional_headers):
        # Only return success for the first package's key
        if url == "http://test.com" and api_key == "test_key_0":
            return [AsyncMock(name="test_action")]
        raise Exception("Failed to get tool definitions")

    with patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions",
        side_effect=mock_get_tool_defs,
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 2

    # First package should be online
    assert result.action_packages[0].name == "test_package_0"
    assert result.action_packages[0].version == "1.0.0"
    assert result.action_packages[0].status == "online"
    assert len(result.action_packages[0].actions) == 1

    # Second package should be offline
    assert result.action_packages[1].name == "test_package_1"
    assert result.action_packages[1].version == "1.0.0"
    assert result.action_packages[1].status == "offline"
    assert len(result.action_packages[1].actions) == 0


async def test_agent_details_with_allowed_actions(mock_user, mock_storage):
    """Test getting agent details for an agent with action packages that have allowed actions."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
        allowed_actions=["action1", "action2"],  # Only allow these actions
    )
    agent = create_test_agent(action_packages=[action_package])

    # Mock tool definitions to return only the allowed actions
    # (since get_spec_and_build_tool_definitions already handles the filtering)
    async def mock_get_tool_defs(url, api_key, allowed_actions, additional_headers):
        # Create mock tool definitions with name attributes
        tool_defs = []
        for name in ["action1", "action2"]:  # Only return the allowed actions
            mock = AsyncMock()
            mock.name = name
            tool_defs.append(mock)
        return tool_defs

    with patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions",
        side_effect=mock_get_tool_defs,
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "test_package"
    assert result.action_packages[0].version == "1.0.0"
    assert result.action_packages[0].status == "online"

    # Verify only allowed actions are included
    action_names = [action.name for action in result.action_packages[0].actions]
    assert len(action_names) == 2, "Should have both allowed actions"
    assert "action1" in action_names, "Should have action1"
    assert "action2" in action_names, "Should have action2"
