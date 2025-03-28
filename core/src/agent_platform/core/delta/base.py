from dataclasses import dataclass, field
from typing import Any, Literal

from agent_platform.core.utils import assert_literal_value_valid

DeltaOpType = Literal[
    # Standard JSON Patch operations
    "add",
    "remove",
    "replace",
    "move",
    "copy",
    "test",
    # Our custom operations
    "concat_string",
    "inc",
]


class _NoValue:
    """A sentinel value that cannot be serialized to JSON.
    Used to distinguish between None (a valid JSON value) and no value provided.
    """

    def __repr__(self) -> str:
        return "NO_VALUE"


NO_VALUE = _NoValue()


@dataclass
class GenericDelta:
    """Type representing a generic delta operation.

    Supports standard JSON Patch operations (RFC 6902):
    - `add`: Add a value at the target location
    - `remove`: Remove the value at the target location
    - `replace`: Replace the value at the target location
    - `move`: Move a value from one location to another
    - `copy`: Copy a value from one location to another
    - `test`: Test that a value at the target location equals the specified value

    And custom operations:
    - `concat_string`: Concatenate a string to the value at the path
    - `inc`: Increment the value at the path by the specified amount
    """

    op: DeltaOpType = field(metadata={"description": "The operation type to perform."})
    """The operation type to perform."""
    path: str = field(metadata={"description": "The JSON path to the target location."})
    """The JSON path to the target location."""
    value: Any | None = field(
        default=NO_VALUE,
        metadata={
            "description": "The value for the operation. Required for add, replace, "
            "test, concat_string, and inc operations. Can be None for these "
            "operations. Must be NO_VALUE for remove, move, and copy operations.",
        },
    )
    """The value for the operation. Required for some operations,
    must be NO_VALUE for others."""
    from_: str | None = field(
        default=None,
        metadata={
            "description": "Source path for move/copy operations.",
        },
    )
    """Source path for move/copy operations."""

    def __post_init__(self) -> None:
        from agent_platform.core.delta.utils import validate_delta_path

        assert_literal_value_valid(self, "op")

        # Validate value requirements based on operation type
        value_required_ops = {"add", "replace", "test", "concat_string", "inc"}
        value_forbidden_ops = {"remove", "move", "copy"}

        if self.op in value_required_ops and self.value is NO_VALUE:
            raise ValueError(f"Operation {self.op} requires a value (can be None)")
        if self.op in value_forbidden_ops and self.value is not NO_VALUE:
            raise ValueError(f"Operation {self.op} must have NO_VALUE value")

        # Validate from_ is present for move/copy operations
        if self.op in {"move", "copy"}:
            if not self.from_:
                raise ValueError(f"Operation {self.op} requires from_ parameter")
        elif self.from_ is not None:
            raise ValueError(f"Operation {self.op} must not have from_ parameter")

        validate_delta_path(None, self)

    def to_json_patch(self) -> dict[str, Any]:
        """Convert to a JSON Patch operation object."""
        patch = {"op": self.op, "path": self.path}

        # Add value for operations that need it
        if self.op in {"add", "replace", "test"}:
            patch["value"] = None if self.value is NO_VALUE else self.value

        # Add from for move/copy operations
        if self.op in {"move", "copy"}:
            patch["from"] = self.from_

        return patch

    def model_dump(self) -> dict[str, Any]:
        """Convert to a dictionary, including optional fields."""
        result = {
            "op": self.op,
            "path": self.path,
        }
        if self.value is not NO_VALUE:
            result["value"] = self.value
        if self.from_ is not None:
            result["from_"] = self.from_
        return result

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "GenericDelta":
        """Validate and convert a dictionary to a GenericDelta object."""
        return cls(**data)
