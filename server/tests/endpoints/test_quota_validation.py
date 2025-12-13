"""Tests for agent quota validation functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.quotas import AgentQuotaExceededError
from agent_platform.server.api.dependencies import check_agent_quota


@pytest.fixture
def mock_storage():
    """Mock storage dependency for testing."""
    storage = AsyncMock()
    storage.count_agents = AsyncMock()
    return storage


@pytest.fixture
def mock_quotas_service():
    """Mock QuotasService for testing."""
    from unittest.mock import Mock

    quotas = Mock(spec=QuotasService)
    quotas.get_max_agents = Mock()
    return quotas


class TestAgentQuotaValidation:
    """Test class for agent quota validation."""

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_quota_check_allows_creation_when_under_limit(
        self, mock_get_quotas_instance, mock_storage, mock_quotas_service
    ):
        """Test that quota check allows agent creation when under limit."""
        # Setup: quota limit is 10, current count is 5
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_agents.return_value = 10
        mock_storage.count_agents.return_value = 5

        # Should not raise any exception
        result = await check_agent_quota(mock_storage)
        assert result is None

        # Verify method calls
        mock_storage.count_agents.assert_called_once()
        mock_quotas_service.get_max_agents.assert_called_once()

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_quota_check_blocks_creation_when_at_limit(
        self, mock_get_quotas_instance, mock_storage, mock_quotas_service
    ):
        """Test that quota check blocks agent creation when at limit."""
        # Setup: quota limit is 5, current count is 5 (at limit)
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_agents.return_value = 5
        mock_storage.count_agents.return_value = 5

        # Should raise AgentQuotaExceededError
        with pytest.raises(AgentQuotaExceededError) as exc_info:
            await check_agent_quota(mock_storage)

        exception = exc_info.value
        assert exception.response.status_code == 429

        # Verify the error data contains expected information
        data = exception.data
        assert isinstance(data, dict)
        assert data["current_count"] == 5
        assert data["quota_limit"] == 5
        assert data["error"] == "Agent quota exceeded"

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_quota_check_blocks_creation_when_over_limit(
        self, mock_get_quotas_instance, mock_storage, mock_quotas_service
    ):
        """Test that quota check blocks agent creation when over limit."""
        # Setup: quota limit is 3, current count is 5 (over limit)
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_agents.return_value = 3
        mock_storage.count_agents.return_value = 5

        # Should raise AgentQuotaExceededError
        with pytest.raises(AgentQuotaExceededError) as exc_info:
            await check_agent_quota(mock_storage)

        exception = exc_info.value
        assert exception.response.status_code == 429
        assert exception.data["current_count"] == 5
        assert exception.data["quota_limit"] == 3

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_quota_check_edge_case_one_below_limit(
        self, mock_get_quotas_instance, mock_storage, mock_quotas_service
    ):
        """Test quota check allows creation when one below limit."""
        # Setup: quota limit is 10, current count is 9
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_agents.return_value = 10
        mock_storage.count_agents.return_value = 9

        # Should allow creation
        result = await check_agent_quota(mock_storage)
        assert result is None

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_quota_check_with_zero_limit(self, mock_get_quotas_instance, mock_storage, mock_quotas_service):
        """Test quota check with zero limit (no agents allowed)."""
        # Setup: quota limit is 0, current count is 0
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_agents.return_value = 0
        mock_storage.count_agents.return_value = 0

        # Should still block creation due to zero limit
        with pytest.raises(AgentQuotaExceededError) as exc_info:
            await check_agent_quota(mock_storage)

        exception = exc_info.value
        assert exception.response.status_code == 429
        assert exception.data["current_count"] == 0
        assert exception.data["quota_limit"] == 0

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_quota_check_with_large_numbers(self, mock_get_quotas_instance, mock_storage, mock_quotas_service):
        """Test quota check works with large numbers."""
        # Setup: large quota limit
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_agents.return_value = 1000000
        mock_storage.count_agents.return_value = 999999

        # Should allow creation (one below limit)
        result = await check_agent_quota(mock_storage)
        assert result is None

        # Test at the limit
        mock_storage.count_agents.return_value = 1000000
        with pytest.raises(AgentQuotaExceededError):
            await check_agent_quota(mock_storage)

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_quota_error_message_format(self, mock_get_quotas_instance, mock_storage, mock_quotas_service):
        """Test that quota error contains proper message format."""
        # Setup
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_agents.return_value = 2
        mock_storage.count_agents.return_value = 2

        # Get the exception
        with pytest.raises(AgentQuotaExceededError) as exc_info:
            await check_agent_quota(mock_storage)

        exception = exc_info.value
        message_str = str(exception.response.message)
        data = exception.data

        # Verify error message contains key information
        assert "Maximum number of agents" in message_str
        assert "Current count" in message_str
        assert data["error"] == "Agent quota exceeded"
        assert data["current_count"] == 2
        assert data["quota_limit"] == 2


class TestQuotaServiceConfig:
    """Test quota service configuration validation."""

    def test_config_type_validation(self):
        """Test that config type validation works correctly."""
        from agent_platform.core.configurations.config_validation import validate_config_type

        # Valid config types should not raise
        validate_config_type("MAX_AGENTS")
        validate_config_type("MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB")

        # Invalid config type should raise ValueError
        with pytest.raises(ValueError, match="Invalid config_type"):
            validate_config_type("INVALID_CONFIG_TYPE")

    def test_all_config_types_present(self):
        """Test that all expected config types are defined."""
        from agent_platform.core.configurations.config_validation import ConfigType

        expected_types = {
            "MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB",
            "MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB",
            "MAX_AGENTS",
            "MAX_PARALLEL_WORK_ITEMS_IN_PROCESS",
            "MAX_MCP_SERVERS_IN_AGENT",
        }

        # All expected types should be present
        assert expected_types.issubset(ConfigType)

    def test_quota_constants_defined(self):
        """Test that quota constants are properly defined."""
        from agent_platform.core.configurations.config_validation import ConfigType
        from agent_platform.core.configurations.quotas import QuotasService

        # Test that storage constants are imported correctly
        assert ConfigType.MAX_AGENTS == "MAX_AGENTS"

        # Test that quota key constants exist
        assert hasattr(QuotasService, "MAX_AGENTS")
        assert QuotasService.MAX_AGENTS == "MAX_AGENTS"

        # Test that quota configs contains expected entries
        assert QuotasService.MAX_AGENTS in QuotasService.CONFIG_TYPES
        agent_config = QuotasService.CONFIG_TYPES[QuotasService.MAX_AGENTS]
        assert agent_config.storage_key == "MAX_AGENTS"
        assert agent_config.default_value == 100

    def test_config_value_validation(self):
        """Test config value validation - positive values pass, negative values raise error."""
        from agent_platform.core.configurations.config_validation import validate_config_value

        # Test positive values - should succeed
        assert validate_config_value("MAX_AGENTS", "100") == 100
        assert validate_config_value("MAX_AGENTS", "0") == 0
        assert validate_config_value("MAX_AGENTS", "1") == 1

        # Test negative values - should raise error
        with pytest.raises(PlatformHTTPError, match="must be >= 0 \\(non-negative\\)"):
            validate_config_value("MAX_AGENTS", "-1")

        with pytest.raises(PlatformHTTPError, match="must be >= 0 \\(non-negative\\)"):
            validate_config_value("MAX_AGENTS", "-100")
