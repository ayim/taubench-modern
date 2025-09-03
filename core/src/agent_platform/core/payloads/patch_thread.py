from dataclasses import dataclass, field

from agent_platform.core.thread import ThreadMessage


@dataclass
class PatchThreadPayload:
    """Payload for patching a thread."""

    name: str | None = field(
        default=None,
        metadata={"description": "The new name of the thread."},
    )
    """The new name of the thread."""

    agent_id: str | None = field(
        default=None,
        metadata={"description": "The new agent ID for this thread."},
    )
    """The new agent ID for this thread."""

    messages: list[ThreadMessage] | None = field(
        default=None,
        metadata={"description": "The new messages for this thread."},
    )
    """The new messages for this thread."""

    metadata: dict | None = field(
        default=None,
        metadata={"description": "The new metadata for this thread."},
    )
    """The new metadata for this thread."""

    work_item_id: str | None = field(
        default=None,
        metadata={"description": "The work item ID associated with this thread."},
    )
    """The work item ID associated with this thread."""
