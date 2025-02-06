from typing import Any

from agent_server_types_v2.streaming.generic.delta import GenericDelta


def compute_generic_delta(old_val: Any, new_val: Any, path: str = "") -> list[GenericDelta]:
    """Compute the delta between two generic values.

    Dispatches to type-specific delta computations.

    Arguments:
        old_val: The old metadata value.
        new_val: The new metadata value.
        path: The path to the metadata value.

    Returns:
        The list of delta operations to apply.
    """
    # If types differ, we can't do a specialized operation => replace
    if type(old_val) is not type(new_val):
        return [GenericDelta(op="replace", path=path, value=new_val)]

    # Type-based dispatch
    if isinstance(old_val, str):
        return _compute_delta_str(path, old_val, new_val)
    elif isinstance(old_val, int):
        return _compute_delta_int(path, old_val, new_val)
    elif isinstance(old_val, list):
        return _compute_delta_list(path, old_val, new_val)
    elif isinstance(old_val, dict):
        return _compute_delta_dict(path, old_val, new_val)
    else:
        # If it's something else (float, bool, None, etc.) => just replace if changed
        return [GenericDelta(op="replace", path=path, value=new_val)]


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
    - If new == old + appended items, produce `append_array`.
    - If we have the same or more items in the new list, produce a delta for each item.
    - Fallback to `replace` if we can't do anything else.

    Arguments:
        path: The path to the list.
        old: The old list value.
        new: The new list value.

    Returns:
        The list of delta operations to apply.
    """
    if old == new:
        return []

    len_old = len(old)
    len_new = len(new)

    # 1) Check if we appended new items at the end
    if len_new > len_old and old == new[:len_old]:
        appended = new[len_old:]
        return [GenericDelta(op="append_array", path=path, value=appended)]

    # 2) Check if we have the same or more items in the new list
    if len_new >= len_old:
        # Let's try and create a compare for each item (assuming they align)
        ops = []
        for i in range(len_old):
            sub_ops = compute_generic_delta(old[i], new[i], _sub_path(path, i))
            ops.extend(sub_ops)
        # And for any new items, we'll just replace them
        for i in range(len_old, len_new):
            ops.append(GenericDelta(op="replace", path=_sub_path(path, i), value=new[i]))
        return ops

    # fallback
    return [GenericDelta(op="replace", path=path, value=new)]


def _compute_delta_dict(path: str, old: dict, new: dict) -> list[GenericDelta]:
    """Computes deltas for dict-like values.

    Strategies:
    - If a key is removed, produce a `remove` op.
    - If a key is added, produce a `merge` op.
    - If a key is changed, recurse into the sub-dict.

    Arguments:
        path: The path to the dict.
        old: The old dict value.
        new: The new dict value.

    Returns:
        The list of delta operations to apply.
    """
    ops = []

    # 1) Keys removed
    removed_keys = set(old.keys()) - set(new.keys())
    for k in removed_keys:
        ops.append(GenericDelta(op="remove", path=_sub_path(path, k), value=None))

    # 2) Keys in both => compute sub-delta
    common_keys = set(old.keys()) & set(new.keys())
    for k in common_keys:
        sub_ops = compute_generic_delta(old[k], new[k], _sub_path(path, k))
        ops.extend(sub_ops)

    # 3) Brand-new keys => combine into a single "merge" op
    added_keys = set(new.keys()) - set(old.keys())
    if added_keys:
        added_dict = {k: new[k] for k in added_keys}
        ops.append(GenericDelta(op="merge", path=path, value=added_dict))

    return ops
