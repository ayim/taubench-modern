import re
from collections.abc import Mapping, Sequence
from typing import Any

from jsonpointer import JsonPointer, escape

from agent_server_types_v2.delta.base import (
    GenericDelta,
)
from agent_server_types_v2.delta.errors import InvalidPathError

# Compile regex once at module level for better performance
_ARRAY_INDEX_PATTERN = re.compile(r"^(?:0|[1-9][0-9]*)$")
_PATH_PATTERN = re.compile(r"^/|(/[^/]+)+$")


def get_value_at_path(obj: Any, path: str | JsonPointer) -> Any:
    """Get a value at a specific path in an object according to RFC 6901.

    Arguments:
        obj: The object to get the value from.
        path: The JSON Pointer path to get the value from.

    Returns:
        The value at the path.

    Raises:
        InvalidPathError: If the path is invalid.
    """
    try:
        return JsonPointer(str(path)).resolve(obj)
    except Exception:
        return None


def _is_array(value: Any) -> bool:
    """Check if a value is an array.

    Args:
        value: The value to check.

    Returns:
        True if the value is an array, False otherwise.
    """
    return isinstance(value, Sequence) and not isinstance(value, str | bytes)


def _validate_array_index(index_str: str, array_len: int | None = None) -> int:
    """Validate and parse a JSON Pointer array index according to RFC 6901.

    Args:
        index_str: The string representation of the array index.
        array_len: Optional length of the array for bounds checking.

    Returns:
        The parsed integer index.

    Raises:
        InvalidPathError: If the index is invalid.
    """
    if index_str == "-":
        return array_len if array_len is not None else 0

    if not _ARRAY_INDEX_PATTERN.match(index_str):
        raise ValueError(
            f"Invalid array index: {index_str}. Must be '0' or a number "
            f"without leading zeros.",
        )

    try:
        return int(index_str)
    except ValueError as e:
        raise ValueError(f"Invalid array index: {index_str}") from e


def _is_valid_array_index(index_str: str, array_len: int | None = None) -> bool:
    """Check if an array index is valid.

    Args:
        index_str: The string representation of the array index.
        array_len: Optional length of the array for bounds checking.

    Returns:
        True if the index is valid, False otherwise.
    """
    try:
        _validate_array_index(index_str, array_len)
        return True
    except ValueError:
        return False


def _validate_direct_array_op(
    initial_value: Any,
    pointer: JsonPointer,
    path_attr: str,
    is_add_op: bool = False,
) -> None:
    """Validate an operation directly on an array (e.g., adding/removing elements).

    Args:
        initial_value: The initial value to validate against.
        path: The path to validate.
        path_attr: Which path attribute is being validated ("path" or "from_").
        pointer: The JsonPointer to validate.
        is_add_op: If True, we are validating an "add" operation.
    """
    if is_add_op and pointer.parts[-1] == "-":
        return

    current = initial_value

    # For array indices, we need our custom validation to ensure no leading zeros
    for part in pointer.parts:
        if _is_array(current):
            try:
                _validate_array_index(part, len(current))
            except ValueError as e:
                raise InvalidPathError(
                    pointer.path,
                    path_attr=path_attr,
                    detailed_message=str(e),
                ) from e
        try:
            current = pointer.walk(current, part)
        except Exception as e:
            # For add operations, as long as the parent exists, the path is valid
            if is_add_op:
                return
            raise InvalidPathError(
                pointer.path,
                path_attr=path_attr,
                detailed_message=str(e),
            ) from e


def _validate_array_element_property_op(
    pointer: JsonPointer,
    path_attr: str,
    array_value: Any,
) -> None:
    """Validate an operation on an array element's property (e.g., modifying object
    properties).

    Example document and operation:

        # Document
        {
            "array": [
                {"key": "value"}
            ]
        }
        # Operation
        {
            "op": "add",
            "path": "/array/0/new_key",
            "value": "new_value"
        }
        # Result
        {
            "array": [
                {"key": "value", "new_key": "new_value"}
            ]
        }

    Args:
        initial_value: The initial value to validate against.
        path: The path to validate.
        path_attr: Which path attribute is being validated ("path" or "from_").
        pointer: The JsonPointer to validate.
        array_value: The array containing the element we're operating on.
        array_pointer: The JsonPointer to the array we're operating on.
        is_add_op: If True, we are validating an "add" operation.
    """
    # TODO: We need to handle arrays in arrays as well, I'm not sure we do now.
    # Get the array index from the path
    array_index = pointer.parts[-2]  # Second to last part is the array index

    try:
        # Validate the array index
        _validate_array_index(array_index, len(array_value))
        # Verify the array element is an object when accessing/modifying its properties
        if not isinstance(array_value[int(array_index)], Mapping):
            raise InvalidPathError(
                pointer.path,
                path_attr=path_attr,
                detailed_message="Cannot access/modify properties of "
                "non-object array element",
            )
    except Exception as e:
        raise InvalidPathError(
            pointer.path,
            path_attr=path_attr,
            detailed_message=str(e),
        ) from e


