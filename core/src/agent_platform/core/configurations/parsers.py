"""Parsers for configuration fields."""

import ast
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import Field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import (
    Any,
    ClassVar,
    Literal,
    get_args,
    get_origin,
)

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class Parser(ABC):
    """A parser for a field in a configuration class. Use the `is_supported`
    property to check if the parser supports the provided field or the
    `supports_type` method to check if the parser supports a specific type.

    If no field is provided, the parser will assume it supports all types.

    Class can be used without initializing it with a field, just use the
    `supports_type` method to check if the parser supports a specific type.
    """

    _supported_types: ClassVar[set[Any]]
    """The types that the parser supports. Can include both concrete types and
    generic types like Literal, Union, etc.

    Note:
        We use `Any` here because Python's type system doesn't provide a way to
        properly type-hint a set that can contain both concrete types (like `str`)
        and generic types (like `Literal`). The `supports_type` method will check
        both direct type matches and the origin of generic types.

        Examples of valid types to include:
        - Concrete types: `str`, `int`, `bool`, `Path`
        - Generic types: `Literal`, `Union`, `Mapping`, `Sequence`

        When a field type is checked, the parser will:
        1. Check if the field type is directly in the supported types
        2. Check if the origin of the field type (for generic types) is in the
           supported types
    """

    def __init__(self, field: Field | None = None) -> None:
        """Initialize the parser with an optional field.

        When a field is provided, the parser checks if it supports the field's type
        using the `supports_type` method. This result is stored and can be accessed
        via the `is_supported` property.

        When no field is provided, the `is_supported` property will always return True.
        This is useful when you want to use the parser directly without checking type
        support, such as when you've already verified the type compatibility.

        Args:
            field: Optional field to check for type compatibility. If None, the parser's
                `is_supported` property will always return True.
        """
        self._field = field
        self._supports_field = self.supports_type(field.type) if field else True

    @property
    def is_supported(self) -> bool:
        """Check if the parser supports the field type."""
        return self._supports_field

    @abstractmethod
    def parse(self, value: Any) -> Any:
        """Parse a value."""
        ...

    @classmethod
    def supports_type(cls, field_type: Any) -> bool:
        """Check if this parser supports the given field type.

        Args:
            field_type: The type to check

        Returns:
            True if this parser supports the type, False otherwise
        """
        # Check if the field_type is directly in the supported types
        if field_type in cls._supported_types:
            return True

        # Check if the field_type is a generic type (like Literal, Union, etc.)
        # and if the origin of that generic type is in the supported types
        origin = get_origin(field_type)
        if origin is not None and origin in cls._supported_types:
            return True

        return False


class AstParserMixin(Parser):
    """A mixin for parsers that parse values using ast.literal_eval."""

    def literal_eval(
        self,
        value: Any,
        expected_types: UnionType | tuple[type, ...] | None = None,
    ) -> Any:
        """Parse a value using ast.literal_eval."""
        try:
            parsed_value = ast.literal_eval(str(value))
            if expected_types and not isinstance(parsed_value, expected_types):
                raise ValueError(
                    f"Value is not one of the expected types: {expected_types}",
                )
            return parsed_value
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"Failed to parse value: {value}") from e


class LiteralParser(AstParserMixin, Parser):
    """A parser for Literal types that validates values against allowed options."""

    # Support Literal as a generic type
    _supported_types: ClassVar[set[Any]] = {Literal}
    """This parser supports the `Literal` generic type. It will match any field type
    that is a `Literal` type, such as `Literal[str, int]` or `Literal[True, False]`.

    The parser will validate that the value matches one of the allowed options
    specified in the Literal type.
    """

    def __init__(self, field: Field | None = None) -> None:
        """Initialize the LiteralParser.

        Args:
            field: The field to check
        """
        super().__init__(field)
        self._field_type = field.type if field else None

    def parse(self, value: Any) -> Any:
        """Parse a value and ensure it's one of the allowed literal values.

        Args:
            value: The string value to parse

        Returns:
            The validated value

        Raises:
            ValueError: If the value doesn't match any of the allowed options
        """
        if self._field_type is None:
            return value

        literal_args = get_args(self._field_type)
        if not literal_args:
            return value

        # Check if the value matches any of the allowed literal values
        # Try to convert the string to match the type of the first literal value
        try:
            # Get the type of the first literal value to determine parsing strategy
            sample_type = type(literal_args[0])

            # Parse the value based on the type of the literal values
            if sample_type is str:
                parsed_value = value
            elif sample_type is int:
                parsed_value = int(value)
            elif sample_type is float:
                parsed_value = float(value)
            elif sample_type is bool:
                parsed_value = value.lower() in ("true", "1", "yes", "y", "t")
            else:
                # For other types, try using ast.literal_eval
                try:
                    parsed_value = self.literal_eval(value, literal_args)
                except (ValueError, SyntaxError):
                    parsed_value = value

            # Check if the parsed value is one of the allowed options
            if parsed_value in literal_args:
                return parsed_value

            # If it's not in the allowed values, raise ValueError
            raise ValueError(
                f"Value '{value}' is not one of the allowed options: {literal_args}",
            )
        except Exception as e:
            raise ValueError(
                f"Failed to parse Literal value '{value}': {e}",
            ) from e

    @classmethod
    def supports_type(cls, field_type: Any) -> bool:
        """Check if this parser supports the given field type.

        Args:
            field_type: The type to check

        Returns:
            True if this parser supports Literal types
        """
        # We can use the parent class's implementation since we've updated it
        return super().supports_type(field_type)


