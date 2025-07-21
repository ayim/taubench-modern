from dataclasses import dataclass

from agent_platform.core.work_items.work_item import WorkItem


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
