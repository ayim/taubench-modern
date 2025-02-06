from dataclasses import dataclass, field
from typing import Any, Literal

DeltaOpType = Literal["replace", "remove", "concat_string", "inc", "append_array", "merge"]


@dataclass
class GenericDelta:
    """Type representing a generic delta operation."""
    op: DeltaOpType = field(metadata={"description": "The operation type to perform."})
    """The operation type to perform."""
    path: str = field(metadata={"description": "The JSON path to the target location."})
    """The JSON path to the target location."""
    value: Any | None = field(metadata={"description": "The value for the operation (optional for remove operations)."})
    """The value for the operation (optional for remove operations)."""

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "path": self.path,
            "value": self.value,
        }