class StrParser(Parser):
    """A parser for a field in a configuration class that parses strings."""

    _supported_types: ClassVar[set[Any]] = {str}

    def parse(self, value: Any) -> str:
        """Parse a value from a string."""
        return str(value)


class IntParser(Parser):
    """A parser for a field in a configuration class that parses integers."""

    _supported_types: ClassVar[set[Any]] = {int}

    def parse(self, value: Any) -> int:
        """Parse a value from a string."""
        return int(value)


class FloatParser(Parser):
    """A parser for a field in a configuration class that parses floats."""

    _supported_types: ClassVar[set[Any]] = {float}

    def parse(self, value: Any) -> float:
        """Parse a value from a string."""
        return float(value)


class BoolParser(Parser):
    """A parser for a field in a configuration class that parses booleans."""

    _supported_types: ClassVar[set[Any]] = {bool}

    def parse(self, value: Any) -> bool:
        """Parse a value from a string."""
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "y", "t")
        elif isinstance(value, int):
            return bool(value)
        else:
            raise ValueError(f"Value is not a boolean: {value}")


class EnumParser(Parser):
    """A parser for a field in a configuration class that parses enums.

    This parser needs to be initialized with the Field so the return type
    will be the correct enum type.
    """

    _supported_types: ClassVar[set[Any]] = {Enum}

    def parse(self, value: Any) -> Enum:
        """Parse a value from a string.

        Args:
            value: The value to parse into an enum.

        Returns:
            The parsed enum value.

        Raises:
            ValueError: If the parser is not initialized with a Field or if the value
                cannot be parsed into the enum.
        """
        if self._field is None:
            raise ValueError("EnumParser must be initialized with a Field")

        enum_type = self._field.type
        if not isinstance(enum_type, type):
            raise ValueError(f"Field type {enum_type} is not a type")

        if not issubclass(enum_type, Enum):
            raise ValueError(f"Field type {enum_type} is not an Enum")

        try:
            return enum_type(value)
        except ValueError as e:
            raise ValueError(
                f"Failed to parse value '{value}' into enum {enum_type.__name__}",
            ) from e


class NestedDataclassParser(Parser):
    """A parser for a field in a configuration class that parses nested
    dataclass fields."""

    _supported_types: ClassVar[set[Any]] = set()

    def parse(self, value: Any) -> Any:
        """Parse a dataclass"""
        if not is_dataclass(value):
            raise ValueError(f"Value is not a dataclass: {value}")
        # load the dataclasses fields and parse them with the appropriate parser
        nested_fields = fields(value)
        for f in nested_fields:
            field_value = getattr(value, f.name)
            parser = get_parser_for_field(f)
            if parser is None:
                raise ValueError(f"No parser found for field {f.name}")
            setattr(value, f.name, parser.parse(field_value))
        return value

    @classmethod
    def supports_type(cls, field_type: Any) -> bool:
        """Check if this parser supports the given field type.

        Args:
            field_type: The type to check
        """
        return is_dataclass(field_type)


