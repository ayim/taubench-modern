"""Semantic model data structures for data frames.

This module defines typed dictionaries for representing semantic models,
which describe collections of tables with their relationships and metadata.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Required, TypedDict

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)

from agent_platform.core.payloads.data_connection import (
    DataConnectionsInspectRequest,
    DataConnectionsInspectResponse,
)

# Type alias for sample values used in Dimension, TimeDimension, Fact, and Metric
SampleValue = str | int | float | bool | date | datetime | None

if typing.TYPE_CHECKING:
    from pydantic.main import IncEx

# ============================================================================
# Validation Enums
# ============================================================================


class ValidationMessageLevel(StrEnum):
    """The level of a validation message."""

    ERROR = "error"
    WARNING = "warning"


class ValidationMessageKind(StrEnum):
    """The kind of a validation message."""

    SEMANTIC_MODEL_MISSING_REQUIRED_FIELD = "semantic_model_missing_required_field"
    """Raised for missing top-level/table/base-table fields such as `name`,
    `tables`, `base_table`, connection identifiers, etc."""
    SEMANTIC_MODEL_DUPLICATE_TABLE = "semantic_model_duplicate_table"
    """Raised when the same logical table name is declared twice in the model."""
    DATA_CONNECTION_NOT_FOUND = "data_connection_not_found"
    """Raised when a referenced data connection id cannot be found."""
    MISSING_DATA_CONNECTION = "missing_data_connection"
    """Raised when a data_connection_name is present but could not be resolved to an ID.
    This typically happens when an SDM is imported from a package but the referenced
    data connection does not exist in the current environment."""
    DATA_CONNECTION_CONNECTION_FAILED = "data_connection_connection_failed"
    """Raised when connecting to a data connection fails (includes connection
    and authentication errors)."""
    DATA_CONNECTION_TABLE_NOT_FOUND = "data_connection_table_not_found"
    """Raised when a referenced table does not exist in the data connection."""
    DATA_CONNECTION_TABLE_ACCESS_ERROR = "data_connection_table_access_error"
    """Raised when a table exists but cannot be accessed or queried."""
    DATA_CONNECTION_COLUMN_INVALID_EXPRESSION = "data_connection_column_invalid_expression"
    """Raised when a column expression is invalid or cannot be evaluated."""
    FILE_REFERENCE_UNRESOLVED = "file_reference_unresolved"
    """Raised when a table references an empty or missing file reference."""
    FILE_MISSING_THREAD_CONTEXT = "file_missing_thread_context"
    """Raised when a file cannot be resolved because no `thread_id` was provided."""
    FILE_NOT_FOUND = "file_not_found"
    """Raised when the referenced file cannot be found in the specified thread."""
    FILE_INSPECTION_ERROR = "file_inspection_error"
    """Raised when file inspection fails (e.g., malformed file or read error)."""
    FILE_SHEET_MISSING = "file_sheet_missing"
    """Raised when the expected worksheet/tab is not present in the file."""
    FILE_COLUMN_MISSING = "file_column_missing"
    """Raised when a required column is absent in the file."""
    VALIDATION_EXECUTION_ERROR = "validation_execution_error"
    """Raised when validation fails due to an unexpected error."""
    VERIFIED_QUERY_SQL_VALIDATION_FAILED = "verified_query_sql_validation_failed"
    """Raised when SQL query validation fails due to syntax errors or other issues."""
    VERIFIED_QUERY_MISSING_SQL_FIELD = "verified_query_missing_sql_field"
    """Raised when SQL field is missing from a verified query."""
    VERIFIED_QUERY_MISSING_NLQ_FIELD = "verified_query_missing_nlq_field"
    """Raised when NLQ field is missing from a verified query."""
    VERIFIED_QUERY_MISSING_NAME_FIELD = "verified_query_missing_name_field"
    """Raised when name field is missing from a verified query."""
    VERIFIED_QUERY_NAME_NOT_UNIQUE = "verified_query_name_not_unique"
    """Raised when a verified query name is not unique within the semantic data model."""
    VERIFIED_QUERY_NAME_INVALID_FORMAT = "verified_query_name_invalid_format"
    """Raised when a verified query name does not follow the required format."""
    VERIFIED_QUERY_REFERENCES_MISSING_TABLES = "verified_query_references_missing_tables"
    """Raised when a verified query references tables that do not exist in the semantic
    data model."""
    VERIFIED_QUERY_REFERENCES_DATA_FRAME = "verified_query_references_data_frame"
    """Raised when a verified query references a data frame that is not backed by a data connection
    nor a file reference."""
    VERIFIED_QUERY_PARAMETERS_VALIDATION_FAILED = "verified_query_parameters_validation_failed"
    """Raised when parameter definitions do not match the SQL query parameters."""


# ============================================================================
# Custom Exceptions for VerifiedQuery Validation
# ============================================================================


class VerifiedQueryValidationError(Exception):
    """Base exception for VerifiedQuery validation errors."""

    def __init__(
        self,
        message: str,
        kind: ValidationMessageKind,
        level: ValidationMessageLevel = ValidationMessageLevel.ERROR,
    ):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.level = level


class VerifiedQuerySQLError(VerifiedQueryValidationError):
    """Exception raised for SQL-related validation errors."""

    def __init__(
        self,
        message: str,
        kind: ValidationMessageKind = ValidationMessageKind.VERIFIED_QUERY_SQL_VALIDATION_FAILED,
        level: ValidationMessageLevel = ValidationMessageLevel.ERROR,
    ):
        super().__init__(message, kind, level)


class VerifiedQueryNameError(VerifiedQueryValidationError):
    """Exception raised for name-related validation errors."""

    def __init__(
        self,
        message: str,
        kind: ValidationMessageKind = ValidationMessageKind.VERIFIED_QUERY_NAME_NOT_UNIQUE,
        level: ValidationMessageLevel = ValidationMessageLevel.ERROR,
    ):
        super().__init__(message, kind, level)


class VerifiedQueryNLQError(VerifiedQueryValidationError):
    """Exception raised for NLQ-related validation errors."""

    def __init__(
        self,
        message: str,
        kind: ValidationMessageKind = ValidationMessageKind.VERIFIED_QUERY_MISSING_NLQ_FIELD,
        level: ValidationMessageLevel = ValidationMessageLevel.ERROR,
    ):
        super().__init__(message, kind, level)


class VerifiedQueryParameterError(VerifiedQueryValidationError):
    """Exception raised for parameter-related validation errors."""

    def __init__(
        self,
        message: str,
        kind: ValidationMessageKind = ValidationMessageKind.VERIFIED_QUERY_PARAMETERS_VALIDATION_FAILED,
        level: ValidationMessageLevel = ValidationMessageLevel.ERROR,
    ):
        super().__init__(message, kind, level)


class ValidationMessage(TypedDict):
    """A validation message."""

    message: Annotated[str, "A human-readable message describing the validation error or warning"]
    level: Annotated[ValidationMessageLevel, "The level of the validation message (error or warning)"]
    kind: Annotated[ValidationMessageKind, "The kind of the validation message"]


@dataclass
class VerifiedQueryValidationContext:
    """Context for VerifiedQuery validation.

    Contains prepared validation data extracted from the semantic data model.
    All data is prepared by the API layer before passing to validators.
    """

    # Prepared validation data (all extracted from semantic_data_model + storage)
    dialect: str | None
    logical_tables: list[LogicalTable]
    available_table_names: set[str]
    available_table_name_to_table: dict[str, LogicalTable]
    existing_query_names: set[str]
    original_name: str | None = None  # Used for name uniqueness check when editing


class CortexSearchService(TypedDict, total=False):
    """Configuration for Cortex Search Service integration."""

    service: Annotated[str, "The name of the Cortex Search Service"]
    literal_column: Annotated[str | None, "The column in the Cortex Search Service that contains the literal values"]
    database: Annotated[
        str | None,
        "The database where the Cortex Search Service is located. Defaults to base_table's database",
    ]
    schema: Annotated[
        str | None,
        "The schema where the Cortex Search Service is located. Defaults to base_table's schema",
    ]


class Dimension(TypedDict, total=False):
    """A dimension describes categorical values such as state, user_type, platform, etc.

    Use when it's categorical/descriptive context you'll group or filter by
    (e.g., product_name, customer_id, region).
    Dimensions answer who/what/where/how and provide labels for facts.
    """

    # Required fields
    name: Annotated[
        str,
        """A descriptive name for this dimension. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with Snowflake
        reserved keywords""",
    ]
    expr: Annotated[
        str,
        """The SQL expression for this dimension. This could be a reference to a physical
        column or a SQL expression with one or more columns from the underlying base table""",
    ]
    data_type: Annotated[
        str,
        """The data type of this dimension. For an overview of all data types in Snowflake
        see SQL data types reference. Note that VARIANT, OBJECT, GEOGRAPHY, and ARRAY are
         currently not supported""",
    ]

    # Optional fields
    synonyms: Annotated[
        list[str] | None,
        """A list of other terms/phrases used to refer to this dimension.
        Must be unique across all synonyms in this semantic model""",
    ]
    description: Annotated[str | None, "A brief description about this dimension, including what data it has"]
    unique: Annotated[bool | None, "A boolean value that indicates this dimension has unique values"]
    sample_values: Annotated[
        list[SampleValue] | None,
        """Sample values of this column, if any. Add any value that is likely to be
        referenced in the user questions""",
    ]
    cortex_search_service: Annotated[
        CortexSearchService | None, "Specifies the Cortex Search Service to use for this dimension"
    ]
    is_enum: Annotated[
        bool | None,
        """A Boolean value. If True, the values in the sample_values field are taken to be
        the full list of possible values, and the model only chooses from those values when
        filtering on that column""",
    ]
    errors: Annotated[list[ValidationMessage] | None, "Validation errors for this dimension, if any"]


class TimeDimension(TypedDict, total=False):
    """A time dimension describes time values, such as sale_date, created_at, and year.

    Use when it's temporal context you'll use to slice trends (e.g., order_date, ship_month,
    or even a computed duration like DATEDIFF(...)). Time dimensions enable period aggregations
    and time based analyses (day/week/month/year, etc.).
    """

    # Required fields
    name: Annotated[
        str,
        """A descriptive name for this time dimension. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with Snowflake reserved
        keywords""",
    ]
    expr: Annotated[
        str,
        """The SQL expression for this column. This could be a reference to a physical column or a
        SQL expression with one or more columns from the underlying base table""",
    ]
    data_type: Annotated[
        str,
        """The data type of this time dimension. For an overview of all data types in Snowflake
        see SQL data types reference. Note that VARIANT, OBJECT, GEOGRAPHY, and ARRAY are currently
        not supported""",
    ]

    # Optional fields
    synonyms: Annotated[
        list[str] | None,
        """A list of other terms/phrases used to refer to this time dimension.
        Must be unique across all synonyms in this semantic model""",
    ]
    description: Annotated[
        str | None,
        """A brief description about this dimension, including what data it has.
        Provide information that'll help someone writing queries using this table. For example,
        for DATETIME columns, specify the timezone of the data""",
    ]
    unique: Annotated[bool | None, "A boolean value that indicates this column has unique values"]
    sample_values: Annotated[
        list[SampleValue] | None,
        """Sample values of this column, if any. Add any values that are likely to be
        referenced in the user questions. This field is optional""",
    ]
    errors: Annotated[list[ValidationMessage] | None, "Validation errors for this time dimension, if any"]


class Fact(TypedDict, total=False):
    """A fact describes numerical values, such as revenue, impressions, and salary.

    Use when it's a row-level numeric value observed for each event/entity
    (e.g., quantity, unit_price, net_revenue = price * (1-discount)).
    Facts are unaggregated measures stored/calculated.
    (In newer docs, “facts” are what some tools call “measures”.)
    """

    # Required fields
    name: Annotated[
        str,
        """A descriptive name for this fact. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with Snowflake
        reserved keywords""",
    ]
    expr: Annotated[
        str,
        """This SQL expression can refer to either a physical column in the same logical table's
        base physical table or a logical column (fact, dimension, or time dimension) within that
        logical table""",
    ]
    data_type: Annotated[
        str,
        """The data type of this fact. For an overview of all data types in Snowflake
        see SQL data types reference. Note that VARIANT, OBJECT, GEOGRAPHY, and ARRAY are currently
        not supported""",
    ]

    # Optional fields
    synonyms: Annotated[
        list[str] | None,
        """A list of other terms/phrases used to refer to this measure.
        Must be unique across all synonyms in this semantic model""",
    ]
    description: Annotated[str | None, "A brief description about this measure, including what data this column has"]
    unique: Annotated[bool | None, "A boolean value that indicates this column has unique values"]
    sample_values: Annotated[
        list[SampleValue] | None,
        """Sample values of this column, if any. Add any values that are likely to be
        referenced in the user questions. This field is optional""",
    ]
    errors: Annotated[list[ValidationMessage] | None, "Validation errors for this fact, if any"]


class Filter(TypedDict, total=False):
    """A filter represents a SQL expression that's used for filtering."""

    # Required fields
    name: Annotated[str, "A descriptive name for this filter"]
    expr: Annotated[str, "The SQL expression of this filter, referencing logical columns"]

    # Optional fields
    synonyms: Annotated[
        list[str] | None,
        "A list of other terms/phrases used to refer to this filter. "
        "Must be unique across all synonyms in this semantic model",
    ]
    description: Annotated[
        str | None,
        "A brief description about this filter, including details of what this filter is typically used for",
    ]
    errors: Annotated[list[ValidationMessage] | None, "Validation errors for this filter, if any"]


