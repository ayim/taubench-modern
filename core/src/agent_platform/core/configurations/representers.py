"""Yaml representers for configuration classes."""

from abc import ABC, abstractmethod
from dataclasses import Field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    get_origin,
)

import structlog

if TYPE_CHECKING:
    import yaml

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class Representer(ABC):
    """A YAML representer for a field in a configuration class.

    These are only needed for certain field types as YAML can natively
    represent many Python types.
    """

    _supported_types: ClassVar[set[type]]
    """The types that the representer supports."""
    _represent_subtypes: ClassVar[bool] = True
    """Whether the representer supports subtypes. If yes, the representer will
    be used for all subtypes of the supported types."""

    @classmethod
    @abstractmethod
    def represent(cls, dumper: "yaml.Dumper", value: Any) -> "yaml.Node":
        """Represent a value as a string."""
        ...

    @classmethod
    def register_representer(cls) -> None:
        """Register the representer with the YAML module."""
        import yaml

        for supported_type in cls._supported_types:
            if cls._represent_subtypes:
                yaml.add_multi_representer(supported_type, cls.represent)
            else:
                yaml.add_representer(supported_type, cls.represent)

    @classmethod
    def supports_type(cls, field_type: Any) -> bool:
        """Check if this representer supports the given field type.

        Args:
            field_type: The type to check

        Returns:
            True if this representer supports the type, False otherwise
        """
        # Handle actual classes
        if isinstance(field_type, type):
            for supported_type in cls._supported_types:
                if cls._represent_subtypes and issubclass(field_type, supported_type):
                    return True
                if not cls._represent_subtypes and field_type == supported_type:
                    return True
            return False

        # Handle type annotations (like Literal, Union, etc.)
        try:
            # Get the origin type (e.g., Literal, Union, etc.)
            origin = get_origin(field_type)

            # If it's a special type annotation, check if we support its origin
            if origin is not None:
                # For type origins, we need to check by name or identity, not using
                # issubclass
                for supported_type in cls._supported_types:
                    # Check if the origin is the same as a supported type
                    if origin == supported_type:
                        return True

                    # For special handling of Literal types
                    if origin.__name__ == "Literal" and Literal in cls._supported_types:
                        return True

        except (ImportError, AttributeError):
            # If typing helpers aren't available, fall back to basic check
            pass

        return False


class PathRepresenter(Representer):
    """A representer for a field in a configuration class that represents
    Path objects as strings."""

    _supported_types: ClassVar[set[type]] = {Path}
    _represent_subtypes: ClassVar[bool] = True

    @classmethod
    def represent(cls, dumper: "yaml.Dumper", value: Path) -> "yaml.Node":
        """Represent a Path object as a string."""
        return dumper.represent_scalar("tag:yaml.org,2002:str", str(value))


class EnumRepresenter(Representer):
    """A representer for a field in a configuration class that represents
    Enum objects as strings using the Enum's attribute value."""

    _supported_types: ClassVar[set[type]] = {Enum}
    _represent_subtypes: ClassVar[bool] = True

    @classmethod
    def represent(cls, dumper: "yaml.Dumper", value: Enum) -> "yaml.Node":
        """Represent an Enum object as a string using the Enum's attribute value."""
        return dumper.represent_scalar("tag:yaml.org,2002:str", value.value)


class DatetimeRepresenter(Representer):
    """A representer for datetime values."""

    _supported_types: ClassVar[set[type]] = {datetime}

    @classmethod
    def represent(cls, dumper: "yaml.Dumper", value: datetime) -> "yaml.ScalarNode":
        """Represent a datetime value as ISO format string."""
        return dumper.represent_scalar("tag:yaml.org,2002:str", value.isoformat())


BUILT_IN_REPRESENTERS: tuple[type[Representer], ...] = (
    PathRepresenter,
    EnumRepresenter,
    DatetimeRepresenter,
)


def get_representer_for_field(field: Field) -> type[Representer] | None:
    """Get the appropriate representer for a field type from the list of
    built in representers.

    If the field has a representer metadata, it will be used.
    Otherwise, the best built in representer will be used.

    Returns:
        The representer for the field or None if no representer is found, in
        which case the field will be reprsesented by the YAML default
        representer.
    """
    representer = None
    if field.metadata.get("representer"):
        representer = field.metadata["representer"]
        if not issubclass(representer, Representer):
            raise ValueError(f"Invalid representer type {representer}")
    else:
        representer = next(
            (r for r in BUILT_IN_REPRESENTERS if r.supports_type(field.type)),
            None,
        )

    return representer


def represent_field_value(
    field: Field,
    dumper: "yaml.Dumper",
    value: Any,
) -> "yaml.Node | None":
    """Represent a value for a field using the field's metadata or the
    appropriate built-in representer for the field type.

    Returns:
        The YAML node for the field value or None if no representer is found,
        in which case the field will be represented by the YAML default
        representer.
    """
    representer = get_representer_for_field(field)
    if representer is None:
        return None
    return representer.represent(dumper, value)
