from typing import Any

from jsonpatch import JsonPatch, JsonPatchConflict
from jsonpointer import JsonPointer, JsonPointerException, resolve_pointer, set_pointer


def ensure_parents(doc: Any, path: str) -> None:
    """
    Ensure all parent containers in JSON Pointer `path` exist.
    Uses jsonpointer to parse tokens; creates dicts/lists as needed.
    """
    parts = JsonPointer(path).parts
    if not parts:
        return
    pointer_so_far = ""
    for i, token in enumerate(parts[:-1]):
        pointer_so_far = f"{pointer_so_far}/{token}"
        try:
            resolve_pointer(doc, pointer_so_far)
        except JsonPointerException:
            # Pick container type by looking at the next token
            nxt = parts[i + 1] if i + 1 < len(parts) else None
            container = [] if (nxt is not None and nxt.isdigit()) else {}
            set_pointer(doc, pointer_so_far, container, inplace=True)


def apply_delta(doc: dict[str, Any], delta: dict[str, Any]) -> None:
    """
    Apply a single delta dict like:
      {"op": "add|replace|concat_string", "path": "/a/b", "value": ...}
    Uses jsonpatch/jsonpointer for path semantics.
    """
    op = delta.get("op")
    path = delta.get("path")
    if not isinstance(path, str):
        raise ValueError(f"Invalid patch path: {path!r}")

    if op in ("add", "replace"):
        try:
            JsonPatch([delta]).apply(doc, in_place=True)
        except (JsonPatchConflict, JsonPointerException):
            # Parent(s) might be missing, create, then re-apply
            ensure_parents(doc, path)
            JsonPatch([delta]).apply(doc, in_place=True)
        return

    if op == "concat_string":
        try:
            cur = resolve_pointer(doc, path)
        except JsonPointerException:
            ensure_parents(doc, path)
            cur = ""
        if not isinstance(cur, str):
            cur = "" if cur is None else str(cur)
        new_val = cur + str(delta.get("value", ""))
        set_pointer(doc, path, new_val, inplace=True)
        return

    raise ValueError(f"Unsupported op: {op}")
