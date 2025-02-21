"""This module contains the logic for computing delta objects for
generic objects (they must be JSON serializable).
"""

from typing import Any

from jsonpatch import JsonPatch

from agent_server_types_v2.delta.base import NO_VALUE, GenericDelta


def compute_generic_delta(
    old_val: Any,
    new_val: Any,
    path: str = "",
) -> list[GenericDelta]:
    """Compute the delta between two generic values.

    Uses specialized delta computations for our custom operations where possible
    (string concatenation, increments) and falls back to standard
    JSON Patch operations for everything else.

    Arguments:
        old_val: The old metadata value.
        new_val: The new metadata value.
        path: The path to the metadata value.

    Returns:
        The list of delta operations to apply.
    """
    # No change => no delta
    if old_val == new_val:
        return []

    # Try specialized operations first if types match
    if type(old_val) is type(new_val):
        if isinstance(old_val, str):
            return _compute_delta_str(path, old_val, new_val)
        elif isinstance(old_val, int):
            return _compute_delta_int(path, old_val, new_val)
        elif isinstance(old_val, list):
            return _compute_delta_list(path, old_val, new_val)
        elif isinstance(old_val, dict):
            return _compute_delta_dict(path, old_val, new_val)

    # For everything else, use standard JSON Patch diff
    patch = JsonPatch.from_diff(
        old_val if old_val is not None else {},
        new_val if new_val is not None else {},
    )

    # Convert JSON Patch operations to our GenericDelta format
    return [
        GenericDelta(
            op=op["op"],
            path=path + op["path"] if path else op["path"],
            value=op.get("value"),
            from_=op.get("from"),
        )
        for op in patch
    ]


def _sub_path(base: str, key: str | int) -> str:
    """Builds a path like "/base/key". If base is "", then it becomes "/key"."""
    if base == "":
        return f"/{key}"
    else:
        return f"{base}/{key}"


def _compute_delta_str(path: str, old: str, new: str) -> list[GenericDelta]:
    """If `new` starts with `old`, produce a `concat_string` op
    with the difference. Otherwise, produce a `replace` if changed.

    Arguments:
        path: The path to the string.
        old: The old string value.
        new: The new string value.

    Returns:
        The list of delta operations to apply.
    """
    if new == old:
        return []
    if new.startswith(old):
        extra = new[len(old) :]
        return [GenericDelta(op="concat_string", path=path, value=extra)]
    else:
        # completely changed
        return [GenericDelta(op="replace", path=path, value=new)]


def _compute_delta_int(path: str, old: int, new: int) -> list[GenericDelta]:
    """If `new > old`, produce an `inc` op with the delta. If the integer
    is smaller or negative change, do a replace.

    Arguments:
        path: The path to the integer.
        old: The old integer value.
        new: The new integer value.

    Returns:
        The list of delta operations to apply.
    """
    if new == old:
        return []
    if new > old:
        amount = new - old
        return [GenericDelta(op="inc", path=path, value=amount)]
    else:
        # smaller or some other scenario => replace
        return [GenericDelta(op="replace", path=path, value=new)]


def _compute_delta_list(path: str, old: list, new: list) -> list[GenericDelta]:
    """Computes deltas for list-like values.

    Strategies:
    - For changed values, recurse into sub-values
    - For new items, use standard JSON Patch add ops

    Arguments:
        path: The path to the list.
        old: The old list value.
        new: The new list value.

    Returns:
        The list of delta operations to apply.
    """
    if old == new:
        return []

    ops = []

    # 1) Check common indices for changes
    for i in range(min(len(old), len(new))):
        if old[i] != new[i]:
            # Recursively compute delta for this index
            sub_ops = compute_generic_delta(old[i], new[i], _sub_path(path, i))
            ops.extend(sub_ops)

    # 2) Add new items
    for i in range(len(old), len(new)):
        ops.append(
            GenericDelta(
                op="add",
                path=_sub_path(path, i),
                value=new[i],
            ),
        )

    return ops


def _compute_delta_dict(path: str, old: dict, new: dict) -> list[GenericDelta]:
    """Computes deltas for dict-like values.

    Strategies:
    - If keys are removed, use standard JSON Patch remove ops
    - For changed values, recurse into sub-values
    - For new keys, use standard JSON Patch add ops

    Arguments:
        path: The path to the dict.
        old: The old dict value.
        new: The new dict value.

    Returns:
        The list of delta operations to apply.
    """
    if old == new:
        return []

    ops = []

    # 1) Keys removed => use standard remove ops
    removed_keys = set(old.keys()) - set(new.keys())
    for k in removed_keys:
        ops.append(GenericDelta(op="remove", path=_sub_path(path, k), value=NO_VALUE))

    # 2) Keys in both => compute sub-delta
    common_keys = set(old.keys()) & set(new.keys())
    for k in common_keys:
        sub_ops = compute_generic_delta(old[k], new[k], _sub_path(path, k))
        ops.extend(sub_ops)

    # 3) Brand-new keys => use standard add ops
    added_keys = set(new.keys()) - set(old.keys())
    for k in added_keys:
        ops.append(
            GenericDelta(
                op="add",
                path=_sub_path(path, k),
                value=new[k],
            ),
        )

    return ops
