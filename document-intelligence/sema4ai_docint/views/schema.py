"""
Dataclasses for the business schema structure.
"""

from dataclasses import dataclass, field
from typing import Any

from .type_system import StandardTypes


@dataclass
class DataFormat:
    """
    Represents a data format with type and optional attributes.

    Attributes:
        type: The abstract data type (e.g., "string", "number")
        attributes: Type-specific attributes (e.g., length, precision, scale)
    """

    type: str
    attributes: dict[str, Any] | None = None

    def __post_init__(self):
        """Validate the format after initialization."""
        if not self.type:
            raise ValueError("Type is required")

        # Convert to lowercase for case-insensitive comparison
        type_lower = self.type.lower()

        # Validate using the StandardTypes enum
        if type_lower not in [t.value for t in StandardTypes]:
            valid_types = [t.value for t in StandardTypes]
            raise ValueError(f"Invalid type: {self.type}. Must be one of: {', '.join(valid_types)}")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "DataFormat":
        """
        Create a DataFormat from a dictionary with 'type' and optional 'attributes',
        or directly from a string representing the type.

        Args:
            data: Dictionary with type and attributes, or a string representing just the type

        Returns:
            A DataFormat instance
        """
        if isinstance(data, str):
            # If just a string is provided, assume it's the type with no attributes
            return cls(type=data)

        type_value = data.get("type")
        attributes = data.get("attributes")

        return cls(type=type_value, attributes=attributes)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the DataFormat to a dictionary.

        Returns:
            A dictionary with type and attributes (if present)
        """
        result = {"type": self.type}
        if self.attributes:
            result["attributes"] = self.attributes
        return result


@dataclass
class SchemaField:
    """
    Represents a single field in the business schema.

    Attributes:
        path: The JSON path to the data (e.g., "customer.name" or "orders[].id")
        name: The column name to use in the view (e.g., "CUSTOMER_NAME")
        format: The data format specification (type and optional attributes)
    """

    path: str
    name: str
    format: DataFormat

    def __post_init__(self):
        """Validate the field after initialization."""
        if not self.path:
            raise ValueError("Path is required")
        if not self.name:
            raise ValueError("Name is required")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SchemaField":
        """
        Create a SchemaField from a dictionary.

        Args:
            data: Dictionary with path, name, and format information

        Returns:
            A SchemaField instance
        """
        path = data.get("path")
        name = data.get("name")

        if "format" not in data:
            raise ValueError("Format is required")

        format_data = data["format"]
        if isinstance(format_data, str) or isinstance(format_data, dict):
            format_data = DataFormat.from_dict(format_data)
        elif not isinstance(format_data, DataFormat):
            raise ValueError(f"Invalid format: {format_data}")

        return cls(path=path, name=name, format=format_data)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the SchemaField to a dictionary.

        Returns:
            A dictionary representing the schema field
        """
        return {"path": self.path, "name": self.name, "format": self.format.to_dict()}


@dataclass
class BusinessSchema:
    """
    Represents a complete business schema with multiple fields.

    Attributes:
        fields: List of schema fields
    """

    fields: list[SchemaField] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> "BusinessSchema":
        """
        Create a BusinessSchema from a list of dictionaries.

        Args:
            data: List of dictionaries representing schema fields

        Returns:
            A BusinessSchema instance
        """
        schema = cls()
        for field_data in data:
            schema.fields.append(SchemaField.from_dict(field_data))
        return schema

    def to_dict(self) -> list[dict[str, Any]]:
        """
        Convert the BusinessSchema to a list of dictionaries.

        Returns:
            A list of dictionaries representing schema fields
        """
        return [field.to_dict() for field in self.fields]
