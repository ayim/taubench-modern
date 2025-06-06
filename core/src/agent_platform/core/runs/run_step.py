from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from agent_platform.core.utils import assert_literal_value_valid


@dataclass(frozen=True)
class RunStep:
    """Represents an individual step in a run, including state
    changes and associated metadata."""

    run_id: str = field(
        metadata={"description": "The ID of the run this step belongs to"},
    )
    """The ID of the run this step belongs to"""

    step_id: str = field(metadata={"description": "The unique ID of the run step"})
    """The unique ID of the run step"""

    sequence_number: int = field(
        metadata={
            "description": "The sequence number of the step within the run",
        },
    )
    """The sequence number of the step within the run"""

    step_status: Literal[
        "created",
        "running",
        "completed",
        "failed",
        "cancelled",
    ] = field(
        default="created",
        metadata={
            "description": "The step's status (e.g., 'created', 'running', "
            "'completed', 'failed', 'cancelled')",
        },
    )
    """The step's status (e.g., 'created', 'running',
    'completed', 'failed', 'cancelled')"""

    input_state: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "The input state for the run step"},
    )
    """The input state for the run step"""

    input_state_hash: str | None = field(
        default=None,
        metadata={"description": "Hash of the input state"},
    )
    """Hash of the input state"""

    output_state: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "The output state for the run step"},
    )
    """The output state for the run step"""

    output_state_hash: str | None = field(
        default=None,
        metadata={"description": "Hash of the output state"},
    )
    """Hash of the output state"""

    metadata: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Metadata associated with the run step"},
    )
    """Metadata associated with the run step"""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The timestamp when the run step was created"},
    )
    """The timestamp when the run step was created"""

    finished_at: datetime | None = field(
        default=None,
        metadata={"description": "The timestamp when the run step was finished"},
    )
    """The timestamp when the run step was finished"""

    def __post_init__(self) -> None:
        assert_literal_value_valid(self, "step_status")

    def model_dump(self) -> dict:
        return {
            "run_id": self.run_id,
            "step_id": self.step_id,
            "step_status": self.step_status,
            "sequence_number": self.sequence_number,
            "input_state_hash": self.input_state_hash,
            "input_state": self.input_state,
            "output_state_hash": self.output_state_hash,
            "output_state": self.output_state,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "RunStep":
        data = data.copy()
        for field_name in ["created_at", "finished_at"]:
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        if "run_id" in data and isinstance(data["run_id"], UUID):
            data["run_id"] = str(data["run_id"])
        if "step_id" in data and isinstance(data["step_id"], UUID):
            data["step_id"] = str(data["step_id"])
        return cls(**data)
