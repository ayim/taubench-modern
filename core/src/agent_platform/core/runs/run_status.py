from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class RunStatus:
    run_id: str = field(metadata={"description": "The ID of the run"})
    """The ID of the run"""

    thread_id: str = field(
        metadata={"description": "The ID of the thread associated with the run"},
    )
    """The ID of the thread associated with the run."""

    status: Literal["created", "running", "completed", "failed", "cancelled"] = field(
        default="created",
        metadata={
            "description": "The run's status (e.g., 'created', 'running',"
            "'completed', 'failed', 'cancelled')",
        },
    )
    """The run's status (e.g., 'created', 'running',
    'completed', 'failed', 'cancelled')"""

    @property
    def is_success(self) -> bool:
        return self.status in ["completed", "cancelled"]

    @property
    def is_failure(self) -> bool:
        return self.status in ["failed", "cancelled"]