class NestedMappingParser(AstParserMixin, Parser):
    """A parser for a field in a configuration class that parses nested
    mapping fields."""

    _supported_types: ClassVar[set[Any]] = {dict, Mapping}

    def parse(self, value: Any) -> Mapping:
        """Parse a value from a string or recursively parse a mapping.

        For mapping types (dict, Mapping), this will recursively parse all values
        in the mapping. For non-mapping types, it attempts to convert string
        representations to dictionaries if possible.

        Args:
            value: The value to parse

        Returns:
            The parsed mapping with all nested values processed
        """
        # If value is not a mapping, try to convert it if it's a string
        if not isinstance(value, dict | Mapping):
            if isinstance(value, str):
                try:
                    parsed_value = self.literal_eval(value, (dict, Mapping))
                    if isinstance(parsed_value, dict | Mapping):
                        # If we successfully parsed it to a mapping, continue processing
                        value = parsed_value
                    else:
                        return parsed_value
                except (ValueError, SyntaxError) as e:
                    raise ValueError(f"Failed to parse mapping value: {value}") from e
            else:
                return value

        # For mapping types, recursively parse each value
        result = {}
        for k, v in value.items():
            # Recursively parse nested values
            if isinstance(v, dict | Mapping):
                result[k] = self.parse(v)
            elif isinstance(v, list | tuple | set | Sequence) and not isinstance(
                v,
                str,
            ):
                # Use NestedListParser for nested sequences
                list_parser = NestedListParser()
                result[k] = list_parser.parse(v)
            else:
                result[k] = v

        return result


class NestedListParser(AstParserMixin, Parser):
    """A parser for a field in a configuration class that parses nested
    list fields."""

    _supported_types: ClassVar[set[Any]] = {list, tuple, set, Sequence}

    def parse(self, value: Any) -> set | Sequence:
        """Parse a value from a string or recursively parse a sequence.

        For sequence types (list, tuple, etc), this will recursively parse all values
        in the sequence. For non-sequence types, it attempts to convert string
        representations to sequences if possible.

        Args:
            value: The value to parse

        Returns:
            The parsed sequence with all nested values processed
        """
        # If value is not a sequence, try to convert it if it's a string
        if not isinstance(value, list | tuple | set | Sequence) or isinstance(
            value,
            str,
        ):
            if isinstance(value, str):
                try:
                    parsed_value = self.literal_eval(value, (list, tuple, set))
                    if isinstance(parsed_value, list | tuple | set):
                        # If we parsed it to a sequence, continue processing
                        value = parsed_value
                    else:
                        return parsed_value
                except (ValueError, SyntaxError) as e:
                    raise ValueError(f"Failed to parse sequence value: {value}") from e
            else:
                return value

        # For sequence types, recursively parse each value
        result = []
        for item in value:
            # Recursively parse nested values
            if isinstance(item, list | tuple | set | Sequence) and not isinstance(
                item,
                str,
            ):
                result.append(self.parse(item))
            elif isinstance(item, dict | Mapping):
                # Use NestedMappingParser for nested dictionaries
                mapping_parser = NestedMappingParser()
                result.append(mapping_parser.parse(item))
            else:
                result.append(item)

        # Return the same type as the input if possible
        if isinstance(value, tuple):
            return tuple(result)
        elif isinstance(value, set):
            return set(result)
        return result


class PathParser(Parser):
    """A parser for a field in a configuration class that parses paths."""

    _supported_types: ClassVar[set[Any]] = {Path}

    def parse(self, value: Any) -> Path:
        """Parse a value from a string."""
        if isinstance(value, str | bytes):
            return Path(str(value))
        elif isinstance(value, Path):
            return value
        else:
            raise ValueError(f"Value is not a path: {value}")


class DatetimeParser(Parser):
    """A parser for datetime values."""

    _supported_types: ClassVar[set[Any]] = {datetime}

    def parse(self, value: Any) -> datetime:
        """Parse a datetime value from a string."""
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value


BUILT_IN_PARSERS = [
    LiteralParser,
    StrParser,
    IntParser,
    FloatParser,
    BoolParser,
    EnumParser,
    NestedMappingParser,
    NestedListParser,
    PathParser,
    DatetimeParser,
]


# TODO: You could optimize this by determining the best parser for a field and saving
# it in the field metadata when a configuration class is created.
def initialize_parsers(field: Field) -> list[Parser]:
    """Initialize the parsers for a field."""
    return [parser(field) for parser in BUILT_IN_PARSERS]


def get_parser_for_field(field: Field) -> Parser | None:
    """Get the appropriate parser for a field type from the list of
    built in parsers."""
    parsers = initialize_parsers(field)
    return next((p for p in parsers if p.is_supported), None)


def parse_field_value(field: Field, value: Any) -> Any:
    """Parse a value for a field using the field's metadata or the
    appropriate built-in parser for the field type."""
    parser = field.metadata.get("parser", get_parser_for_field(field))
    if parser is None:
        return value
    return parser.parse(value)
