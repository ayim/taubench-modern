from unittest.mock import AsyncMock, patch

import pytest

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.utils import SecretString


class TestActionPackage:
    def test_initialization_basic(self):
        """Test basic initialization of ActionPackage."""
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
        )

        assert package.name == "test-package"
        assert package.organization == "test-org"
        assert package.version == "1.0.0"
        assert package.url is None
        assert package.api_key is None
        assert package.allowed_actions == []
        assert package.whitelist == ""

    def test_api_key_string_conversion(self):
        """Test that string api_key is converted to SecretString."""
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            api_key=SecretString("test-api-key"),
        )

        assert isinstance(package.api_key, SecretString)
        assert package.api_key.get_secret_value() == "test-api-key"

    def test_legacy_whitelist_upgrade(self):
        """Test that whitelist is correctly upgraded to allowed_actions."""
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            whitelist="action1,action2,action3",
        )

        assert package.allowed_actions == ["action1", "action2", "action3"]
        assert package.whitelist == ""  # Should be cleared after upgrade

    def test_whitelist_empty(self):
        """Test that empty whitelist doesn't affect allowed_actions."""
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            whitelist="",
            allowed_actions=["action1"],
        )

        assert package.allowed_actions == ["action1"]
        assert package.whitelist == ""

    def test_whitelist_no_commas(self):
        """Test that whitelist without commas doesn't get split."""
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            whitelist="action1",
        )

        assert package.allowed_actions == ["action1"]
        assert package.whitelist == ""

    def test_whitelist_with_spaces(self):
        """Test that whitelist with spaces gets stripped."""
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            whitelist="action1, action2, action3",
        )

        assert package.allowed_actions == ["action1", "action2", "action3"]
        assert package.whitelist == ""

    def test_whitelist_with_trailing_spaces(self):
        """Test that whitelist with trailing spaces gets stripped."""
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            whitelist="action1, action2, action3, ",
        )

        assert package.allowed_actions == ["action1", "action2", "action3"]
        assert package.whitelist == ""

    def test_copy(self):
        """Test deep copy functionality."""
        original = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            url="http://example.com",
            api_key=SecretString("test-api-key"),
            allowed_actions=["action1", "action2"],
        )

        copied = original.copy()

        assert copied.name == original.name
        assert copied.organization == original.organization
        assert copied.version == original.version
        assert copied.url == original.url
        assert copied.api_key is not None
        assert original.api_key is not None
        assert copied.api_key.get_secret_value() == original.api_key.get_secret_value()
        assert copied.allowed_actions == original.allowed_actions
        assert copied.whitelist == original.whitelist

        # Ensure it's actually a copy
        assert id(copied) != id(original)

    def test_model_dump(self):
        """Test serialization to dictionary."""
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            url="http://example.com",
            api_key=SecretString("test-api-key"),
            allowed_actions=["action1", "action2"],
        )

        dumped = package.model_dump()

        assert dumped == {
            "name": "test-package",
            "organization": "test-org",
            "version": "1.0.0",
            "url": "http://example.com",
            "api_key": "test-api-key",
            "allowed_actions": ["action1", "action2"],
        }

    def test_model_validate(self):
        """Test deserialization from dictionary."""
        data = {
            "name": "test-package",
            "organization": "test-org",
            "version": "1.0.0",
            "url": "http://example.com",
            "api_key": "test-api-key",
            "allowed_actions": ["action1", "action2"],
        }

        package = ActionPackage.model_validate(data)

        assert package.name == "test-package"
        assert package.organization == "test-org"
        assert package.version == "1.0.0"
        assert package.url == "http://example.com"
        assert isinstance(package.api_key, SecretString)
        assert package.api_key.get_secret_value() == "test-api-key"
        assert package.allowed_actions == ["action1", "action2"]

    @pytest.mark.asyncio
    @patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions"
    )
    async def test_to_tool_definitions(self, mock_get_spec):
        """Test conversion to tool definitions with mocked API response."""
        # Setup mock return value
        tool_def = ToolDefinition(
            name="test-action",
            description="Test action description",
            input_schema={"type": "object", "properties": {}},
            function=AsyncMock(),
        )
        mock_get_spec.return_value = [tool_def]

        # Create package
        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            url="http://example.com",
            api_key=SecretString("test-api-key"),
            allowed_actions=["action1"],
        )

        # Call the method
        tool_definitions = await package.to_tool_definitions()

        # Verify results
        assert len(tool_definitions) == 1
        assert tool_definitions[0] == tool_def

        # Verify the mock was called with correct arguments
        mock_get_spec.assert_called_once_with(
            "http://example.com", "test-api-key", ["action1"]
        )

    @pytest.mark.asyncio
    @patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions"
    )
    async def test_to_tool_definitions_missing_url(self, mock_get_spec):
        """Test conversion with missing URL."""
        mock_get_spec.return_value = []

        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            api_key=SecretString("test-api-key"),
        )

        tool_definitions = await package.to_tool_definitions()

        assert tool_definitions == []
        mock_get_spec.assert_called_once_with("", "test-api-key", [])

    @pytest.mark.asyncio
    @patch(
        "agent_platform.core.actions.action_package.get_spec_and_build_tool_definitions"
    )
    async def test_to_tool_definitions_missing_api_key(self, mock_get_spec):
        """Test conversion with missing API key."""
        mock_get_spec.return_value = []

        package = ActionPackage(
            name="test-package",
            organization="test-org",
            version="1.0.0",
            url="http://example.com",
        )

        tool_definitions = await package.to_tool_definitions()

        assert tool_definitions == []
        mock_get_spec.assert_called_once_with("http://example.com", "", [])
