"""
Tests for the work items status endpoint.

This module tests the /api/v2/work-items/status endpoint which reports
the status of all work item execution slots.
"""

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent_platform.core.work_items import WorkItem
from agent_platform.server.work_items.service import WorkItemsService
from agent_platform.server.work_items.slot_executor import SlotExecutor, SlotState
from sema4ai.common.null import NULL


@contextmanager
def mock_work_items_service(executor: Any):
    """
    Context manager to temporarily replace the WorkItemsService instance with a custom executor.

    Args:
        executor: The executor to use (SlotExecutor or BatchExecutor)

    Yields:
        None
    """
    original_instance = WorkItemsService._instance
    try:
        service = WorkItemsService.__new__(WorkItemsService)
        service._executor = executor
        service._transaction_logger = NULL
        WorkItemsService._instance = service
        yield
    finally:
        WorkItemsService._instance = original_instance


@pytest.mark.asyncio
async def test_report_work_item_status_reports_slots(client: TestClient):
    """Test reporting status when all slots are idle."""

    # Create a custom SlotExecutor with controlled state
    async def mock_execute(item: WorkItem) -> bool:
        """Mock executor that does nothing."""
        return True

    executor = SlotExecutor(mock_execute)

    # Set up 3 idle slots
    executor.slot_manager.slots = {
        0: SlotState(slot_id=0, status="idle", work_item_id=None),
        1: SlotState(slot_id=1, status="executing", work_item_id="12345"),
        2: SlotState(slot_id=2, status="idle", work_item_id=None),
    }

    with mock_work_items_service(executor):
        # Call the endpoint
        response = client.get("/api/v2/work-items/status")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] is not None
        assert len(data["status"]) == 3

        # Check each slot status
        for slot_status in data["status"]:
            assert slot_status["task_id"] in [0, 1, 2]
            if slot_status["task_id"] == 1:
                assert slot_status["status"] == "executing"
                assert slot_status["work_item_id"] == "12345"
            else:
                assert slot_status["status"] == "idle"
                assert slot_status["work_item_id"] is None


@pytest.mark.asyncio
async def test_report_work_item_status_with_batch_executor(client: TestClient):
    """Test reporting status when using BatchExecutor (should return null)."""
    from agent_platform.server.work_items.batch_executor import BatchExecutor

    # Create a custom BatchExecutor
    async def mock_execute(item: WorkItem) -> bool:
        """Mock executor that does nothing."""
        return True

    executor = BatchExecutor(mock_execute)

    with mock_work_items_service(executor):
        # Call the endpoint
        response = client.get("/api/v2/work-items/status")

        # Verify response - should be null when using BatchExecutor
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] is None
