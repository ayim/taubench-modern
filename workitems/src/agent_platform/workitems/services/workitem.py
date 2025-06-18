from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from agent_platform.workitems.agents import AgentClient
from agent_platform.workitems.models import (
    CreateWorkItemPayload,
    WorkItem,
    WorkItemStatus,
)
from agent_platform.workitems.orm import WorkItemORM


class AgentValidationError(Exception):
    """Raised when agent validation fails."""

    pass


class WorkItemService:
    def __init__(self, session: Session, agent_client: AgentClient):
        self.session = session
        self.agent_client = agent_client

    async def create(
        self,
        payload: CreateWorkItemPayload,
    ) -> WorkItem:
        # Validate agent exists before creating work item
        agent_info = await self.agent_client.describe_agent(payload.agent_id)
        if agent_info is None:
            raise AgentValidationError(f"Agent with ID {payload.agent_id} not found")

        work_item = WorkItemORM(
            agent_id=payload.agent_id,
            thread_id=str(uuid4()),
            messages=[msg.model_dump() for msg in payload.messages],
            payload=payload.payload,
        )
        self.session.add(work_item)
        self.session.commit()
        self.session.refresh(work_item)

        return work_item.to_model()

    async def describe(self, work_item_id: str) -> WorkItem | None:
        result = self.session.execute(
            select(WorkItemORM).where(WorkItemORM.work_item_id == work_item_id)
        )
        orm_item = result.scalar_one_or_none()
        return orm_item.to_model() if orm_item else None

    async def list(self, limit: int = 100) -> list[WorkItem]:
        result = self.session.execute(select(WorkItemORM).limit(limit))
        return [item.to_model() for item in result.scalars().all()]

    async def update_status(
        self,
        work_item_id: str,
        status: WorkItemStatus,
        status_updated_by: str,
    ) -> WorkItem | None:
        self.session.execute(
            update(WorkItemORM)
            .where(WorkItemORM.work_item_id == work_item_id)
            .values(status=status, status_updated_by=status_updated_by)
        )
        self.session.commit()
        return await self.describe(work_item_id)
