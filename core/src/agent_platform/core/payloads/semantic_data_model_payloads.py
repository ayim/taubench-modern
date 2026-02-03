"""Payload types for semantic data model API endpoints."""

from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.payloads.data_connection import (
    DataConnectionsInspectRequest,
    DataConnectionsInspectResponse,
)
from agent_platform.core.semantic_data_model.types import (
    SemanticDataModel,
    ValidationMessage,
    VerifiedQuery,
)


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


class ColumnInfo(BaseModel):
    """Information about a column in a table."""

    model_config = ConfigDict(extra="ignore")

    name: str
    data_type: str = "unknown"
    sample_values: list[Any] | None = None
    description: str | None = None
    synonyms: list[str] | None = None


class TableInfo(BaseModel):
    """Information about a table."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str
    columns: list[ColumnInfo] = Field(..., min_length=1)
    database: str | None = None
    schema_: str | None = Field(default=None, alias="schema")
    description: str | None = None


class DataConnectionInfo(BaseModel):
    """Information about a data connection with its tables.

    Optionally includes the original inspection request/response for metadata tracking.
    """

    model_config = ConfigDict(extra="ignore")

    data_connection_id: str
    tables_info: list[TableInfo]
    inspect_request: DataConnectionsInspectRequest | None = None
    inspect_response: DataConnectionsInspectResponse | None = None


class FileInfo(BaseModel):
    """Information about a file with its tables.

    Optionally includes the original inspection response for metadata tracking.
    """

    model_config = ConfigDict(extra="ignore")

    thread_id: str
    file_ref: str
    tables_info: list[TableInfo]
    sheet_name: str | None = None
    inspect_response: DataConnectionsInspectResponse | None = None


class GenerateSemanticDataModelPayload(BaseModel):
    """Payload for generating a semantic data model."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str | None
    data_connections_info: list[DataConnectionInfo]
    files_info: list[FileInfo]
    agent_id: str | None = None
    existing_semantic_data_model: SemanticDataModel | dict | None | str = Field(
        default=None,
        description=(
            "The existing semantic data model to enhance. Can be provided as a dict/object "
            "or just its id. If not provided, a new semantic data model will be generated "
            "based on the data_connections_info and files_info."
        ),
    )


class GenerateSemanticDataModelResponse(BaseModel):
    """Response for generating a semantic data model."""

    model_config = ConfigDict(extra="ignore")

    semantic_model: SemanticDataModel


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
class EmptyFileReference:
    """Empty file reference information. This is used when the semantic data model
    has an empty file reference (thread_id and file_ref are empty).
    This means that the semantic data model must match a file automatically
    after it's added to a thread (and cannot be used until that reference is satisfied)."""

    logical_table_name: str
    sheet_name: str | None
    base_table_table: str


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
    empty_file_references: list[EmptyFileReference]


@dataclass(frozen=True)
class ImportSemanticDataModelPayload:
    """Payload for importing a semantic data model.

    The semantic_model should contain data_connection_name instead of data_connection_id.
    These names will be resolved to IDs in the target environment.

    If agent_id is provided, deduplication will check for existing SDMs linked to that agent.
    If a matching SDM is found (same name and content), it will be reused instead of creating
    a duplicate.
    """

    semantic_model: SemanticDataModel | dict | str = field(
        metadata={"description": ("The semantic data model with data_connection_name (can be dict or YAML string).")},
    )
    """The semantic data model with data_connection_name instead of data_connection_id.
    Can be provided as a dict/object or as a YAML string."""

    agent_id: str | None = field(
        default=None,
        metadata={"description": "Optional agent ID for deduplication check."},
    )
    """If provided, checks for duplicate SDMs linked to this agent before creating new."""

    thread_id: str | None = field(
        default=None,
        metadata={"description": "Optional thread ID for file reference resolution."},
    )
    """If provided, enables resolution of file references during import."""

    @classmethod
    def model_validate(cls, data: Any) -> "ImportSemanticDataModelPayload":
        """Validate and create payload from dict data.

        If semantic_model is provided as a string, it will be parsed as YAML.
        """
        import yaml

        semantic_model_data = data.get("semantic_model", {})

        # Parse YAML string if provided
        if isinstance(semantic_model_data, str):
            try:
                semantic_model_data = yaml.safe_load(semantic_model_data)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in semantic_model: {e}") from e

        return ImportSemanticDataModelPayload(
            semantic_model=semantic_model_data,
            agent_id=data.get("agent_id"),
            thread_id=data.get("thread_id"),
        )


