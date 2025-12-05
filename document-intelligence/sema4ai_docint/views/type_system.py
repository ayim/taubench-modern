"""
Abstract type system for database-agnostic type definitions.
"""

from enum import StrEnum


class StandardTypes(StrEnum):
    """
    Standard abstract data types used across all database adapters.
    These types are mapped to specific database types by each database adapter.
    """

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
