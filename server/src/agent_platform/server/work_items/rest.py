from dataclasses import dataclass
from typing import Any

from agent_platform.core.utils.dataclass_meta import TolerantDataclass
from agent_platform.core.work_items.work_item import WorkItem, WorkItemStatus


@dataclass
class WorkItemsListResponse:
    records: list[WorkItem]
    next_offset: int | None = None

    def model_dump(self) -> dict:
        return {
            "records": [work_item.model_dump() for work_item in self.records],
            "next_offset": self.next_offset,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "WorkItemsListResponse":
        return cls(
            records=[WorkItem.model_validate(work_item) for work_item in data["records"]],
            next_offset=data.get("next_offset"),
        )


@dataclass
class AgentWorkItemsSummaryResponse(TolerantDataclass):
    """Response model for work items summary grouped by agent and status."""

    agent_id: str
    agent_name: str
    work_items_status_counts: dict[WorkItemStatus, int]

    def model_dump(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "work_items_status_counts": {
                status.value: count for status, count in self.work_items_status_counts.items()
            },
        }

    @classmethod
    def model_validate(cls, data: dict) -> "AgentWorkItemsSummaryResponse":
        return cls(
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
            work_items_status_counts={
                WorkItemStatus(status): count
                for status, count in data["work_items_status_counts"].items()
            },
        )
