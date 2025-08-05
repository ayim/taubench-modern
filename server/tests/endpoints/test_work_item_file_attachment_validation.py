"""Tests for work item file attachment size validation."""

from unittest.mock import Mock, patch

import pytest
from fastapi import UploadFile

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.errors.work_items import WorkItemFileAttachmentTooLargeError
from agent_platform.server.api.dependencies import check_work_item_file_attachment_size


@pytest.fixture
def mock_quotas_service():
    """Mock QuotasService for testing."""
    quotas = Mock(spec=QuotasService)
    quotas.get_max_work_item_file_attachment_size = Mock()
    return quotas


@pytest.fixture
def mock_upload_file():
    """Mock UploadFile for testing."""
    file = Mock(spec=UploadFile)
    file.size = None  # Default to None, will be overridden in tests
    return file


class TestWorkItemFileAttachmentValidation:
    """Test class for work item file attachment size validation."""

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_file_check_allows_small_file(
        self, mock_get_quotas_instance, mock_upload_file, mock_quotas_service
    ):
        """Test that small files are allowed."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_file_attachment_size.return_value = 10  # 10 MB limit
        mock_upload_file.size = 1024 * 1024  # 1 MB file

        # Should not raise any exception
        result = await check_work_item_file_attachment_size(mock_upload_file)
        assert result is None

        # Verify method calls
        mock_quotas_service.get_max_work_item_file_attachment_size.assert_called_once()

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_file_check_blocks_large_file(
        self, mock_get_quotas_instance, mock_upload_file, mock_quotas_service
    ):
        """Test that large files are blocked."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_file_attachment_size.return_value = 5  # 5 MB limit
        mock_upload_file.size = 10 * 1024 * 1024  # 10 MB file

        # Should raise WorkItemFileAttachmentTooLargeError
        with pytest.raises(WorkItemFileAttachmentTooLargeError) as exc_info:
            await check_work_item_file_attachment_size(mock_upload_file)

        # Verify exception details
        error = exc_info.value
        assert "Work item file attachment size (10.0 MB) exceeds the allowed limit (5.0 MB)" in str(
            error
        )

        # Verify method calls
        mock_quotas_service.get_max_work_item_file_attachment_size.assert_called_once()

    async def test_file_check_skips_string_input(self):
        """Test that string inputs are skipped (no validation)."""
        # String input should be skipped entirely
        result = await check_work_item_file_attachment_size("some_file_path")
        assert result is None

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_file_check_handles_none_size(
        self, mock_get_quotas_instance, mock_upload_file, mock_quotas_service
    ):
        """Test that files with None size are skipped."""
        # Setup mocks - QuotasService should not be called if file.size is None
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_upload_file.size = None

        # Should return early without calling quotas service
        result = await check_work_item_file_attachment_size(mock_upload_file)
        assert result is None

        # Verify QuotasService was not called since we returned early
        mock_quotas_service.get_max_work_item_file_attachment_size.assert_not_called()

    @patch("agent_platform.core.configurations.quotas.QuotasService.get_instance")
    async def test_file_check_edge_case_exactly_at_limit(
        self, mock_get_quotas_instance, mock_upload_file, mock_quotas_service
    ):
        """Test file exactly at the size limit."""
        # Setup mocks
        mock_get_quotas_instance.return_value = mock_quotas_service
        mock_quotas_service.get_max_work_item_file_attachment_size.return_value = 5  # 5 MB limit
        mock_upload_file.size = 5 * 1024 * 1024  # Exactly 5 MB

        # Should allow (not raise exception) since it's exactly at limit
        result = await check_work_item_file_attachment_size(mock_upload_file)
        assert result is None