class Metric(TypedDict, total=False):
    """A metric describes quantifiable measures of business performance.

    Use when it's a business KPI that aggregates (often over facts) across rows
    e.g., total_revenue = SUM(net_revenue), avg_order_value = AVG(order_total),
    or a composite like margin %. Define metrics at the most granular level so
    they can roll up by any dimension.
    """

    # Required fields
    name: Annotated[
        str,
        """A descriptive name for this metric. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with Snowflake
        reserved keywords""",
    ]
    expr: Annotated[
        str,
        """The SQL expression for this column. This could reference a logical column (fact,
        dimension or time dimension) in the same logical table or a logical column from another
        logical table within the semantic model""",
    ]
    data_type: Annotated[
        str,
        """The data type of this metric. For an overview of all data types in Snowflake, see the
        reference for SQL data types. Note that VARIANT, OBJECT, GEOGRAPHY, and ARRAY are
        currently not supported""",
    ]

    # Optional fields
    synonyms: Annotated[
        list[str] | None,
        "A list of other terms/phrases used to refer to this metric. "
        "It must be unique across all synonyms in this semantic model",
    ]
    description: Annotated[str | None, "A brief description of this metric, including what data this column has"]
    sample_values: Annotated[
        list[SampleValue] | None,
        "Sample values of this column, if any. Add any values that are likely to be referenced in the user questions",
    ]
    errors: Annotated[list[ValidationMessage] | None, "Validation errors for this metric, if any"]


