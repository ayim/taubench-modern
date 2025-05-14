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
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    get_args,
    get_origin,
)

import structlog

from agent_platform.core.configurations.errors import ConfigurationDiscriminatorError
from agent_platform.core.configurations.utils import (
    is_union_of_dataclasses_type,
)

if TYPE_CHECKING:
    from agent_platform.core.configurations.base import Configuration

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
    _allow_subclasses: ClassVar[bool] = False
    """If True, the parser will allow subclasses of the supported types to be
    supported.
    """

    def __init__(
        self,
        field: Field | None = None,
        parent_config: "type[Configuration] | Configuration | None" = None,
        config_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the parser with an optional field.

        When a field is provided, the parser checks if it supports the field's type
        using the `supports_type` method. This result is stored and can be accessed
        via the `is_supported` property.

        When no field is provided, the `is_supported` property will always return True.
        This is useful when you want to use the parser directly without checking type
        support, such as when you've already verified the type compatibility.

        Args:
            field: Optional field to check for type compatibility or provide additional
                context for the parser. Some parsers may require this to parse
                values correctly, in which case the parser may fail at runtime if
                the field is not provided.
            parent_config: The parent configuration the field belongs to. This provides
                context for the parser, which may be required for some parsers to
                parse values correctly. If not provided, the parser will not have
                any context and may fail at runtime if it requires parent config
                information. This class may be partially or not initialized, so
                be careful when accessing properties. It is recommended to use
                the `config_data` parameter to provide the full unparsed config
                data to the parser if required.
            config_data: The data from the configuration file. This provides
                context for the parser, which may be required for some parsers to
                parse values correctly. If not provided, the parser will not have
                any context and may fail at runtime if it requires config data.
                This is useful when you may need to access raw unparsed config data
                to parse a specific value (e.g., a nested dataclass).
        """
        self._field = field
        self._parent_config = parent_config
        self._supports_field = self.supports_type(field.type) if field else True
        self._config_data = config_data

    @property
    def is_supported(self) -> bool:
        """Check if the parser supports the field type."""
        return self._supports_field

    @property
    def parent_config(self) -> "type[Configuration] | Configuration | None":
        """Get the parent configuration."""
        return self._parent_config

    @property
    def field(self) -> Field | None:
        """Get the field."""
        return self._field

    @property
    def config_data(self) -> dict[str, Any] | None:
        """Get the config data."""
        return self._config_data

    @abstractmethod
    def parse(self, value: Any) -> Any:
        """Parse a value.

        Note: Input values of None will always be returned as None to ensure
        field defaults are honored.

        Args:
            value: The value to parse

        Returns:
            The parsed value
        """
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

        # Check if the field_type is a subclass of any of the supported types
        try:
            if cls._allow_subclasses and issubclass(
                field_type, tuple(cls._supported_types)
            ):
                return True
        except TypeError:
            pass

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


class FieldRequiredMixin(Parser):
    """A mixin for parsers that require a field to be initialized."""

    @property
    def field(self) -> Field:
        """Get the field."""
        if self._field is None:
            raise ValueError(
                f"{self.__class__.__name__} must be initialized with a Field"
            )
        return self._field


class ParentConfigRequiredMixin(Parser):
    """A mixin for parsers that require a parent config to be initialized."""

    @property
    def parent_config(self) -> "type[Configuration] | Configuration":
        """Get the parent config."""
        if self._parent_config is None:
            raise ValueError(
                f"{self.__class__.__name__} must be initialized with a parent config"
            )
        return self._parent_config


class LiteralParser(AstParserMixin, Parser):
    """A parser for Literal types that validates values against allowed options."""

    # Support Literal as a generic type
    _supported_types: ClassVar[set[Any]] = {Literal}
    """This parser supports the `Literal` generic type. It will match any field type
    that is a `Literal` type, such as `Literal[str, int]` or `Literal[True, False]`.

    The parser will validate that the value matches one of the allowed options
    specified in the Literal type.
    """

    def parse(self, value: Any) -> Any:
        """Parse a value and ensure it's one of the allowed literal values.

        Args:
            value: The string value to parse

        Returns:
            The validated value

        Raises:
            ValueError: If the value doesn't match any of the allowed options
        """
        field_type = self.field.type if self.field else None
        if value is None or field_type is None:
            return value

        literal_args = get_args(field_type)
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

    def parse(self, value: Any) -> str | None:
        """Parse a value from a string."""
        if value is None:
            return None
        return str(value)


class IntParser(Parser):
    """A parser for a field in a configuration class that parses integers."""

    _supported_types: ClassVar[set[Any]] = {int}

    def parse(self, value: Any) -> int | None:
        """Parse a value from a string."""
        if value is None:
            return None
        return int(value)


class FloatParser(Parser):
    """A parser for a field in a configuration class that parses floats."""

    _supported_types: ClassVar[set[Any]] = {float}

    def parse(self, value: Any) -> float | None:
        """Parse a value from a string."""
        if value is None:
            return None
        return float(value)


class BoolParser(Parser):
    """A parser for a field in a configuration class that parses booleans."""

    _supported_types: ClassVar[set[Any]] = {bool}

    def parse(self, value: Any) -> bool | None:
        """Parse a value from a string."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "y", "t")
        elif isinstance(value, int):
            return bool(value)
        else:
            raise ValueError(f"Value is not a boolean: {value}")


class EnumParser(FieldRequiredMixin, Parser):
    """A parser for a field in a configuration class that parses enums.

    This parser needs to be initialized with the Field so the return type
    will be the correct enum type.
    """

    _supported_types: ClassVar[set[Any]] = {Enum}
    _allow_subclasses: ClassVar[bool] = True

    def parse(self, value: Any) -> Enum | None:
        """Parse a value from a string.

        Args:
            value: The value to parse into an enum.

        Returns:
            The parsed enum value.

        Raises:
            ValueError: If the parser is not initialized with a Field or if the value
                cannot be parsed into the enum.
        """
        if value is None:
            return value

        enum_type = self.field.type
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


class NestedDataclassParser(AstParserMixin, FieldRequiredMixin, Parser):
    """A parser for a field in a configuration class that parses nested
    dataclass types. This parser requires a field to be initialized or the
    parse method will raise a ValueError.
    """

    _supported_types: ClassVar[set[Any]] = set()

    def parse(self, value: Any) -> Any:
        """Parse a value into a dataclass. If the value is a string, it will be
        parsed using ast.literal_eval before being parsed into the dataclass.

        Args:
            value: The value to parse

        Returns:
            The parsed dataclass.

        Raises:
            ValueError: If the value is not a dataclass type or if the value
                does not match any of the configured discriminators.
        """
        if value is None:
            return value
        if not is_dataclass(self.field.type):
            raise ValueError(f"Field type {self.field.type} is not a dataclass type")
        if isinstance(value, str):
            value = self.literal_eval(value, (dict,))
        if not isinstance(value, dict):
            raise ValueError(
                f"Field value must be a dictionary for "
                f"Nested Dataclasses. Field: {self.field.name}"
            )
        for f in fields(self.field.type):
            if not f.init:
                value.pop(f.name, None)
            elif f.name in value:
                value[f.name] = parse_field_value(f, value[f.name], self.parent_config)

        # Ensure we're working with a class, not an instance
        dataclass_type = self.field.type
        if not isinstance(dataclass_type, type):
            dataclass_type = type(dataclass_type)

        return dataclass_type(**value)

    @classmethod
    def supports_type(cls, field_type: Any) -> bool:
        """Check if this parser supports the given field type.

        Args:
            field_type: The type to check
        """
        return is_dataclass(field_type)


class UnionOfDataclassParser(
    AstParserMixin, FieldRequiredMixin, ParentConfigRequiredMixin, Parser
):
    """A parser for a field in a configuration class that parses a Union of
    dataclass types. This parser requires a field and parent config to be
    initialized or the parse method will raise a ValueError.

    This parser will parse a value into the appropriate dataclass based on the
    discriminators configured in the Union of dataclasses type.

    Note: This parser does not support unions of dataclasses that are themselves
    nested in dataclasses or other types
    """

    _supported_types: ClassVar[set[Any]] = set()

    def _validate_discriminator_field(self) -> None:
        """Validate the discriminator field."""
        if not is_union_of_dataclasses_type(self.field.type):
            raise ValueError(
                f"Field type {self.field.type} is not a Union of dataclasses type",
            )
        if (
            "discriminator_mapping" not in self.field.metadata
            or "discriminator" not in self.field.metadata
        ):
            raise ConfigurationDiscriminatorError(
                f"Discriminator mapping and discriminator field name are required for "
                f"Unions of Dataclasses. Field: {self.field.name}"
            )
        discriminator_field = self.field.metadata["discriminator"]
        if not isinstance(discriminator_field, str):
            raise ConfigurationDiscriminatorError(
                f"Discriminator field name must be a string for "
                f"Unions of Dataclasses. Field: {self.field.name}"
            )

    def get_target_class(self) -> Any:
        """Get the target class for the Union of dataclasses type based on
        the discriminator value.

        Returns:
            The target class for the Union of dataclasses type.
        """
        self._validate_discriminator_field()
        # Get the discriminator field name from the metadata
        discriminator_field = self.field.metadata["discriminator"]
        if not isinstance(discriminator_field, str):
            raise ConfigurationDiscriminatorError(
                f"Discriminator field name must be a string for "
                f"Unions of Dataclasses. Field: {self.field.name}"
            )

        # Get the discriminator value from the parent config or config data. Config data
        # takes precedence over the parent config if both are provided.
        discriminator_value = None
        if self.config_data is not None:
            discriminator_value = self.config_data.get(discriminator_field)
        else:
            for parent_field in fields(self.parent_config):
                if parent_field.name == discriminator_field:
                    # Because of the ConfigMeta metaclass, the parent config is a
                    # singleton instance of the configuration class, so we can access
                    # the field directly and get the value even though we may be in the
                    # middle of parsing the config as long as we are not parsing for the
                    # first time.
                    discriminator_value = getattr(self.parent_config, parent_field.name)
                break
            else:
                raise ConfigurationDiscriminatorError(
                    f"Discriminator field {discriminator_field} not found "
                    f"in parent config"
                )
        if discriminator_value is None:
            raise ConfigurationDiscriminatorError(
                f"Discriminator value must be loaded before the Union type "
                f"can be parsed. Discriminator field: {discriminator_field} "
                f"Field: {self.field.name}"
            )

        # Get the discriminator mapping from the metadata
        discriminator_mapping = self.field.metadata["discriminator_mapping"]
        if not isinstance(discriminator_mapping, dict):
            raise ConfigurationDiscriminatorError(
                f"Discriminator mapping must be a dictionary for "
                f"Unions of Dataclasses. Field: {self.field.name}"
            )

        # Get the class for this discriminator value
        target_class = discriminator_mapping.get(discriminator_value)
        if target_class is None and isinstance(discriminator_value, Enum):
            # Try getting the class using the enum value
            target_class = discriminator_mapping.get(discriminator_value.value)
        if target_class is None:
            raise ConfigurationDiscriminatorError(
                f"No class found for discriminator value '{discriminator_value}' "
                f"in field {self.field.name}"
            )
        if isinstance(target_class, type) and not is_dataclass(target_class):
            raise ConfigurationDiscriminatorError(
                f"Target class {target_class.__name__} is not a dataclass"
            )
        return target_class

    def parse(self, value: Any) -> Any:
        """Parse a value into the appropriate dataclass based on the
        discriminators configured in the Union of dataclasses type. If the value
        is a string, it will be parsed using ast.literal_eval before being parsed
        into the dataclass.

        Args:
            value: The value to parse

        Returns:
            The parsed dataclass.

        Raises:
            ValueError: If the value is not a Union of dataclasses type or if the
                value does not match any of the configured discriminators.
        """
        if value is None:
            return None
        self._validate_discriminator_field()
        # Check input
        if isinstance(value, str):
            value = self.literal_eval(value, (dict,))
        if not isinstance(value, dict):
            raise ConfigurationDiscriminatorError(
                f"Field value must be a dictionary for "
                f"Unions of Dataclasses. Field: {self.field.name}"
            )

        # Create an instance of the target class, which is a dataclass
        target_class = self.get_target_class()
        try:
            for f in fields(target_class):
                if not f.init:
                    value.pop(f.name, None)
                elif f.name in value:
                    value[f.name] = parse_field_value(
                        f, value[f.name], self.parent_config
                    )
            return target_class(**value)
        except Exception as e:
            raise ConfigurationDiscriminatorError(
                f"Failed to create instance of {target_class.__name__} "
                f"for field {self.field.name}: {e}"
            ) from e

    @classmethod
    def supports_type(cls, field_type: Any) -> bool:
        """Check if this parser supports the given field type.

        Args:
            field_type: The type to check
        """
        return is_union_of_dataclasses_type(field_type)


class NestedMappingParser(AstParserMixin, Parser):
    """A parser for a field in a configuration class that parses nested
    mapping fields."""

    _supported_types: ClassVar[set[Any]] = {dict, Mapping}

    def parse(self, value: Any) -> Mapping | None:
        """Parse a value from a string or recursively parse a mapping.

        For mapping types (dict, Mapping), this will recursively parse all values
        in the mapping. For non-mapping types, it attempts to convert string
        representations to dictionaries if possible.

        Args:
            value: The value to parse

        Returns:
            The parsed mapping with all nested values processed
        """
        if value is None:
            return None
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

    def parse(self, value: Any) -> set | Sequence | None:
        """Parse a value from a string or recursively parse a sequence.

        For sequence types (list, tuple, etc), this will recursively parse all values
        in the sequence. For non-sequence types, it attempts to convert string
        representations to sequences if possible.

        Args:
            value: The value to parse

        Returns:
            The parsed sequence with all nested values processed
        """
        if value is None:
            return None
        # If value is not a sequence, try to convert it if it's a string
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

    def parse(self, value: Any) -> Path | None:
        """Parse a value as a path."""
        if value is None:
            return None
        if isinstance(value, str | bytes):
            return Path(str(value))
        elif isinstance(value, Path):
            return value
        else:
            raise ValueError(f"Value is not a path: {value}")


class DatetimeParser(Parser):
    """A parser for datetime values."""

    _supported_types: ClassVar[set[Any]] = {datetime}

    def parse(self, value: Any) -> datetime | None:
        """Parse a value as a datetime."""
        if value is None:
            return None
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
    NestedDataclassParser,
    UnionOfDataclassParser,
]


