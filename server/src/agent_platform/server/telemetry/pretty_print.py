# ruff: noqa: PLR1714, PLR0912, PLR0911, C901

"""
Pretty print module for formatting strings with python-like dict/string/list syntax
with proper indentation.

Note: ported over from robocorp log (typescript implementation)
"""

from structlog import get_logger

from agent_platform.server.telemetry.parsing_utils import ParsingUtils

logger = get_logger(__name__)


MAX_CHARS_TO_CONSIDER_SMALL_LINE = 40


def format_str(s: str) -> str:
    """Format a string by replacing escaped newlines and handling multi-line literals."""
    new_s = s.replace("\\n", "\n")
    if len(new_s) == len(s):
        return s
    c = s[0]
    if s[-1] == c:
        return f"{c}{c}{new_s}{c}{c}"
    else:
        return f"{c}{c}{new_s}"


class PrettyPrinter:
    """A pretty printer for formatting code with proper indentation."""

    def __init__(self, full: str, indent_string: str = "  ") -> None:
        self.indentation_level = 0
        self.indentation_string = ""
        self.formatted: list[str] = []
        self.full = full
        self.indent_string = indent_string

        self.update_indentation_string()

        self.parsing = ParsingUtils(full, True)

        self.length = len(full)
        self.skip_spaces = False

    def update_indentation_string(self) -> None:
        """Update the indentation string based on the current indentation level."""
        self.indentation_string = self.indent_string * self.indentation_level

    def format_in_single_line(self, start: int, end: int) -> None:
        """Format a section of code in a single line."""
        i = start
        while i < end:
            current_char = self.parsing.char_at(i)

            if current_char == '"' or current_char == "'":
                j = self.parsing.find_next_single(i + 1, current_char)
                if j == -1:
                    j = self.length
                self.formatted.append(format_str(self.full[i : j + 1]))
                i = j + 1
                continue

            if self.skip_spaces and (current_char == " " or current_char == "\t"):
                i += 1
                continue
            self.skip_spaces = False

            if current_char == ",":
                self.formatted.append(current_char)
                self.formatted.append(" ")
                self.skip_spaces = True
                i += 1
                continue
            self.formatted.append(current_char)
            i += 1

    def format_str(self) -> str:
        """Format the entire string with proper indentation."""
        i = 0
        while i < self.length:
            current_char = self.parsing.char_at(i)

            if current_char == '"' or current_char == "'":
                j = self.parsing.find_next_single(i + 1, current_char)
                if j == -1:
                    j = self.length
                self.formatted.append(format_str(self.full[i : j + 1]))
                i = j + 1
                continue

            if self.skip_spaces and (current_char == " " or current_char == "\t"):
                i += 1
                continue
            self.skip_spaces = False

            if current_char == "{" or current_char == "[" or current_char == "(":
                j = self.parsing.eat_par(i, None, current_char)
                if j == -1:
                    self.formatted.append(current_char)
                    i += 1
                    continue

                if j - i < MAX_CHARS_TO_CONSIDER_SMALL_LINE:
                    self.format_in_single_line(i, j + 1)
                    i = j + 1
                else:
                    # Add indentation after opening a bracket.
                    self.indentation_level += 1
                    self.update_indentation_string()
                    self.formatted.append(current_char)
                    self.formatted.append("\n")
                    self.formatted.append(self.indentation_string)
                    i += 1
            elif current_char == "}" or current_char == "]" or current_char == ")":
                # Decrease the indentation level after closing a bracket.
                if self.indentation_level > 0:
                    self.indentation_level -= 1
                    self.update_indentation_string()
                    self.formatted.append("\n")
                    self.formatted.append(self.indentation_string)
                    self.formatted.append(current_char)
                else:
                    self.formatted.append(current_char)
                i += 1
            elif current_char == ",":
                # Add a new line after comma
                self.formatted.append(current_char)
                self.formatted.append("\n")
                self.formatted.append(self.indentation_string)
                self.skip_spaces = True
                i += 1
            else:
                self.formatted.append(current_char)
                i += 1
        return "".join(self.formatted)


def pretty_print(full: str, indent: int = 2) -> str:
    """Pretty print a string with proper formatting."""
    try:
        printer = PrettyPrinter(full, indent_string=" " * indent)
        ret = printer.format_str()
        return ret
    except Exception as err:
        # Something bad happened: show original.
        logger.error("Error pretty-printing", content=full, exc_info=err)
        return full