class FileReference(TypedDict, total=False):
    """A file reference represents a file reference."""

    thread_id: Annotated[str, "The thread_id of the file"]
    file_ref: Annotated[str, "The file_ref of the file"]
    sheet_name: Annotated[str | None, "The sheet name of the file"]


class DataConnectionSnapshotMetadata(TypedDict):
    """Provenance metadata for data connection inspection snapshots.

    Captures the context needed to understand how the inspection was performed:
    - Which data connection was inspected (both local ID and portable name)
    - What request parameters were used (tables_to_inspect, columns_to_inspect, etc.)
    """

    data_connection_id: Annotated[
        str | None,
        "Local data connection ID (unique to this agent-server instance)",
    ]
    data_connection_name: Annotated[
        str | None,
        "Data connection name (stable across environments for export/import)",
    ]
    data_connection_inspect_request: Annotated[
        DataConnectionsInspectRequest | None,
        "Original API request parameters used to produce the inspection",
    ]


class FileSnapshotMetadata(TypedDict):
    """Provenance metadata for file inspection snapshots.

    Captures the file reference needed to identify which file was inspected.
    """

    file_reference: Annotated[
        FileReference | None,
        "Reference to the inspected file (thread_id, file_ref, sheet_name)",
    ]


class InputDataConnectionSnapshot(TypedDict):
    """Complete inspection snapshot stored within an SDM's metadata.

    Combines the inspection API response with provenance metadata, enabling consumers to:
    - Extract `inspection_result` and use it like an API response (tables, columns, sample data)
    - Understand context via `inspection_request_info` (what was inspected, how, and when)
    - Reproduce inspections or trace data lineage

    Structure mirrors the public inspection API contract.
    """

    kind: Annotated[
        Literal["file", "data_connection"],
        "Data source type: 'file' for uploaded files, 'data_connection' for database connections",
    ]

    inspection_result: Annotated[
        DataConnectionsInspectResponse,
        "Inspection API response: tables with columns, data types, and sample values",
    ]

    inspection_request_info: Annotated[
        DataConnectionSnapshotMetadata | FileSnapshotMetadata,
        "Provenance metadata: which data source was inspected and how",
    ]

    inspected_at: Annotated[
        str,
        "ISO 8601 timestamp when the inspection occurred",
    ]


