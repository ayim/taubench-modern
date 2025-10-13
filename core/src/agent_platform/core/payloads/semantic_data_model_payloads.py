"""Payload types for semantic data model API endpoints."""

from dataclasses import dataclass, field
from typing import Any

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel


@dataclass(frozen=True)
class SetSemanticDataModelPayload:
    """Payload for setting a semantic data model."""

    semantic_model: SemanticDataModel | dict = field(
        metadata={"description": "The semantic data model as a dictionary."},
    )
    """The semantic data model as a dictionary."""

    @classmethod
    def model_validate(cls, data: Any) -> "SetSemanticDataModelPayload":
        """Validate and create payload from dict data."""
        return SetSemanticDataModelPayload(
            semantic_model=data.get("semantic_model", {}),
        )


@dataclass(frozen=True)
class GetSemanticDataModelPayload:
    """Payload for getting a semantic data model."""

    semantic_data_model_id: str = field(
        metadata={"description": "The ID of the semantic data model to get."},
    )
    """The ID of the semantic data model to get."""

    @classmethod
    def model_validate(cls, data: Any) -> "GetSemanticDataModelPayload":
        """Validate and create payload from dict data."""
        return GetSemanticDataModelPayload(
            semantic_data_model_id=data["semantic_data_model_id"],
        )


@dataclass(frozen=True)
class DeleteSemanticDataModelPayload:
    """Payload for deleting a semantic data model."""

    semantic_data_model_id: str = field(
        metadata={"description": "The ID of the semantic data model to delete."},
    )
    """The ID of the semantic data model to delete."""

    @classmethod
    def model_validate(cls, data: Any) -> "DeleteSemanticDataModelPayload":
        """Validate and create payload from dict data."""
        return DeleteSemanticDataModelPayload(
            semantic_data_model_id=data["semantic_data_model_id"],
        )


@dataclass(frozen=True)
class ColumnInfo:
    """Information about a column in a table."""

    name: str
    data_type: str = "unknown"
    sample_values: list[Any] | None = None
    description: str | None = None
    synonyms: list[str] | None = None


@dataclass(frozen=True)
class TableInfo:
    """Information about a table."""

    name: str
    columns: list[ColumnInfo]
    database: str | None = None
    schema: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class DataConnectionInfo:
    """Information about a data connection with its tables."""

    data_connection_id: str
    tables_info: list[TableInfo]


@dataclass(frozen=True)
class FileInfo:
    """Information about a file with its tables."""

    thread_id: str
    file_ref: str
    tables_info: list[TableInfo]
    sheet_name: str | None = None


@dataclass(frozen=True)
class GenerateSemanticDataModelPayload:
    """Payload for generating a semantic data model."""

    name: str
    description: str | None
    data_connections_info: list[DataConnectionInfo]
    files_info: list[FileInfo]
    agent_id: str | None = None


@dataclass(frozen=True)
class GenerateSemanticDataModelResponse:
    """Response for generating a semantic data model."""

    semantic_model: SemanticDataModel | dict


@dataclass(frozen=True)
class GetSemanticDataModelsPayload:
    """Payload for getting semantic data models with optional filtering."""

    agent_id: str | None = None
    thread_id: str | None = None

    @classmethod
    def model_validate(cls, data: Any) -> "GetSemanticDataModelsPayload":
        """Validate and create payload from dict data."""
        return GetSemanticDataModelsPayload(
            agent_id=data.get("agent_id"),
            thread_id=data.get("thread_id"),
        )


@dataclass(frozen=True)
class FileReference:
    """File reference information."""

    thread_id: str
    file_ref: str
    sheet_name: str | None = None


@dataclass(frozen=True)
class SemanticDataModelWithAssociations:
    """Semantic data model with its associations."""

    semantic_data_model_id: str
    semantic_data_model: SemanticDataModel | dict
    agent_ids: list[str]
    thread_ids: list[str]
    data_connection_ids: list[str]
    file_references: list[FileReference]
    errors_in_semantic_data_model: list[str]
