"""Tests for the AgentServerWorkItemInterface and WorkItemTools classes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_platform.core.kernel_interfaces.work_item import WorkItemArchState
from agent_platform.core.work_items.work_item import WorkItem, WorkItemStatus
from agent_platform.server.kernel.work_item import AgentServerWorkItemInterface, WorkItemTools


@pytest.fixture
def mock_kernel():
    """Create a mock kernel for testing."""
    kernel = MagicMock()
    kernel.thread.thread_id = "test-thread-id"
    kernel.thread.work_item_id = "test-work-item-id"
    kernel.user = MagicMock()
    return kernel


@pytest.fixture
def mock_storage():
    """Create a mock storage service."""
    storage = MagicMock()
    storage.get_work_item = AsyncMock()
    storage.update_work_item = AsyncMock()
    return storage


@pytest.fixture
def mock_work_item():
    """Create a mock work item."""
    return WorkItem(
        work_item_id="test-work-item-id",
        user_id="test-user-id",
        created_by="test-user-id",
        work_item_name="Test Work Item",
        status=WorkItemStatus.PENDING,
    )


@pytest.fixture
def work_item_interface(mock_kernel):
    """Create a work item interface for testing."""
    interface = AgentServerWorkItemInterface()
    interface.attach_kernel(mock_kernel)
    return interface


class TestAgentServerWorkItemInterface:
    """Test cases for AgentServerWorkItemInterface."""

    def test_is_enabled(self, work_item_interface):
        """Test that work items are always enabled."""
        assert work_item_interface.is_enabled() is True

    @pytest.mark.asyncio
    async def test_step_initialize_with_work_item(
        self, work_item_interface, mock_work_item, mock_storage
    ):
        """Test step_initialize when a work item exists."""
        work_item_interface.kernel.thread.work_item_id = "test-work-item-id"
        mock_storage.get_work_item.return_value = mock_work_item
        state = MagicMock(spec=WorkItemArchState)

        with patch(
            "agent_platform.server.kernel.work_item.StorageService.get_instance",
            return_value=mock_storage,
        ):
            await work_item_interface.step_initialize(state)

        assert work_item_interface._work_item == mock_work_item
        assert len(work_item_interface._work_item_tools) == 1
        assert work_item_interface._work_item_tools[0].name == "work_item_rename"
        assert state.work_item_tools_state == "enabled"

    @pytest.mark.asyncio
    async def test_step_initialize_without_work_item(self, work_item_interface, mock_storage):
        """Test step_initialize when no work item exists."""
        work_item_interface.kernel.thread.work_item_id = None
        state = MagicMock(spec=WorkItemArchState)

        with patch(
            "agent_platform.server.kernel.work_item.StorageService.get_instance",
            return_value=mock_storage,
        ):
            await work_item_interface.step_initialize(state)

        assert work_item_interface._work_item is None
        assert len(work_item_interface._work_item_tools) == 0
        assert state.work_item_tools_state == ""

    @pytest.mark.asyncio
    async def test_work_item_summaries(self, work_item_interface, mock_work_item, mock_storage):
        """Test work item summary methods."""
        # Setup work item and tools
        work_item_interface._work_item = mock_work_item
        work_item_interface.kernel.thread.work_item_id = "test-work-item-id"
        mock_storage.get_work_item.return_value = mock_work_item
        state = MagicMock(spec=WorkItemArchState)

        with patch(
            "agent_platform.server.kernel.work_item.StorageService.get_instance",
            return_value=mock_storage,
        ):
            await work_item_interface.step_initialize(state)

        # Get the actual tools that were created
        tools = work_item_interface.get_work_item_tools()

        with_tools = work_item_interface.work_item_summary_with_tools
        # Check that each tool name appears in the with_tools summary
        for tool in tools:
            assert tool.name in with_tools

        no_tools = work_item_interface.work_item_summary_no_tools
        # Check that no tool names appear in the no_tools summary
        for tool in tools:
            assert tool.name not in no_tools

        # Test without work item
        work_item_interface._work_item = None
        assert work_item_interface.work_item_summary_with_tools == ""
        assert work_item_interface.work_item_summary_no_tools == ""

    def test_get_work_item_tools(self, work_item_interface):
        """Test get_work_item_tools returns the correct tools."""
        mock_tools = (MagicMock(), MagicMock())
        work_item_interface._work_item_tools = mock_tools
        assert work_item_interface.get_work_item_tools() == mock_tools


class TestWorkItemTools:
    """Test cases for WorkItemTools."""

    @pytest.fixture
    def work_item_tools(self, mock_work_item, mock_storage):
        """Create WorkItemTools instance for testing."""
        return WorkItemTools(
            user=MagicMock(),
            tid="test-thread-id",
            work_item=mock_work_item,
            storage=mock_storage,
        )

    @pytest.mark.asyncio
    async def test_work_item_rename_success(self, work_item_tools, mock_work_item, mock_storage):
        """Test successful work item rename."""
        result = await work_item_tools.work_item_rename("New Name")

        assert result == {"result": "Work item renamed to 'New Name'"}
        assert mock_work_item.work_item_name == "New Name"
        mock_storage.update_work_item.assert_called_once_with(mock_work_item)

    @pytest.mark.asyncio
    async def test_work_item_rename_errors(self, mock_storage):
        """Test rename error cases."""
        # No work item
        tools_no_item = WorkItemTools(
            user=MagicMock(),
            tid="test-thread-id",
            work_item=None,
            storage=mock_storage,
        )
        result = await tools_no_item.work_item_rename("New Name")
        assert result == {
            "error_code": "no_work_item",
            "error": "No work item associated with this thread",
        }

        # Empty name
        mock_work_item = WorkItem(
            work_item_id="test-id",
            user_id="test-user",
            created_by="test-user",
            work_item_name="Test",
        )
        tools = WorkItemTools(
            user=MagicMock(),
            tid="test-thread-id",
            work_item=mock_work_item,
            storage=mock_storage,
        )
        result = await tools.work_item_rename("   ")
        assert result == {
            "error_code": "empty_work_item_name",
            "error": "Work item name cannot be empty",
        }
