import json
import re
from json.decoder import JSONDecodeError, scanstring  # type: ignore

# Accept: plain chars, simple escapes, non-surrogate \uXXXX, or a full surrogate pair.
_JSON_STRING_PREFIX_SAFE = re.compile(
    r"(?:"
    r'[^"\\]'  # plain
    r'|\\["\\/bfnrt]'  # simple escapes
    r"|\\u(?!d(?:[89ab]|[c-f]))[0-9a-f]{4}"  # \uXXXX, not D800--DFFF
    r"|\\ud[89ab][0-9a-f]{2}\\ud[c-f][0-9a-f]{2}"  # surrogate pair
    r")*",
    re.IGNORECASE,
).match


def _decode_longest_prefix(body: str) -> str:
    m = _JSON_STRING_PREFIX_SAFE(body)
    prefix = body[: m.end()] if m else ""
    return json.loads('"' + prefix + '"')


def _read_json_string_token(s: str, i_quote: int):
    if i_quote >= len(s) or s[i_quote] != '"':
        return None, i_quote, False
    try:
        val, end = scanstring(s, i_quote + 1, True)
        return val, end, True  # end is index of closing quote
    except JSONDecodeError:
        return None, i_quote, False


class _TopLevelStringValueFinder:
    """Find the start of a top-level string value for ``field_name``.

    Minimal top-level scanner: it recognizes only the first JSON object in the input,
    then walks it tracking the current object depth. At depth 1 (top level inside the
    outermost object), it looks for string keys followed by ``:`` and values.

    Important behaviors (tested):
    - Ignores appearances of the field name inside any string literal.
    - Skips non-matching keys and their values; continues scanning for our key.
    - If the requested key is found but its value is not a string, returns ``-2`` so
      callers can return the original content unchanged.
    - Returns ``-1`` when there is not enough information yet (e.g. incomplete key).
    """

    def __init__(self, content: str, field_name: str) -> None:
        self.content = content
        self.field_name = field_name
        self.n = len(content)
        self.i = 0
        self.depth: int | None = None
        self.expecting_key = False

    def _skip_ws(self, k: int) -> int:
        while k < self.n and self.content[k].isspace():
            k += 1
        return k

    def _handle_open_brace(self) -> None:
        """Enter an object; the very first ``{`` starts our top-level search."""
        if self.depth is None:
            self.depth = 1
            self.expecting_key = True
        else:
            self.depth += 1
        self.i += 1

    def _handle_close_brace(self) -> int:
        """Leave an object; when the top-level object closes, search ends."""
        if self.depth is not None:
            self.depth -= 1
            if self.depth == 0:
                return -1
        self.i += 1
        return 0

    def _handle_comma(self) -> None:
        """At depth 1, commas separate pairs; the next token is expected to be a key."""
        if self.depth == 1:
            self.expecting_key = True
        self.i += 1

    def _handle_string(self) -> int:
        """Handle a string token either as a key (at depth 1) or skip it.

        Returns:
            > 0: The start index of the target value body (immediately after the opening
                 quote of the value string).
            -1:  Incomplete token encountered; the key cannot yet be determined.
            -2:  The requested key exists but does not hold a string value.
             0:  Keep scanning.
        """
        # When expecting a key at top level, attempt to read it
        if self.depth == 1 and self.expecting_key:
            key, j, complete = _read_json_string_token(self.content, self.i)
            if not complete or key is None:
                return -1
            self.i = self._skip_ws(j)
            if self.i >= self.n or self.content[self.i] != ":":
                self.expecting_key = False
                return 0
            self.i += 1
            self.i = self._skip_ws(self.i)
            if key == self.field_name:
                if self.i >= self.n or self.content[self.i] != '"':
                    return -2
                # Found the start position
                return self.i + 1
            self.expecting_key = False
            return 0

        # Otherwise, skip over the string literal entirely
        ret = 0
        _, j, complete = _read_json_string_token(self.content, self.i)
        if not complete:
            ret = -1
        else:
            self.i = j
        return ret

    def find(self) -> int:
        while self.i < self.n:
            ch = self.content[self.i]
            if ch == "{":
                self._handle_open_brace()
                continue
            if ch == "}":
                ret = self._handle_close_brace()
                if ret:
                    return ret
                continue
            if ch == "," and self.depth == 1:
                self._handle_comma()
                continue
            if ch == '"':
                ret = self._handle_string()
                if ret:
                    return ret
                continue
            self.i += 1
        return -1


def _find_top_level_string_value_start(content: str, field_name: str) -> int:
    return _TopLevelStringValueFinder(content, field_name).find()


def clean_json_string(content: str, field_name: str) -> str:
    """
    Extract the top-level field's string value from JSON (best-effort, partial tolerant).

    Contract (by design, per requirements):
    - Only supported shape: a *top-level* JSON object with a *top-level* key `field_name`
      whose value is a JSON string.
    - If the JSON parses cleanly and that condition holds, return the decoded string value.
    - If parsing fails (partial stream), locate the top-level field and decode its *string*
      value incrementally with best-effort semantics.
    - If the field is missing, nested, or not a string, **return the original content**.
    """
    # Fast path: fully-formed JSON (top-level object, top-level string value)
    try:
        obj = json.loads(content)
        if isinstance(obj, dict):
            val = obj.get(field_name)
            if isinstance(val, str):
                return val
        return content
    except json.JSONDecodeError:
        pass

    # Partial path: scan for top-level key and a string value
    pos = _find_top_level_string_value_start(content, field_name)
    if pos in {-1, -2}:
        return content

    # Decode incrementally from the start of the string body
    return _decode_longest_prefix(content[pos:])
