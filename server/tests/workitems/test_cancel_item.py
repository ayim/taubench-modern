"""Tests for the cancel_item endpoint with state machine integration."""

from http import HTTPStatus
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.user import User
from agent_platform.core.work_items.work_item import WorkItem, WorkItemStatus
from agent_platform.server.api.private_v2.work_items import cancel_item


class TestCancelItem:
    """Test cases for the cancel_item endpoint."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock authenticated user."""
        return User(user_id=str(uuid4()), sub="test-user")

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage dependency."""
        return AsyncMock()

    @pytest.fixture
    def sample_work_item(self):
        """Create a sample work item."""
        return WorkItem(
            work_item_id=str(uuid4()),
            user_id=str(uuid4()),
            agent_id=str(uuid4()),
            status=WorkItemStatus.PENDING,
            messages=[],
            payload={},
        )

    @pytest.mark.parametrize(
        "status",
        [
            WorkItemStatus.PRECREATED,
            WorkItemStatus.PENDING,
            WorkItemStatus.EXECUTING,
        ],
    )
    async def test_cancel_success(self, status, mock_user, mock_storage, sample_work_item):
        """Test successful cancellation from allowed states."""
        sample_work_item.status = status
        mock_storage.get_work_item.return_value = sample_work_item
        mock_storage.update_work_item_status.return_value = None

        result = await cancel_item(
            work_item_id=sample_work_item.work_item_id,
            user=mock_user,
            storage=mock_storage,
        )

        assert result == {"status": "ok"}
        mock_storage.get_work_item.assert_called_once_with(sample_work_item.work_item_id)
        mock_storage.update_work_item_status.assert_called_once_with(
            mock_user.user_id,
            sample_work_item.work_item_id,
            WorkItemStatus.CANCELLED,
        )

    @pytest.mark.parametrize(
        "status",
        [
            WorkItemStatus.COMPLETED,
            WorkItemStatus.CANCELLED,
            WorkItemStatus.NEEDS_REVIEW,
            WorkItemStatus.ERROR,
        ],
    )
    async def test_cancel_fails(self, status, mock_user, mock_storage, sample_work_item):
        """Test that cancellation fails from disallowed states."""
        sample_work_item.status = status
        mock_storage.get_work_item.return_value = sample_work_item

        with pytest.raises(PlatformHTTPError) as exc_info:
            await cancel_item(
                work_item_id=sample_work_item.work_item_id,
                user=mock_user,
                storage=mock_storage,
            )

        assert exc_info.value.status_code == HTTPStatus.PRECONDITION_FAILED.value
        mock_storage.update_work_item_status.assert_not_called()

    async def test_cancel_nonexistent_work_item(self, mock_user, mock_storage):
        """Test that cancellation fails when work item doesn't exist."""
        mock_storage.get_work_item.return_value = None
        work_item_id = str(uuid4())

        with pytest.raises(PlatformHTTPError) as exc_info:
            await cancel_item(
                work_item_id=work_item_id,
                user=mock_user,
                storage=mock_storage,
            )

        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND.value
        assert exc_info.value.detail == "Work item not found"
        mock_storage.update_work_item_status.assert_not_called()