class SemanticDataModelMetadata(TypedDict, total=False):
    """Top-level metadata container for semantic data models.

    Stores inspection snapshots and other metadata directly in the SDM JSON payload,
    avoiding the need for separate storage tables.

    Current fields:
    - `input_data_connection_snapshots`: Inspection results from data sources used to create the SDM
    - `extra`: Reserved for future metadata types (e.g., column JSON schemas, versioning info)

    Note: Currently only one snapshot is populated (from the primary data source), but the
    list structure supports multiple sources for future SDMs that span multiple connections/files.
    """

    input_data_connection_snapshots: Annotated[
        list[InputDataConnectionSnapshot] | None,
        """Inspection snapshots from data sources (files or database connections).
        Each snapshot contains the inspection API response plus provenance metadata.""",
    ]

    extra: Annotated[
        dict[str, Any] | None,
        """Reserved for future metadata extensions (e.g., schemas, versioning).
        Enables forward-compatible additions without breaking existing consumers.""",
    ]


class BaseTable(TypedDict, total=False):
    """A base table represents fully qualified table names.

    Note that as an extension to the default snowflake model we provide a way
    to reference either a data connection, a file reference, or a data frame in the following way:

    For a database, the `data_connection_id` must be specified with the id of the data connection.
        In this case the database/schema/table must be specified as usual

    For a file, the `file_reference` must be specified with the thread_id and file_ref of the file.

    For a data frame, just the `table` must be specified with the name of the data frame
        in the thread (and the data_connection_id and file_reference must not be specified).
    """

    # Not required for all databases (not all databases have a database and schema
    # -- i.e.: SQLite or files)
    database: Annotated[
        str | None,
        "Name of the database (when a data_connection_id is specified)",
    ]

    # Not required for all databases (not all databases have a database and schema
    # -- i.e.: SQLite or files)
    schema: Annotated[
        str | None,
        "Name of the schema (when a data_connection_id is specified)",
    ]

    # The real table name. For file_references it may be unspecified if a data frame
    # is not yet created from the file reference.
    table: Annotated[
        str | None,
        """Name of the table (or data frame name for a file). It must be a valid SQL identifier
        and is used to reference this table in the SQL queries.""",
    ]

    # For data connections the data_connection_id is required
    data_connection_id: Annotated[str | None, "ID of the data connection"]
    # For portable exports, data_connection_name is used instead of ID
    data_connection_name: Annotated[str | None, "Name of the data connection (portable export/import)"]
    file_reference: Annotated[FileReference | None, "File reference (thread_id, file_ref, sheet_name) for a file"]