def _validate_single_path(
    initial_value: Any,
    pointer: JsonPointer,
    path_attr: str,
    is_add_op: bool = False,
) -> None:
    """Helper to validate a single path string.

    Args:
        initial_value: The initial value to validate against.
        pointer: The JsonPointer to validate.
        path_attr: Which path attribute is being validated ("path" or "from_").
        is_add_op: If True, we are validating an "add" operation.
    """
    if not pointer.parts:  # Empty path is always valid
        return
    # Test path pattern (note, array's can't be tested unless
    # we have an initial value beause ints can be valid object keys)
    if not _PATH_PATTERN.match(pointer.path):
        raise InvalidPathError(
            pointer.path,
            path_attr=path_attr,
        )
    if initial_value is None:
        # Can't validate anything else about the path without an initial value
        return

    # Get the parent and grandparent values to check for array operations
    parent_pointer = _get_parent_pointer(pointer)
    parent_value = get_value_at_path(initial_value, parent_pointer)

    grandparent_value = None
    grandparent_pointer = None
    # If we have at least 2 parts, also check the grandparent
    if len(pointer.parts) >= 2:  # noqa: PLR2004
        grandparent_pointer = _get_parent_pointer(parent_pointer)
        grandparent_value = get_value_at_path(initial_value, grandparent_pointer)

    try:
        # Handle direct array operations
        if _is_array(parent_value):
            _validate_direct_array_op(
                initial_value,
                pointer,
                path_attr,
                is_add_op,
            )
        # Handle operations on array element properties
        elif _is_array(grandparent_value) and _is_valid_array_index(
            pointer.parts[-2],
            len(grandparent_value),
        ):
            _validate_array_element_property_op(
                pointer,
                path_attr,
                grandparent_value,
            )
        # For non-array operations, let JsonPointer handle validation
        elif is_add_op:
            # For add operations, only validate up to the parent
            parent_pointer.resolve(initial_value)
        else:
            pointer.resolve(initial_value)
    except InvalidPathError:
        raise
    except Exception as e:
        raise InvalidPathError(
            pointer.path,
            path_attr=path_attr,
            detailed_message=str(e),
        ) from e


def validate_delta_path(initial_value: Any, delta: GenericDelta) -> None:
    """Validate the paths of a delta object according to RFC 6901 and RFC 6902.

    For "add" operations, the parent path must exist but the final path component
    may be missing. For all other operations (except empty path operations), the
    full path must exist.

    Args:
        initial_value: The initial value of the object.
        delta: The delta object to validate.

    Raises:
        InvalidPathError: If the path is invalid.
    """
    # Empty path operations are always valid as they refer to the whole document
    if not delta.path:
        return

    # For add, move, and copy operations, we only need to validate that
    # the parent path of the path attribute exists
    validate_parent_only = delta.op in {"add", "move", "copy"}

    # Validate main path
    path_attr = "path"
    try:
        _validate_single_path(
            initial_value,
            JsonPointer(delta.path),
            path_attr,
            validate_parent_only,
        )

        # Validate from_ path for move/copy operations - these always need
        # full path validation
        if delta.op in {"move", "copy"} and delta.from_ is not None:
            path_attr = "from_"
            _validate_single_path(
                initial_value,
                JsonPointer(delta.from_),
                path_attr,
                is_add_op=False,
            )
    except InvalidPathError as e:
        e.delta_object = delta
        raise e
    except Exception as e:
        raise InvalidPathError(
            delta.path,
            path_attr=path_attr,
            detailed_message=str(e),
            delta_object=delta,
        ) from e


def _get_parent_pointer(pointer: JsonPointer, level: int = 1) -> JsonPointer:
    """Get the parent pointer for a given JsonPointer.

    According to RFC 6901, an empty string represents the whole document.
    For paths with only one component, the parent is the root (empty string).
    For all other paths, we need to join the parts with "/" and prefix with "/".

    Args:
        pointer: The JsonPointer to get the parent of.
        level: The level of parent to get, defaults to 1 (immediate parent).

    Returns:
        A JsonPointer representing the parent path.
    """
    if not pointer.parts:  # Empty path
        return pointer
    if len(pointer.parts) == 1:  # Root is parent
        return JsonPointer("")
    # Join all but the last part and ensure leading slash
    escaped_parts = [escape(part) for part in pointer.parts[:-level]]
    return JsonPointer("/" + "/".join(escaped_parts))
