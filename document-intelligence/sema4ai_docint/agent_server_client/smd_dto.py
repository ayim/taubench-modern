"""Data Transfer Objects for Semantic Data Model operations.

This module contains simplified DTOs for document-intelligence, which only deals with
Postgres data connections and does not use file references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


class Sslmode:
    """SSL mode for database connections."""

    REQUIRE = "require"
    DISABLE = "disable"
    ALLOW = "allow"
    PREFER = "prefer"


@dataclass
class PostgresDataConnectionConfiguration:
    """Configuration for a Postgres database connection."""

    host: str
    port: float
    database: str
    user: str
    password: str
    schema: str = "public"
    sslmode: str | None = None


@dataclass
class PostgresDataConnection:
    """Postgres data connection payload."""

    name: str
    description: str
    configuration: PostgresDataConnectionConfiguration
    engine: Literal["postgres"] = "postgres"
    created_at: str | None = None
    updated_at: str | None = None
    id: str | None = None
    external_id: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ColumnInfo:
    """Information about a database column."""

    name: str
    data_type: str
    sample_values: list[Any] | None
    primary_key: bool | None
    unique: bool | None
    description: str | None
    synonyms: list[str] | None


@dataclass
class TableInfo:
    """Information about a database table."""

    name: str
    database: str | None
    schema: str | None
    description: str | None
    columns: list[ColumnInfo]


@dataclass
class DataConnectionsInspectResponse:
    """Response from data connection inspection."""

    tables: list[TableInfo]
    inspected_at: str | None = None  # ISO 8601 timestamp


@dataclass
class DataConnectionInfo:
    """Information about a data connection with its tables for semantic model generation.

    Note: For docint, we don't use inspect_request/inspect_response metadata.
    """

    data_connection_id: str
    tables_info: list[TableInfo]


@dataclass
class GenerateSemanticDataModelPayload:
    """Payload for generating a semantic data model.

    Note: docint only uses data connections (Postgres), no file references.
    """

    name: str
    description: str | None
    data_connections_info: list[DataConnectionInfo]
    agent_id: str | None = None


class GenerateSemanticDataModelResponse(TypedDict):
    """Response from generating a semantic data model."""

    semantic_model: dict[str, Any]  # This is a SemanticDataModel dict


class SetSemanticDataModelPayload(TypedDict):
    """Payload for saving/creating a semantic data model."""

    semantic_model: dict[str, Any]  # This is a SemanticDataModel dict


class SaveSemanticDataModelResponse(TypedDict):
    """Response from saving a semantic data model.

    Note: Simplified for docint - no file_references since we don't use files.
    """

    semantic_data_model_id: str
    data_connection_ids: list[str]