@dataclass(frozen=True)
class ImportSemanticDataModel:
    """Response for importing a semantic data model."""

    semantic_data_model_id: str
    """The ID of the created or reused semantic data model."""

    resolved_data_connections: dict[str, str]
    """Mapping of data_connection_name to data_connection_id that were resolved."""

    is_duplicate: bool = False
    """True if an existing SDM was reused (duplicate found), False if new SDM was created."""

    warnings: list[str] = field(default_factory=list)
    """Any warnings encountered during import."""


@dataclass(frozen=True)
class ValidateSemanticDataModelPayload:
    """Payload for validating a semantic data model.

    **Selector fields** (exactly one required):
    - `semantic_data_model`, `semantic_data_model_id`, `agent_id`, OR `thread_id` alone

    **Context field** (optional):
    - `thread_id` can be provided alongside selectors for file reference resolution

    Supported validation modes:

    1. **Validate a specific inline SDM**:
       - Provide `semantic_data_model` (dict)
       - Optionally add `thread_id` for file resolution
       - Without `thread_id`: file references will be warnings

    2. **Validate a specific stored SDM by ID**:
       - Provide `semantic_data_model_id`
       - Optionally add `thread_id` for file resolution
       - Without `thread_id`: file references will be warnings

    3. **Validate all SDMs for an agent**:
       - Provide `agent_id`
       - Optionally add `thread_id` for file resolution
       - Without `thread_id`: file references will be warnings
       - If `thread_id` is provided, it must belong to the agent

    4. **Validate all SDMs for a thread**:
       - Provide `thread_id` alone
       - Validates all SDMs stored in the thread
       - File references can be resolved using the thread context
       - Note: Does NOT validate agent SDMs, only thread SDMs

    Examples:
        # Validate inline SDM (no file resolution)
        ValidateSemanticDataModelPayload(semantic_data_model={...})

        # Validate inline SDM with file resolution
        ValidateSemanticDataModelPayload(semantic_data_model={...}, thread_id="thread_456")

        # Validate stored SDM by ID with file resolution
        ValidateSemanticDataModelPayload(semantic_data_model_id="sdm_123", thread_id="thread_456")

        # Validate all agent SDMs with file resolution
        ValidateSemanticDataModelPayload(agent_id="agent_123", thread_id="thread_456")

        # Validate all thread SDMs (with file resolution)
        ValidateSemanticDataModelPayload(thread_id="thread_456")
    """

    semantic_data_model: Annotated[
        SemanticDataModel | dict | None,
        "The semantic data model to validate (selector). Can be combined with thread_id.",
    ] = None

    semantic_data_model_id: Annotated[
        str | None,
        "The ID of the semantic data model to validate (selector). Can be combined with thread_id.",
    ] = None

    agent_id: Annotated[
        str | None,
        "The ID of the agent whose SDMs should be validated (selector). "
        "Can be combined with thread_id (thread must belong to the agent).",
    ] = None

    thread_id: Annotated[
        str | None,
        "The ID of the thread for file resolution context OR as the sole selector to validate all thread SDMs.",
    ] = None

    @classmethod
    def model_validate(cls, data: Any) -> "ValidateSemanticDataModelPayload":
        """Validate and create payload from dict data."""
        return ValidateSemanticDataModelPayload(
            semantic_data_model=data.get("semantic_data_model"),
            semantic_data_model_id=data.get("semantic_data_model_id"),
            agent_id=data.get("agent_id"),
            thread_id=data.get("thread_id"),
        )

    def __post_init__(self) -> None:
        """Validate payload options and raise BAD_REQUEST if invalid."""
        # Validate we have at least one option provided
        if not any([self.semantic_data_model, self.semantic_data_model_id, self.agent_id, self.thread_id]):
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="At least one of semantic_data_model, semantic_data_model_id, "
                "agent_id, or thread_id must be provided",
            )

        # Count selectors (excluding thread_id which can be a context parameter)
        selectors = [
            self.semantic_data_model,
            self.semantic_data_model_id,
            self.agent_id,
        ]
        num_selectors = sum(1 for x in selectors if x is not None)

        # Must have exactly one selector, OR just thread_id alone
        if num_selectors > 1:
            options = [
                f"{opt}: {str(x)[:50]}"
                for opt, x in [
                    ("semantic_data_model", self.semantic_data_model),
                    ("semantic_data_model_id", self.semantic_data_model_id),
                    ("agent_id", self.agent_id),
                ]
                if x is not None
            ]
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="Only one of semantic_data_model, semantic_data_model_id, or "
                "agent_id can be provided as the selector, got: " + ", ".join(options),
            )


