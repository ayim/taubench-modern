"""Result types for agent package diff operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DiffChangeType = Literal["add", "update", "delete"]


@dataclass(frozen=True)
class DiffResult:
    """Represents a single difference between spec and deployed agent.

    Attributes:
        change: The type of change - 'add', 'update', or 'delete'.
        field_path: The field path that differs. For nested fields, use dot notation
                    (e.g., 'selected_tools.tools.0.name').
        deployed_value: The value in the deployed agent (None for 'add' changes).
        package_value: The value in the spec agent (None for 'delete' changes).
    """

    change: DiffChangeType
    field_path: str
    deployed_value: Any = None
    package_value: Any = None

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "change": self.change,
            "field_path": self.field_path,
            "deployed_value": self.deployed_value,
            "package_value": self.package_value,
        }


@dataclass(frozen=True)
class AgentDiffResult:
    """Result of comparing a SpecAgent with a deployed Agent.

    Attributes:
        changes: List of differences found between the spec and deployed agent.
    """

    is_synced: bool = field(
        default=False,
        metadata={"description": "True if there are no differences"},
    )
    changes: list[DiffResult] = field(
        default_factory=list,
        metadata={"description": "List of differences between spec and deployed agent"},
    )

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "is_synced": len(self.changes) == 0,
            "changes": [change.model_dump() for change in self.changes],
        }
