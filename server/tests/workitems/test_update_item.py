from http import HTTPStatus
from uuid import uuid4

import pytest

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.user import User
from agent_platform.core.work_items.work_item import (
    MAX_WORK_ITEM_NAME_LENGTH,
    WorkItem,
    WorkItemStatus,
)
from agent_platform.server.work_items.rest import update_work_item

from .mock_storage import MockStorage


class TestUpdateItem:
    """Test cases for the update_work_item function."""

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
            work_item_name="Original Name",
        )

    async def test_update_success(self, mock_user, mock_storage, sample_work_item):
        """Test successful updating of a work item, including truncation of long names."""
        # Pre-populate the mock storage with the work item
        await mock_storage.create_work_item(sample_work_item)

        # Test normal update
        new_name = "Updated Work Item Name"
        result = await update_work_item(
            work_item_id=sample_work_item.work_item_id,
            work_item_name=new_name,
            user=mock_user,
            storage=mock_storage,
        )

        assert result.work_item_name == new_name

        # Verify the work item was updated in storage
        updated_item = await mock_storage.get_work_item(sample_work_item.work_item_id)
        assert updated_item.work_item_name == new_name

    async def test_name_update_truncation(self, mock_user, mock_storage, sample_work_item):
        """Test that long names are truncated to the maximum length."""
        # Pre-populate the mock storage with the work item
        await mock_storage.create_work_item(sample_work_item)
        long_name = "x" * (MAX_WORK_ITEM_NAME_LENGTH + 50)
        result = await update_work_item(
            work_item_id=sample_work_item.work_item_id,
            work_item_name=long_name,
            user=mock_user,
            storage=mock_storage,
        )
        assert result.work_item_name == WorkItem.normalize_work_item_name(long_name)
        assert result.work_item_name is not None
        assert len(result.work_item_name) <= MAX_WORK_ITEM_NAME_LENGTH

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "",
            "   ",
            "\n",
        ],
    )
    async def test_update_empty_name_fails(self, invalid_name, mock_user, mock_storage, sample_work_item):
        """Test that updating with empty/whitespace-only names fails."""
        # Pre-populate the mock storage with the work item
        await mock_storage.create_work_item(sample_work_item)

        with pytest.raises(PlatformHTTPError) as exc_info:
            await update_work_item(
                work_item_id=sample_work_item.work_item_id,
                work_item_name=invalid_name,
                user=mock_user,
                storage=mock_storage,
            )

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST.value
        assert "cannot be empty" in exc_info.value.detail.lower()

        # Verify the work item name was NOT changed
        unchanged_item = await mock_storage.get_work_item(sample_work_item.work_item_id)
        assert unchanged_item.work_item_name == "Original Name"
