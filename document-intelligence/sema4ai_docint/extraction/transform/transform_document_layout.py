from copy import deepcopy
from pathlib import Path
from typing import Any


class TransformDocumentLayout:
    @classmethod
    def get_doc_uuid(cls, file_path: Path) -> str:
        import warnings

        from sema4ai_docint.utils import compute_document_id

        warnings.warn(
            "TransformDocumentLayout.get_doc_uuid is deprecated, "
            + "use utils.compute_document_id instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return compute_document_id(file_path)

    @classmethod
    def tokens(cls, path: str) -> list[str]:
        """Split a period-separated path into a list of tokens."""
        return path.split(".")

    @classmethod
    def collect(cls, node: Any, tokens: list[str]) -> list[Any] | Any | None:
        """Return all values that match the (possibly wildcard) path."""
        if not tokens:
            return node

        head, *tail = tokens
        if head.endswith("[*]"):
            key = head[:-3]
            child = node.get(key) if isinstance(node, dict) else None
            out = []

            if isinstance(child, list):
                for item in child:
                    xform = cls.collect(item, tail)
                    if isinstance(xform, list) and tail and tail[0].endswith("[*]"):
                        out.extend(xform)
                    else:
                        out.append(cls.collect(item, tail))
            else:
                out.append(child)
            return out
        else:
            nxt = node.get(head) if isinstance(node, dict) else None
            if nxt is not None:
                return cls.collect(nxt, tail)
            return None

    @classmethod
    def set_path(cls, root: dict[str, Any], dotted: str, value: Any) -> None:
        """Create nested objects as needed and assign value at the dotted path."""
        cur = root
        path_parts = dotted.split(".")

        # Handle the case where we're setting a nested path and intermediate parts might be lists
        for i, part in enumerate(path_parts[:-1]):
            if part not in cur:
                cur[part] = {}
            elif isinstance(cur[part], list):
                # If we encounter a list in the path, we need to merge the value into each list item
                remaining_path = ".".join(path_parts[i + 1 :])
                for item in cur[part]:
                    if isinstance(item, dict):
                        cls.set_path(item, remaining_path, value)
                return
            cur = cur[part]

        # Set the final value
        final_key = path_parts[-1]
        cur[final_key] = value

    # TODO: Fix lint issues in this function
    @classmethod
    def cast(cls, val: Any, kind: str | None) -> Any:  # noqa: C901, PLR0912, PLR0911
        """Apply a simple cast when transform is provided."""
        if kind is None:
            return val
        match kind:
            case "int":
                # Basic normalization
                if isinstance(val, str):
                    # Trim whitespace
                    val = val.strip()

                    # Remove commas
                    if "," in val:
                        val = val.replace(",", "")

                    # Remove everything after the decimal point
                    if "." in val:
                        idx = val.index(".")
                        val = val[:idx]

                return int(val)
            case "float":
                # handle dollar amounts like "$ 1,234,567.00"
                if isinstance(val, str):
                    # Trim whitespace
                    val = val.strip()

                    # Remove commas
                    if "," in val:
                        val = val.replace(",", "")

                    # Remove dollar sign
                    if val.startswith("$"):
                        val = val[1:]

                return float(val)
            case "str":
                return str(val)
            case "bool":
                if isinstance(val, str):
                    # Trim whitespace
                    val = val.strip()
                    # Some helpful alternatives to boolean values
                    if val.lower() in ["true", "yes", "y", "1"]:
                        return True
                    elif val.lower() in ["false", "no", "n", "0"]:
                        return False

                return bool(val)
            case _:
                return val

    @classmethod
    def _resolve_relative(cls, stack: list[Any], rel_path: str) -> Any | None:
        """Resolve relative path against stack where stack[0] is root and stack[-1] is current
        leaf."""
        segments = rel_path.split("/")
        up = 0
        while up < len(segments) and segments[up] == "..":
            up += 1

        idx = len(stack) - 1
        if not isinstance(stack[idx], dict):
            idx -= 1

        idx -= up
        if idx < 0:
            return None

        node = stack[idx]
        for seg in segments[up:]:
            for key in seg.split("."):
                if isinstance(node, dict) and key in node:
                    node = node[key]
                else:
                    return None
        return node

    @classmethod
    def flatten(
        cls, doc: dict[str, Any], src_tokens: list[str], extras: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Produce one merged object per element matched by src_tokens, plus any extra columns."""
        results = []

        def walk(node: Any, tokens: list[str], stack: list[Any]) -> None:
            if not tokens:
                merged = deepcopy(node) if isinstance(node, dict) else {"value": node}
                for new_key, rel_path in extras.items():
                    if rel_path == new_key:
                        continue

                    val = cls._resolve_relative(stack, rel_path)
                    if val is not None:
                        merged[new_key] = val
                        if not rel_path.startswith(".") and rel_path in merged:
                            merged.pop(rel_path)
                results.append(merged)
                return

            head, *tail = tokens
            if head.endswith("[*]"):
                key = head[:-3]
                seq = node.get(key, []) if isinstance(node, dict) else []
                for item in seq:
                    walk(item, tail, [*stack, item])
            else:
                nxt = node.get(head) if isinstance(node, dict) else None
                if nxt is not None:
                    walk(nxt, tail, [*stack, nxt])

        walk(doc, src_tokens, [doc])
        return results
