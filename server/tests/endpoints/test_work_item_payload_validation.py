"""Tests for work item payload size validation."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import Request

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.errors.work_items import WorkItemPayloadTooLargeError
from agent_platform.server.api.dependencies import check_work_item_payload_size


@pytest.fixture
def mock_quotas_service():
    """Mock QuotasService for testing."""
    quotas = Mock(spec=QuotasService)
    quotas.get_max_work_item_payload_size = Mock()
    return quotas


@pytest.fixture
def mock_request():
    """Mock FastAPI Request for testing."""
    request = Mock(spec=Request)
    request.body = AsyncMock()
    return request


class TestWorkItemPayloadValidation:
    """Test class for work item payload size validation."""

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_payload_check_allows_small_payload(
        self, mock_get_quotas_instance, mock_request, mock_quotas_service
    ):
        """Test that small payloads are allowed."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_payload_size.return_value = 100  # 100 KB limit
        mock_request.body.return_value = b"small payload"  # ~13 bytes = 0.013 KB

        # Should not raise any exception
        result = await check_work_item_payload_size(mock_request)
        assert result is None

        # Verify method calls
        mock_request.body.assert_called_once()
        mock_quotas_service.get_max_work_item_payload_size.assert_called_once()

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_payload_check_blocks_large_payload(
        self, mock_get_quotas_instance, mock_request, mock_quotas_service
    ):
        """Test that large payloads are blocked."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_payload_size.return_value = 1  # 1 KB limit
        # Create a payload larger than 1 KB (1024 bytes)
        large_payload = b"x" * 2048  # 2048 bytes = 2 KB
        mock_request.body.return_value = large_payload

        # Should raise WorkItemPayloadTooLargeError
        with pytest.raises(WorkItemPayloadTooLargeError) as exc_info:
            await check_work_item_payload_size(mock_request)

        # Verify exception details
        error = exc_info.value
        assert "Work item payload size (2 KB) exceeds the allowed limit (1 KB)" in str(error)

        # Verify method calls
        mock_request.body.assert_called_once()
        mock_quotas_service.get_max_work_item_payload_size.assert_called_once()

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_payload_check_edge_case_exactly_at_limit(
        self, mock_get_quotas_instance, mock_request, mock_quotas_service
    ):
        """Test payload exactly at the limit."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_payload_size.return_value = 1  # 1 KB limit
        # Create a payload exactly 1 KB (1024 bytes)
        exact_payload = b"x" * 1024  # 1024 bytes = 1 KB
        mock_request.body.return_value = exact_payload

        # Should allow (not raise exception) since it's exactly at limit
        result = await check_work_item_payload_size(mock_request)
        assert result is None

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_payload_check_edge_case_just_over_limit(
        self, mock_get_quotas_instance, mock_request, mock_quotas_service
    ):
        """Test payload just over the limit."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_payload_size.return_value = 1  # 1 KB limit
        # Create a payload just over 1 KB
        over_payload = b"x" * 1025  # 1025 bytes = ~1.001 KB
        mock_request.body.return_value = over_payload

        # Should raise WorkItemPayloadTooLargeError
        with pytest.raises(WorkItemPayloadTooLargeError):
            await check_work_item_payload_size(mock_request)

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_payload_check_empty_payload(
        self, mock_get_quotas_instance, mock_request, mock_quotas_service
    ):
        """Test empty payload."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_payload_size.return_value = 100  # 100 KB limit
        mock_request.body.return_value = b""  # Empty payload

        # Should allow empty payloads
        result = await check_work_item_payload_size(mock_request)
        assert result is None

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_payload_check_large_quota_limit(
        self, mock_get_quotas_instance, mock_request, mock_quotas_service
    ):
        """Test with large quota limits."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_payload_size.return_value = 10000  # 10 MB limit
        # Create a moderately large payload
        large_payload = b"x" * (500 * 1024)  # 500 KB
        mock_request.body.return_value = large_payload

        # Should allow since it's under the large limit
        result = await check_work_item_payload_size(mock_request)
        assert result is None

    def test_error_response_format(self):
        """Test the WorkItemPayloadTooLargeError response format."""
        error = WorkItemPayloadTooLargeError(payload_size=150, allowed_payload_size=100)

        # Check error message
        expected_message = "Work item payload size (150 KB) exceeds the allowed limit (100 KB)"
        assert expected_message in str(error)

        # Check error data
        assert hasattr(error, "data")
        assert error.data["payload_size_kb"] == 150
        assert error.data["allowed_payload_size_kb"] == 100
