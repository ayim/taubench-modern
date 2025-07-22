"""Tests for the cancel_item endpoint with state machine integration."""

from http import HTTPStatus
from uuid import uuid4

import pytest

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.user import User
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemStatus,
)
from agent_platform.server.api.private_v2.work_items import cancel_item

from .mock_storage import MockStorage


class TestCancelItem:
    """Test cases for the cancel_item endpoint."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock authenticated user."""
        return User(user_id=str(uuid4()), sub="test-user")

    @pytest.fixture
    def mock_storage(self) -> MockStorage:
        """Create a mock storage dependency."""
        return MockStorage()

    @pytest.fixture
    def sample_work_item(self):
        """Create a sample work item."""
        return WorkItem(
            work_item_id=str(uuid4()),
            user_id=str(uuid4()),
            created_by=str(uuid4()),
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
        # Set up the work item with the desired status
        sample_work_item.status = status

        # Pre-populate the mock storage with the work item
        mock_storage.create_work_item(sample_work_item)

        result = await cancel_item(
            work_item_id=sample_work_item.work_item_id,
            user=mock_user,
            storage=mock_storage,
        )

        assert result == {"status": "ok"}

        # Verify the work item status was updated
        updated_item = await mock_storage.get_work_item(sample_work_item.work_item_id)
        assert updated_item.status == WorkItemStatus.CANCELLED

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
        # Set up the work item with the desired status
        sample_work_item.status = status

        # Pre-populate the mock storage with the work item
        mock_storage.create_work_item(sample_work_item)

        with pytest.raises(PlatformHTTPError) as exc_info:
            await cancel_item(
                work_item_id=sample_work_item.work_item_id,
                user=mock_user,
                storage=mock_storage,
            )

        assert exc_info.value.status_code == HTTPStatus.PRECONDITION_FAILED.value

        # Verify the work item status was NOT changed
        unchanged_item = await mock_storage.get_work_item(sample_work_item.work_item_id)
        assert unchanged_item.status == status

    async def test_cancel_nonexistent_work_item(self, mock_user, mock_storage):
        """Test that cancellation fails when work item doesn't exist."""
        work_item_id = str(uuid4())

        with pytest.raises(PlatformHTTPError) as exc_info:
            await cancel_item(
                work_item_id=work_item_id,
                user=mock_user,
                storage=mock_storage,
            )

        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND.value
        assert exc_info.value.detail == "A work item with the given ID was not found"
