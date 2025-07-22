from datetime import UTC, datetime

from agent_platform.core.work_items import (
    WorkItem,
    WorkItemCompletedBy,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)
from agent_platform.server.storage.errors import WorkItemNotFoundError


class MockStorage:
    """Mock storage class for testing work items storage."""

    def __init__(self) -> None:
        self.work_items: dict[str, WorkItem] = {}

    async def get_work_item(self, work_item_id: str) -> WorkItem:
        item = self.work_items.get(work_item_id)
        if not item:
            raise WorkItemNotFoundError(work_item_id)
        return item

    async def update_work_item(self, work_item: WorkItem) -> None:
        if work_item.work_item_id not in self.work_items:
            raise WorkItemNotFoundError(work_item.work_item_id)
        self.work_items[work_item.work_item_id] = work_item

    def create_work_item(self, work_item: WorkItem) -> None:
        self.work_items[work_item.work_item_id] = work_item

    def delete_work_item(self, work_item_id: str) -> None:
        if work_item_id not in self.work_items:
            raise WorkItemNotFoundError(work_item_id)
        del self.work_items[work_item_id]

    async def get_work_items_by_ids(self, work_item_ids: list[str]) -> list[WorkItem]:
        return [await self.get_work_item(wid) for wid in work_item_ids]

    def list_work_items(self, user_id: str, agent_id: str | None = None) -> list[WorkItem]:
        candidates = list(self.work_items.values())
        if agent_id:
            candidates = [item for item in candidates if item.agent_id == agent_id]
        return candidates

    async def update_work_item_status(
        self,
        user_id: str,
        work_item_id: str,
        status: WorkItemStatus,
        status_updated_by: WorkItemStatusUpdatedBy = WorkItemStatusUpdatedBy.SYSTEM,
    ) -> None:
        if work_item_id not in self.work_items:
            raise WorkItemNotFoundError(work_item_id)
        self.work_items[work_item_id].status = status
        self.work_items[work_item_id].status_updated_by = status_updated_by
        self.work_items[work_item_id].status_updated_at = datetime.now(UTC)

    async def complete_work_item(
        self, user_id: str, work_item_id: str, completed_by: WorkItemCompletedBy
    ) -> None:
        """Complete a work item with the specified completed_by value."""
        if work_item_id not in self.work_items:
            raise WorkItemNotFoundError(work_item_id)
        self.work_items[work_item_id].status = WorkItemStatus.COMPLETED
        self.work_items[work_item_id].completed_by = completed_by
        self.work_items[work_item_id].status_updated_by = completed_by.as_status_updated_by()
        self.work_items[work_item_id].status_updated_at = datetime.now(UTC)