class PrimaryKey(TypedDict):
    """A primary key represents the columns that uniquely represent each row of the table."""

    # Required fields
    columns: Annotated[list[str], "A list of dimension columns uniquely representing the table"]


class RelationshipColumn(TypedDict):
    """A column mapping for relationships between tables."""

    left_column: Annotated[str, "The column name from the left table"]
    right_column: Annotated[str, "The column name from the right table"]


class Relationship(TypedDict):
    """Defines join relationships between logical tables."""

    # Required fields
    name: Annotated[str, "A unique identifier for the relationship"]
    left_table: Annotated[
        str,
        "Logical table name as defined earlier in your YAML file. For many-to-one relationships, "
        "the left table should be the many side of the relationship for optimal performance",
    ]
    right_table: Annotated[
        str,
        "Logical table name as defined earlier in your YAML file. For many-to-one relationships, "
        "the right table must be the one side of the relationship for optimal performance",
    ]
    relationship_columns: Annotated[
        list[RelationshipColumn],
        "A list of equal columns from each of the left table and right table representing the join path",
    ]


class LogicalTable(TypedDict, total=False):
    """A logical table represents a view over a physical database table or view."""

    # Required fields
    name: Required[
        Annotated[
            str,
            """A descriptive name for this table. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with Snowflake
        reserved keywords""",
        ]
    ]
    base_table: Required[Annotated[BaseTable, "A fully qualified name of the underlying base table in the database"]]

    # Optional fields
    synonyms: Annotated[
        list[str] | None,
        "A list of other terms/phrases used to refer to this table. "
        "It must be unique across synonyms within the logical table",
    ]
    description: Annotated[str | None, "A description of this table"]
    primary_key: Annotated[
        PrimaryKey | None,
        "The primary key columns for this table. Required if you're defining relationships",
    ]
    dimensions: Annotated[list[Dimension] | None, "A list of dimension columns in this table"]
    time_dimensions: Annotated[list[TimeDimension] | None, "A list of time dimension columns in this table"]
    facts: Annotated[list[Fact] | None, "A list of fact columns in this table"]
    metrics: Annotated[list[Metric] | None, "A list of metrics in this table"]
    filters: Annotated[list[Filter] | None, "Predefined filters on this table, if any"]
    errors: Annotated[list[ValidationMessage], "Validation errors for this table, if any"]


CategoriesType = Literal["dimensions", "time_dimensions", "metrics", "facts"]

CATEGORIES: tuple[CategoriesType, CategoriesType, CategoriesType, CategoriesType] = (
    "dimensions",
    "time_dimensions",
    "metrics",
    "facts",
)


# Type alias for the Literal type used in QueryParameter
# This is the single source of truth for valid parameter data types
# Runtime values can be extracted using typing.get_args(QueryParameterDataType)
QueryParameterDataType = Literal["integer", "float", "boolean", "string", "datetime"]

# Mapping from QueryParameterDataType to Python types
# Used for creating tool signatures with proper type annotations
QUERY_PARAMETER_TYPE_TO_PYTHON: dict[str, type] = {
    "integer": int,
    "float": float,
    "boolean": bool,
    "string": str,
    "datetime": str,
}