@dataclass(frozen=True)
class ValidateSemanticDataModelResultItem:
    """Result of validating a single semantic data model."""

    semantic_data_model_id: str | None
    """The ID of the semantic data model, if it exists in storage."""

    semantic_data_model: SemanticDataModel
    """The validated semantic data model."""

    errors: list[ValidationMessage] = field(default_factory=list)
    """List of validation errors for this SDM."""

    warnings: list[ValidationMessage] = field(default_factory=list)
    """List of validation warnings for this SDM (e.g., unresolved file references)."""


@dataclass(frozen=True)
class _ValidateSemanticDataModelResultsSummary:
    """Summary of validation results."""

    total_sdms: Annotated[int, "Total number of semantic data models validated."]
    total_errors: Annotated[int, "Total number of validation errors."]
    total_warnings: Annotated[int, "Total number of validation warnings."]
    sdms_with_errors: Annotated[int, "Number of semantic data models with errors."]
    sdms_with_warnings: Annotated[int, "Number of semantic data models with warnings."]


@dataclass(frozen=True)
class ValidateSemanticDataModelResult:
    """Result of validating one or more semantic data models."""

    results: Annotated[
        list[ValidateSemanticDataModelResultItem],
        "List of validation results, one per SDM validated.",
    ]

    summary: Annotated[
        _ValidateSemanticDataModelResultsSummary | None,
        "Summary statistics about the validation run (e.g., total_sdms, total_errors).",
    ] = None


@dataclass(frozen=True)
class VerifyVerifiedQueryPayload:
    """Payload for verifying a verified query against a semantic data model."""

    semantic_data_model: Annotated[
        SemanticDataModel | dict,
        "The semantic data model to validate the verified query against.",
    ]

    verified_query: Annotated[
        VerifiedQuery | dict,
        "The verified query to validate. Must contain at least 'name', 'nlq', and 'sql' fields.",
    ]

    accept_initial_name: Annotated[
        str,
        "The initial name of the verified query. If the name is different from the initial name, "
        "the name must be unique.",
    ]

    @classmethod
    def model_validate(cls, data: Any) -> "VerifyVerifiedQueryPayload":
        """Validate and create payload from dict data."""
        return VerifyVerifiedQueryPayload(
            semantic_data_model=data.get("semantic_data_model", {}),
            verified_query=data.get("verified_query", {}),
            accept_initial_name=data.get("accept_initial_name", ""),
        )


@dataclass(frozen=True)
class VerifyVerifiedQueryResponse:
    """Response for verifying a verified query."""

    verified_query: Annotated[
        VerifiedQuery,
        "The verified query with validation errors set, if any.",
    ]
