from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from agent_server_types_v2.utils import assert_literal_value_valid


@dataclass(frozen=True)
class Run:
    """Represents a single invocation of an agent (a run) with its status and metadata."""

    run_id: str = field(metadata={"description": "The ID of the run"})
    """The ID of the run"""

    agent_id: str = field(metadata={"description": "The ID of the associated agent"})
    """The ID of the associated agent"""

    thread_id: str = field(metadata={"description": "The ID of the associated thread"})
    """The ID of the associated thread"""

    created_at: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "The timestamp when the run was created"},
    )
    """The timestamp when the run was created"""

    finished_at: datetime | None = field(
        default=None,
        metadata={"description": "The timestamp when the run was finished"},
    )
    """The timestamp when the run was finished"""

    status: Literal["created", "running", "completed", "failed", "cancelled"] = field(
        default="created",
        metadata={"description": "The run's status (e.g., 'created', 'running', 'completed', 'failed', 'cancelled')"},
    )
    """The run's status (e.g., 'created', 'running', 'completed', 'failed', 'cancelled')"""

    metadata: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Metadata associated with the run"},
    )
    """Metadata associated with the run"""

    run_type: Literal["sync", "async", "stream"] = field(
        default="stream",
        metadata={"description": "The type of run (e.g., 'sync', 'async', 'stream')"},
    )
    """The type of run (e.g., 'sync', 'async', 'stream')"""

    def __post_init__(self) -> None:
        assert_literal_value_valid(self, "status")
        assert_literal_value_valid(self, "run_type")

    def to_json_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "thread_id": self.thread_id,
            "created_at": self.created_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status,
            "metadata": self.metadata,
            "run_type": self.run_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Run":
        data = data.copy()
        for field_name in ["created_at", "finished_at"]:
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        if "run_id" in data and isinstance(data["run_id"], UUID):
            data["run_id"] = str(data["run_id"])
        if "agent_id" in data and isinstance(data["agent_id"], UUID):
            data["agent_id"] = str(data["agent_id"])
        if "thread_id" in data and isinstance(data["thread_id"], UUID):
            data["thread_id"] = str(data["thread_id"])
        return cls(**data)