class QueryParameter(BaseModel):
    """A parameter definition for a verified query.

    Parameters allow verified queries to be reusable with different values.

    Example:
        {
            "name": "country",
            "data_type": "string",
            "example_value": "Germany",
            "description": "Country to filter customers by"
        }
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ...,
        min_length=1,
        description="Parameter name used in SQL (e.g., 'country' for :country)",
    )
    data_type: QueryParameterDataType = Field(
        ...,
        description="Data type of this parameter.",
    )
    example_value: str | int | float | bool | None = Field(
        default=None,
        description="Optional example value for SQL validation and default.",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Human-readable description of the parameter",
    )

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_string_fields(cls, v: str) -> str:
        """Strip whitespace from string fields."""
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_example_value_matches_data_type(self) -> QueryParameter:
        """Validate that example_value matches the declared data_type.

        Uses model_validator to access both data_type and example_value after
        all fields are validated, ensuring reliable cross-field validation.

        If example_value is None, validation is skipped.
        """
        data_type = self.data_type
        example_value = self.example_value

        # Skip validation if example_value is not provided
        if example_value is None:
            return self

        match data_type:
            case "integer":
                if not isinstance(example_value, int):
                    raise ValueError(
                        f"Parameter '{self.name}': example_value must be an integer "
                        f"for data_type 'integer', got {type(example_value).__name__}"
                    )
            case "float":
                if not isinstance(example_value, int | float):
                    raise ValueError(
                        f"Parameter '{self.name}': example_value must be a number "
                        f"for data_type 'float', got {type(example_value).__name__}"
                    )
            case "boolean":
                if not isinstance(example_value, bool):
                    raise ValueError(
                        f"Parameter '{self.name}': example_value must be a boolean "
                        f"for data_type 'boolean', got {type(example_value).__name__}"
                    )
            case "string":
                if not isinstance(example_value, str):
                    raise ValueError(
                        f"Parameter '{self.name}': example_value must be a string "
                        f"for data_type 'string', got {type(example_value).__name__}"
                    )
            case "datetime":
                if not isinstance(example_value, str):
                    raise ValueError(
                        f"Parameter '{self.name}': example_value must be a string (ISO-8601 format) "
                        f"for data_type 'datetime', got {type(example_value).__name__}"
                    )
                # Validate ISO-8601 format
                try:
                    # Handle both with without timezone
                    datetime_str = example_value.replace("Z", "+00:00")
                    datetime.fromisoformat(datetime_str)
                except ValueError as e:
                    raise ValueError(
                        f"Parameter '{self.name}': example_value must be in ISO-8601 format "
                        f"for data_type 'datetime': {e}"
                    ) from e

        return self


class VerifiedQuery(BaseModel):
    """A verified query represents a validated SQL query saved from a data frame.

    Verified queries can optionally include parameters using :param_name
    syntax in the SQL. When parameters are present, each must have a
    corresponding QueryParameter definition with an example_value that will
    be used for validation and as the default value.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ...,
        min_length=1,
        description="The name of the data frame that was saved as a validated query.",
    )
    nlq: str = Field(
        ...,
        min_length=1,
        description=(
            "The NLQ (Natural Language Question) that the validated query answers (from the data frame description)."
        ),
    )
    verified_at: str = Field(
        ...,
        description="The ISO date-time string when the query was verified.",
    )
    verified_by: str = Field(
        ...,
        description="The user ID of the user who verified the query.",
    )
    sql: str = Field(
        ...,
        min_length=1,
        description="The full SQL query. May contain :param_name placeholders for parameterized queries.",
    )

    parameters: list[QueryParameter] | None = Field(
        default=None,
        description="Optional list of parameters for parameterized queries. Each "
        "parameter must have name, example_value, and description.",
    )

    sql_errors: list[ValidationMessage] | None = Field(
        default=None,
        description="Validation errors for the SQL query",
    )
    nlq_errors: list[ValidationMessage] | None = Field(
        default=None,
        description="Validation errors for the NLQ",
    )
    name_errors: list[ValidationMessage] | None = Field(
        default=None,
        description="Validation errors for the name",
    )
    parameter_errors: list[ValidationMessage] | None = Field(
        default=None,
        description="Validation errors for the parameters",
    )

    @field_validator("name", "nlq", "sql", mode="before")
    @classmethod
    def strip_string_fields(cls, v: str) -> str:
        """Strip whitespace from string fields."""
        return v.strip()

    @field_validator("parameters", mode="before")
    @classmethod
    def convert_parameters_to_models(cls, v: list[QueryParameter | dict] | None) -> list[QueryParameter] | None:
        """Convert parameter dicts to QueryParameter instances.

        This ensures that QueryParameter validators run on each parameter,
        validating data_type, example_value, etc.

        Any validation errors from QueryParameter will be caught and re-raised
        with proper parameter index in the error location.
        """
        if v is None:
            return None

        result = []
        for idx, item in enumerate(v):
            if isinstance(item, dict):
                # Convert dict to QueryParameter - this triggers all validators
                try:
                    result.append(QueryParameter.model_validate(item))
                except ValidationError as e:
                    # Re-raise with parameter index in location
                    from pydantic_core import ValidationError as PydanticCoreValidationError

                    # Extract errors and prepend the index to the location
                    new_errors = []
                    for error in e.errors():
                        error_dict = error.copy()
                        # Prepend index to location tuple
                        error_dict["loc"] = (idx, *error.get("loc", ()))
                        new_errors.append(error_dict)

                    raise PydanticCoreValidationError.from_exception_data(
                        "VerifiedQuery.parameters",
                        new_errors,
                    ) from e
            else:
                result.append(item)
        return result

    @field_validator("name", mode="after")
    @classmethod
    def validate_name_format(cls, v: str) -> str:
        """Validate name format using validate_verified_query_name.

        This validates the name format synchronously without external dependencies.
        Name uniqueness is validated separately in _validate_name() method
        since it requires access to the semantic data model.
        """
        from agent_platform.core.data_frames.data_frame_utils import (
            VerifiedQueryNameError,
            validate_verified_query_name,
        )

        try:
            return validate_verified_query_name(v)
        except VerifiedQueryNameError as e:
            # Convert PlatformHTTPError to ValueError for Pydantic
            raise ValueError(str(e)) from e

    @model_validator(mode="after")
    def validate_against_semantic_data_model(self, info: ValidationInfo) -> VerifiedQuery:
        """Validate this verified query against a semantic data model.

        This validator runs during model_validate() and performs:
        - SQL syntax and table references validation
        - Parameter definitions validation
        - Name uniqueness validation
        """
        # Get validation context from info.context
        if not info.context or "validation_context" not in info.context:
            # If no context provided, skip semantic validations
            # This allows the model to be created without full validation
            return self

        validation_context: VerifiedQueryValidationContext = info.context["validation_context"]

        # Run validations - each raises immediately on error
        self._validate_sql(validation_context)
        self._validate_name(validation_context)

        return self

    def _validate_sql(
        self,
        context: VerifiedQueryValidationContext,
    ) -> None:
        """Validate SQL query syntax, table references, and parameters."""
        # 1. Check dialect - raise immediately if missing
        if not context.dialect:
            raise VerifiedQuerySQLError(
                message=(
                    "Cannot determine SQL dialect from semantic data model. "
                    "Please ensure at least one table has a data connection "
                    "configured."
                ),
            )

        # Type assertion: dialect is guaranteed to be non-None after the check above
        dialect = typing.cast(str, context.dialect)

        # 2. Validate SQL syntax and table references (combined)
        self._validate_sql_syntax_and_tables(context)

        # 3. Validate parameters
        self._validate_sql_parameters(context, dialect)

    def _validate_sql_parameters(
        self,
        context: VerifiedQueryValidationContext,
        dialect: str,
    ) -> None:
        """Validate parameters in SQL against the parameter definitions."""
        from agent_platform.server.data_frames.sql_parameter_utils import (
            extract_parameters_from_sql,
            validate_parameter_definitions,
        )

        provided_params_list = self.parameters or []

        try:
            extracted_param_names = extract_parameters_from_sql(self.sql, dialect=dialect)
        except ValueError:
            # SQL parsing failed - will be caught by syntax validation
            return

        if extracted_param_names:
            # SQL contains parameters - validate definitions
            if not provided_params_list:
                param_names_str = ", ".join(extracted_param_names)
                raise VerifiedQueryParameterError(
                    message=(
                        f"SQL query contains {len(extracted_param_names)} "
                        f"parameter(s) ({param_names_str}) but no parameter "
                        "definitions were provided. Please provide parameter "
                        "definitions with name, data_type, example_value, and "
                        "description."
                    ),
                )
            else:
                # Validate parameter definitions
                validation_result = validate_parameter_definitions(
                    self.sql,
                    provided_params_list,
                    dialect=dialect,
                )

                # Raise immediately on missing parameters (errors)
                if validation_result.missing_in_definitions:
                    param_name = next(iter(validation_result.missing_in_definitions))
                    raise VerifiedQueryParameterError(
                        message=(
                            f"SQL query contains parameter '{param_name}' that is not "
                            "defined. Please add a parameter definition with name, "
                            "data_type, example_value, and description."
                        ),
                    )

                # Raise immediately on extra parameters (warnings)
                if validation_result.extra_in_definitions:
                    param_name = next(iter(validation_result.extra_in_definitions))
                    raise VerifiedQueryParameterError(
                        message=(
                            f"Parameter definition for '{param_name}' is provided but "
                            "not used in the SQL query. Please remove this definition "
                            f"or add :{param_name} to the SQL."
                        ),
                        level=ValidationMessageLevel.WARNING,
                    )

        elif provided_params_list:
            # No parameters in SQL but definitions provided - raise warning
            raise VerifiedQueryParameterError(
                message=(
                    "Parameter definitions were provided but SQL query "
                    "does not contain any :param_name placeholders. "
                    "Either add parameters to the SQL or remove the "
                    "definitions."
                ),
                level=ValidationMessageLevel.WARNING,
            )

    def _validate_sql_syntax_and_tables(
        self,
        context: VerifiedQueryValidationContext,
    ) -> None:
        """Validate SQL syntax using sqlglot and given dialect
        and validate table references in SQL against the semantic data model.
        """
        from agent_platform.server.data_frames.sql_manipulation import (
            extract_variable_names_required_from_sql_computation,
            validate_sql_query,
        )

        # Parse SQL once and validate syntax
        try:
            sql_ast = validate_sql_query(self.sql, dialect=context.dialect)
        except Exception as e:
            raise VerifiedQuerySQLError(
                message=f"SQL syntax error: {e}",
            ) from e

        # Extract table names from the validated AST
        required_table_names = extract_variable_names_required_from_sql_computation(sql_ast)

        # Check if we have table names to validate
        if not context.available_table_names:
            # If SQL requires tables but SDM has none, that's an error
            if required_table_names:
                table_list = ", ".join(sorted(required_table_names))
                raise VerifiedQuerySQLError(
                    message=(
                        f"SQL query references tables ({table_list}) but the "
                        "semantic data model has no tables defined. Please add "
                        "tables to the semantic data model before creating verified queries."
                    ),
                    kind=ValidationMessageKind.VERIFIED_QUERY_REFERENCES_MISSING_TABLES,
                )
            # SQL doesn't reference any tables, validation passes
            return

        # Check for missing tables
        missing_tables = required_table_names - context.available_table_names
        if missing_tables:
            missing_str = ", ".join(sorted(missing_tables))
            available_str = ", ".join(sorted(context.available_table_names)) if context.available_table_names else ""
            raise VerifiedQuerySQLError(
                message=(
                    f"SQL query references tables that do not exist in the "
                    f"semantic data model: {missing_str}.\nExisting tables: "
                    f"{available_str}"
                ),
                kind=ValidationMessageKind.VERIFIED_QUERY_REFERENCES_MISSING_TABLES,
            )

        # Check data frame references (warnings) - raise immediately if found
        for table_name in required_table_names:
            table = context.available_table_name_to_table.get(table_name)
            if table:
                base_table = table.get("base_table")
                if base_table:
                    if not base_table.get("data_connection_id") and not base_table.get("file_reference"):
                        raise VerifiedQuerySQLError(
                            message=(
                                f"Table {table_name} references a data frame in "
                                "the semantic data model that's not backed by a "
                                "data connection nor a file reference. When used in a "
                                "new chat, a data frame with that name must be created "
                                "in the chat before using this query."
                            ),
                            kind=ValidationMessageKind.VERIFIED_QUERY_REFERENCES_DATA_FRAME,
                            level=ValidationMessageLevel.WARNING,
                        )

    def _validate_name(
        self,
        context: VerifiedQueryValidationContext,
    ) -> None:
        """Validate query name uniqueness within the semantic data model."""
        if context.existing_query_names and self.name in context.existing_query_names:
            raise VerifiedQuerySQLError(
                message=f"Name '{self.name}' is already used by another verified query in the semantic data model.",
                kind=ValidationMessageKind.VERIFIED_QUERY_NAME_NOT_UNIQUE,
            )


