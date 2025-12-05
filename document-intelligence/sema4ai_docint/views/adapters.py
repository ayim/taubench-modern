"""
Database adapters for generating SQL views for different database systems.
"""

from abc import ABC, abstractmethod
from typing import Any

from .type_system import StandardTypes


class DBAdapter(ABC):
    """
    Abstract base class for database adapters.
    Each adapter handles database-specific SQL generation and type casting.
    """

    @abstractmethod
    def build_json_path(self, component: str, is_last: bool, current_path: str) -> str:
        """
        Build a JSON path expression for the given component.

        Args:
            component: The component name
            is_last: Whether this is the last component in the path
            current_path: The current path expression

        Returns:
            A database-specific JSON path expression
        """
        pass

    @abstractmethod
    def build_array_accessor(self, current_path: str, component: str) -> str:
        """
        Build an array accessor expression.

        Args:
            current_path: The current path expression
            component: The array component name

        Returns:
            A database-specific array accessor expression
        """
        pass

    @abstractmethod
    def apply_type_cast(
        self,
        json_path: str,
        field_type: str,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        """
        Apply type casting to a JSON path expression.

        Args:
            json_path: The JSON path expression
            field_type: The abstract field type (string, number, integer, boolean, date, datetime)
            attributes: Optional type attributes (precision, scale, etc.)

        Returns:
            A database-specific type-cast expression
        """
        pass

    # TODO: Fix lint issues in this function
    def parse_type(  # noqa: PLR0911
        self, field_type: str, attributes: dict[str, Any] | None = None
    ) -> tuple[StandardTypes, str]:
        """
        Parse a field type from the abstract type system into a database-specific type.
        BusinessSchema dataclass validation handles any unsupported field type upstream.

        Args:
            field_type: The field type from the abstract type system
                (already validated by DataFormat)
            attributes: Additional type attributes

        Returns:
            A database-specific type string
        """
        # Convert to lowercase for case-insensitive comparison
        field_type_lower = field_type.lower()

        if field_type_lower == StandardTypes.STRING:
            if attributes and "length" in attributes:
                length = attributes["length"]
                return StandardTypes.STRING, f"VARCHAR({length})"
            return StandardTypes.STRING, "VARCHAR"

        elif field_type_lower == StandardTypes.NUMBER:
            if attributes and "precision" in attributes and "scale" in attributes:
                precision = attributes["precision"]
                scale = attributes["scale"]
                return StandardTypes.NUMBER, f"DECIMAL({precision},{scale})"
            elif attributes and "precision" in attributes:
                precision = attributes["precision"]
                return StandardTypes.NUMBER, f"DECIMAL({precision})"
            return StandardTypes.NUMBER, "DECIMAL"

        elif field_type_lower == StandardTypes.INTEGER:
            return StandardTypes.INTEGER, "INT"

        elif field_type_lower == StandardTypes.BOOLEAN:
            return StandardTypes.BOOLEAN, "BOOLEAN"

        elif field_type_lower == StandardTypes.DATE:
            return StandardTypes.DATE, "DATE"

        elif field_type_lower == StandardTypes.DATETIME:
            return StandardTypes.DATETIME, "TIMESTAMP"

        raise ValueError(f"Unsupported field type: {field_type}")


class PostgresAdapter(DBAdapter):
    """
    Adapter for PostgreSQL database.
    """

    def build_json_path(self, component: str, is_last: bool, current_path: str) -> str:
        """
        Build a PostgreSQL JSON path expression.
        Uses -> for object access and ->> for text extraction (last component).
        """
        if is_last:
            return f"{current_path}->>'{component}'"
        else:
            return f"{current_path}->'{component}'"

    def build_array_accessor(self, current_path: str, component: str) -> str:
        """
        Build a PostgreSQL array accessor expression.
        """
        return f"{current_path}->'{component}'"

    def apply_type_cast(
        self,
        json_path: str,
        field_type: str,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        """
        Apply PostgreSQL type casting to a JSON path expression.
        Numbers are coerced using a custom function that returns NULL for values that
        cannot be coerced to numbers.
        """
        db_type, db_type_str = self.parse_type(field_type, attributes)

        if db_type in {StandardTypes.NUMBER, StandardTypes.INTEGER}:
            return f"TRY_TO_NUMBER({json_path})"
        else:
            return f"CAST({json_path} AS {db_type_str})"