# TODO: You could optimize this by determining the best parser for a field and saving
# it in the field metadata when a configuration class is created.
def initialize_parsers(
    field: Field,
    parent_config: "type[Configuration] | Configuration | None" = None,
    config_data: dict[str, Any] | None = None,
) -> list[Parser]:
    """Initialize the parsers for a field."""
    return [parser(field, parent_config, config_data) for parser in BUILT_IN_PARSERS]


def get_parser_for_field(
    field: Field,
    parent_config: "type[Configuration] | Configuration | None" = None,
    config_data: dict[str, Any] | None = None,
) -> Parser | None:
    """Get the appropriate parser for a field type from the list of
    built in parsers."""
    parsers = initialize_parsers(field, parent_config, config_data)
    return next((p for p in parsers if p.is_supported), None)


def parse_field_value(
    field: Field,
    value: Any,
    parent_config: "type[Configuration] | Configuration | None" = None,
    config_data: dict[str, Any] | None = None,
) -> Any:
    """Parse a value for a field using the field's metadata or the
    appropriate built-in parser for the field type.

    Note: An input value of None will always be returned as None to ensure
    field defaults are honored."""
    if value is None:
        return None
    parser = field.metadata.get(
        "parser", get_parser_for_field(field, parent_config, config_data)
    )
    if parser is None:
        return value
    if isinstance(parser, type) and issubclass(parser, Parser):
        parser = parser(field, parent_config, config_data)
    return parser.parse(value)
