from datetime import UTC, datetime

from agent_platform.core.agent.agent import Agent
from agent_platform.core.user import User
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
        self.users: dict[str, User] = {}
        self.agents: dict[str, Agent] = {}

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Get an existing user or create a new one."""
        if sub in self.users:
            return self.users[sub], False

        user = User(
            user_id=f"user_{len(self.users)}",
            sub=sub,
            created_at=datetime.now(UTC),
        )
        self.users[sub] = user
        return user, True

    async def get_work_item(self, work_item_id: str) -> WorkItem:
        item = self.work_items.get(work_item_id)
        if not item:
            raise WorkItemNotFoundError(work_item_id)
        return item

    async def update_work_item(self, work_item: WorkItem) -> None:
        if work_item.work_item_id not in self.work_items:
            raise WorkItemNotFoundError(work_item.work_item_id)
        self.work_items[work_item.work_item_id] = work_item

    async def create_work_item(self, work_item: WorkItem) -> None:
        # TODO add mock enforcements, e.g. agent exists
        self.work_items[work_item.work_item_id] = work_item

    def delete_work_item(self, work_item_id: str) -> None:
        if work_item_id not in self.work_items:
            raise WorkItemNotFoundError(work_item_id)
        del self.work_items[work_item_id]

    async def get_work_items_by_ids(self, work_item_ids: list[str]) -> list[WorkItem]:
        return [await self.get_work_item(wid) for wid in work_item_ids]

    async def list_work_items(
        self,
        agent_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        created_by: str | None = None,
    ) -> list[WorkItem]:
        candidates = list(self.work_items.values())
        if agent_id:
            candidates = [item for item in candidates if item.agent_id == agent_id]
        if created_by:
            candidates = [item for item in candidates if item.created_by == created_by]

        # Apply pagination
        return candidates[offset : offset + limit]

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

    async def get_agent(self, user_id: str, agent_id: str) -> Agent | None:
        """Get an agent by user_id and agent_id."""
        return self.agents.get(agent_id)
