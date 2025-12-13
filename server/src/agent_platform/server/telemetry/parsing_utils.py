# ruff: noqa: PLR1714, C901, PLR0912, PLR0911

"""
Helper module for parsing strings with bracket/quote matching.

Note: ported over from robocorp log (typescript implementation)
"""


def get_peer(c: str) -> str:
    """Return the matching bracket/quote character for the given character."""
    match c:
        case "{":
            return "}"
        case "}":
            return "{"
        case "(":
            return ")"
        case ")":
            return "("
        case "[":
            return "]"
        case "]":
            return "["
        case ">":
            return "<"
        case "<":
            return ">"
        case "'":
            return "'"
        case '"':
            return '"'
        case "/":
            return "/"
        case "`":
            return "`"
        case _:
            raise ValueError(f"Unable to find peer for: {c}")


class FastStringBuffer:
    """A buffer for efficiently building strings."""

    def __init__(self) -> None:
        self.contents: list[str] = []

    def right_trim_whitespaces_and_tabs(self) -> None:
        """Remove trailing whitespaces and tabs from the buffer."""
        while True:
            if len(self.contents) == 0:
                return
            c = self.contents[-1]
            if c == " " or c == "\t":
                self.contents.pop()
            else:
                break

    def append(self, c: str) -> None:
        """Append a character to the buffer."""
        self.contents.append(c)


class ParsingUtils:
    """Utility class for parsing strings with bracket/quote matching."""

    def __init__(self, contents: str, return_negative_on_no_match: bool) -> None:
        self.return_negative_on_no_match = return_negative_on_no_match
        self.contents = contents

    def len(self) -> int:
        """Return the length of the contents."""
        return len(self.contents)

    def char_at(self, i: int) -> str:
        """Return the character at the given index."""
        if i < 0:
            i = len(self.contents) + i
        if i < 0 or i >= len(self.contents):
            raise IndexError(f"Index {i} out of range")
        return self.contents[i]

    def eat_comments(self, buf: FastStringBuffer | None, i: int) -> int:
        """Eat comments from the current position."""
        return self.eat_comments2(buf, i, True)

    def eat_comments2(self, buf: FastStringBuffer | None, i: int, add_new_line: bool) -> int:
        """Eat comments from the current position with optional newline handling."""
        length = self.len()
        c = "\0"

        while i < length and (c := self.char_at(i)) != "\n" and c != "\r":
            if buf is not None:
                buf.append(c)
            i += 1

        if not add_new_line:
            if c == "\r" or c == "\n":
                i -= 1
                return i

        if i < length:
            if buf is not None:
                buf.append(c)
            if c == "\r":
                if i + 1 < length and self.char_at(i + 1) == "\n":
                    i += 1
                    if buf is not None:
                        buf.append("\n")

        return i

    def eat_whitespaces(self, buf: FastStringBuffer | None, i: int) -> int:
        """Eat whitespaces from the current position."""
        length = self.len()

        while i < length and self.char_at(i) == " ":
            if buf is not None:
                buf.append(self.char_at(i))
            i += 1

        i -= 1

        return i

    def eat_literals(self, buf: FastStringBuffer | None, start_pos: int) -> int:
        """Eat string literals from the current position."""
        return self.eat_literals2(buf, start_pos, False)

    def eat_literals2(
        self,
        buf: FastStringBuffer | None,
        start_pos: int,
        right_trim_multiline: bool,
    ) -> int:
        """Eat string literals from the current position with optional trimming."""
        start_char = self.char_at(start_pos)

        if start_char != '"' and start_char != "'":
            raise ValueError(f"Wrong location to eat literals. Expecting ' or \". Found: >>{start_char}<<")

        end_pos = self.get_literal_end(start_pos, start_char)

        if buf is not None:
            right_trim = right_trim_multiline and self.is_multi_literal(start_pos, start_char)
            last_pos = min(end_pos, self.len() - 1)
            for i in range(start_pos, last_pos + 1):
                ch = self.char_at(i)
                if right_trim and (ch == "\r" or ch == "\n"):
                    buf.right_trim_whitespaces_and_tabs()
                buf.append(ch)
        return end_pos

    def is_multi_literal(self, i: int, curr: str) -> bool:
        """
        Check if we are at the start of a multi-line literal.

        Args:
            i: current position (should have a ' or ")
            curr: the current char (' or ")
        Returns:
            whether we are at the start of a multi line literal or not.
        """
        length: int = self.len()
        if length <= i + 2:
            return False
        if self.char_at(i + 1) == curr and self.char_at(i + 2) == curr:
            return True
        return False

    def get_literal_end(self, i: int, curr: str) -> int:
        """Get the end position of a literal starting at the given position."""
        multi = self.is_multi_literal(i, curr)

        if multi:
            j = self.find_next_multi(i + 3, curr)
        else:
            j = self.find_next_single(i + 1, curr)
        return j

    def eat_par(self, i: int, buf: FastStringBuffer | None, par: str) -> int:
        """Eat a parenthesized expression from the current position."""
        c = " "

        closing_par = get_peer(par)

        j = i + 1
        length = self.len()
        while j < length and (c := self.char_at(j)) != closing_par:
            j += 1

            if c == "'" or c == '"':
                j = self.eat_literals(None, j - 1) + 1
                if j == 0 and self.return_negative_on_no_match:
                    return -1
            elif c == par:
                j = self.eat_par(j - 1, None, par) + 1
                if j == 0 and self.return_negative_on_no_match:
                    return -1
            elif buf is not None:
                buf.append(c)
        if self.return_negative_on_no_match and c != closing_par:
            return -1
        j = min(length, j)
        return j

    def find_next_single(self, i: int, curr: str) -> int:
        """Find the next occurrence of a single quote character."""
        ignore_next = False
        length = self.len()
        while i < length:
            c = self.char_at(i)

            if not ignore_next and c == curr:
                return i

            if not ignore_next:
                if c == "\\":
                    ignore_next = True
            else:
                ignore_next = False

            i += 1
        if self.return_negative_on_no_match:
            return -1
        return i

    def find_previous_single(self, i: int, curr: str) -> int:
        """Find the previous occurrence of a single quote character."""
        while i >= 0:
            c = self.char_at(i)

            if c == curr:
                if i > 0:
                    if self.char_at(i - 1) == "\\":
                        i -= 1
                        continue
                return i

            i -= 1
        if self.return_negative_on_no_match:
            return -1
        return i

    def find_next_multi(self, i: int, curr: str) -> int:
        """Find the next occurrence of a multi-line literal ending."""
        length = self.len()
        while i + 2 < length:
            c = self.char_at(i)
            if c == curr and self.char_at(i + 1) == curr and self.char_at(i + 2) == curr:
                return i + 2
            i += 1
            if c == "\\":
                i += 1

        if self.return_negative_on_no_match:
            return -1

        if length < i + 2:
            return length
        return i + 2
