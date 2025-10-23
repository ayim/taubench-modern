import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def _strip_code_fences(s: str) -> str:
    m = _CODE_FENCE_RE.match(s.strip())
    return m.group(1) if m else s


def _extract_outer_json_object(text: str) -> str | None:
    """
    Conservative extractor:
    - strips code fences
    - finds the first '{' and returns a balanced JSON object up to its matching '}'
    - returns None if not found/balanced
    """
    s = _strip_code_fences(text)
    start = s.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def parse_json_object(text: str) -> dict[str, Any]:
    """
    Attempts to parse a JSON object from arbitrary LLM output.
    Raises ValueError if it cannot produce a dict.
    """
    candidate = _extract_outer_json_object(text)
    if candidate is None:
        raise ValueError("No JSON object found in text")

    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as e:
        # Optional conservative fixes: remove trailing commas before } or ]
        candidate_fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            obj = json.loads(candidate_fixed)
        except json.JSONDecodeError:
            # As a last resort, raise with the original error for debuggability
            raise ValueError(f"Cannot parse JSON: {e}") from e

    if not isinstance(obj, dict):
        raise ValueError("Top-level JSON value is not an object")

    return obj
