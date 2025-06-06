"""
This module contains the logic for combining a list of GenericDelta
objects back into a single object.
"""

from copy import deepcopy
from typing import Any, TypeVar, cast

from jsonpatch import JsonPatch, JsonPatchException, JsonPointerException

from agent_platform.core.delta.base import GenericDelta
from agent_platform.core.delta.errors import InvalidOperationError, InvalidPathError
from agent_platform.core.delta.utils import (
    get_value_at_path,
    validate_delta_path,
)

T = TypeVar("T")


def _apply_patch_safely(
    patch: JsonPatch,
    result: Any,
    delta: GenericDelta,
) -> Any:
    """Apply a JSON Patch safely with proper error handling.

    Args:
        patch: The JsonPatch to apply.
        result: The current document state.
        delta: The delta operation being applied (for error context).

    Returns:
        The result after applying the patch.

    Raises:
        InvalidPathError: If the path cannot be resolved.
        InvalidOperationError: If the operation is invalid.
    """
    try:
        return patch.apply(result)
    except (JsonPatchException, JsonPointerException) as e:
        if isinstance(e, JsonPointerException) or "no such path" in str(e):
            raise InvalidPathError(
                path=delta.path,
                path_attr="path",
                message=str(e),
                delta_object=delta,
            ) from e
        raise InvalidOperationError(str(e)) from e


def _handle_concat_string(
    current_value: str | None,
    result: Any,
    delta: GenericDelta,
) -> str:
    """Handle the concat_string operation."""
    if not isinstance(current_value, str | type(None)):
        raise InvalidOperationError(
            f"Cannot concat_string on non-string value: {current_value}",
            delta_object=delta,
        )
    if current_value is None:
        current_value = ""
    # Use standard JSON Patch replace operation
    patch = JsonPatch(
        [
            {
                "op": "replace",
                "path": delta.path,
                "value": current_value + cast(str, delta.value),
            },
        ],
    )
    return _apply_patch_safely(patch, result, delta)


def _handle_inc(
    current_value: int | float | None,
    result: Any,
    delta: GenericDelta,
) -> int | float:
    """Handle the inc operation."""
    if not isinstance(current_value, int | float | type(None)):
        raise InvalidOperationError(
            f"Cannot increment non-numeric value: {current_value}",
            delta_object=delta,
        )
    if current_value is None:
        current_value = 0
    # Use standard JSON Patch replace operation
    patch = JsonPatch(
        [
            {
                "op": "replace",
                "path": delta.path,
                "value": current_value + cast(int | float, delta.value),
            },
        ],
    )
    return _apply_patch_safely(patch, result, delta)


def combine_generic_deltas(
    deltas: list[GenericDelta],
    initial_value: T | None = None,
) -> T:
    """Combines a list of GenericDelta objects back into a single object.

    Uses jsonpatch for standard operations (add, remove, replace, move, copy, test)
    and custom handlers for our extended operations (concat_string, inc).

    Args:
        deltas: List of GenericDelta objects to combine.
        initial_value: Optional initial value to start with.

    Returns:
        The combined object after applying all deltas.

    Raises:
        InvalidPathError: If a delta path cannot be resolved in the target object.
        InvalidOperationError: If a delta operation is not supported.
    """
    if not deltas:
        assert initial_value is not None, "initial_value must be provided if deltas is empty"
        return initial_value

    # Make a copy of the initial value to avoid modifying it
    result = deepcopy(initial_value) if initial_value is not None else {}

    # Process each delta in order
    for delta in deltas:
        # Validate the path using our custom validator
        validate_delta_path(result, delta)

        # Special handling for empty path operations
        if not delta.path and delta.op in {"add", "replace"}:
            # Empty path means replace entire document
            result = delta.value if delta.value is not None else {}
            continue

        # Handle standard JSON Patch operations
        if delta.op in {"add", "remove", "replace", "move", "copy", "test"}:
            patch = JsonPatch([delta.to_json_patch()])
            result = _apply_patch_safely(patch, result, delta)
            continue

        # Handle custom operations
        current_value = get_value_at_path(result, delta.path)

        match delta.op:
            case "concat_string":
                result = _handle_concat_string(current_value, result, delta)

            case "inc":
                result = _handle_inc(current_value, result, delta)

            case _:
                raise InvalidOperationError(delta.op, delta_object=delta)

    return cast(T, result)
