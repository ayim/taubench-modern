from dataclasses import dataclass, field


@dataclass
class UpdateWorkItemPayload:
    """Payload for updating a work item."""

    work_item_name: str | None = field(
        default=None,
        metadata={"description": "The new name for the work item."},
    )
    """The new name for the work item."""