def _remove_none_values(obj: Any) -> Any:
    """Recursively remove None values from dicts and lists."""
    if isinstance(obj, dict):
        return {k: _remove_none_values(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_remove_none_values(item) for item in obj]
    return obj


class SemanticDataModel(BaseModel):
    """A semantic model represents a collection of tables with their relationships."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    # Required field
    name: str = Field(
        ...,
        min_length=1,
        description=(
            "A descriptive name for this semantic model. Must be unique and follow the "
            "unquoted identifiers requirements. It also cannot conflict with Snowflake reserved keywords."
        ),
    )

    # Optional fields
    id: str | None = Field(
        default=None,
        description="The unique identifier of this semantic model.",
    )
    description: str | None = Field(
        default=None,
        description="A description of this semantic model, including details of what kind of analysis it's useful for.",
    )
    tables: list[LogicalTable] = Field(
        default_factory=list,
        description="A list of logical tables in this semantic model.",
    )
    relationships: list[Relationship] | None = Field(
        default=None,
        description="A list of joins between logical tables.",
    )
    # TODO we should make this default to a list to avoid extra null-checks in the REST API
    errors: list[ValidationMessage] | None = Field(
        default=None,
        description="Validation errors for this semantic data model, if any.",
    )
    verified_queries: list[VerifiedQuery] | None = Field(
        default=None,
        description="A list of validated queries that were saved from data frames created from SQL computations.",
    )
    metadata: SemanticDataModelMetadata | None = Field(
        default=None,
        description=(
            "Metadata container for inspection snapshots, schemas, and other metadata. "
            "Stores data directly within the SDM JSON payload without extra storage tables."
        ),
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        """Strip whitespace from name."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("verified_queries", mode="before")
    @classmethod
    def convert_verified_queries(cls, v: list | None) -> list[VerifiedQuery] | None:
        """Convert verified query dicts to VerifiedQuery models."""
        if v is None:
            return None
        result = []
        for item in v:
            if isinstance(item, dict):
                result.append(VerifiedQuery.model_validate(item))
            else:
                result.append(item)
        return result

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = True,  # Defaulting to always excluding None for SDM, which pydantic doesn't do by default
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        """Dump the model to a dictionary.

        Overrides the default to set exclude_none=True by default.
        """
        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )

    @model_serializer(mode="wrap")
    def _serialize_exclude_none(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict[str, Any]:
        """Serialize the model, excluding None values by default.

        This ensures FastAPI responses exclude None values, while still respecting
        explicit exclude_none=False calls.
        """
        serialized = handler(self)
        # Respect the exclude_none parameter:
        # - If exclude_none=False was explicitly passed, keep None values
        # - Otherwise (True or None/default), strip None values for FastAPI compatibility
        if info.exclude_none is False:
            return serialized
        return _remove_none_values(serialized)

    def to_comparable_json(self, *, exclude_metadata: bool = True) -> str:
        """Convert to sorted JSON string for comparison, stripping environment-specific fields.

        This strips environment-specific fields (data_connection_id, data_connection_name,
        file_reference) to enable comparison of semantic structure only.

        Args:
            exclude_metadata: If True, also excludes metadata from comparison (default: True)

        Returns:
            A sorted JSON string representation suitable for comparison
        """
        import json

        # Use mode="json" to serialize datetime objects to ISO strings
        data = self.model_dump(mode="json")

        # Strip environment-specific fields from tables
        for table in data.get("tables") or []:
            if base_table := table.get("base_table"):
                base_table.pop("data_connection_id", None)
                base_table.pop("data_connection_name", None)
                base_table.pop("file_reference", None)
            table.pop("file", None)

        # Optionally exclude metadata
        if exclude_metadata:
            data.pop("metadata", None)

        return json.dumps(data, sort_keys=True)
