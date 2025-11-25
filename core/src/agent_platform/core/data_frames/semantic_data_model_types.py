"""Semantic model data structures for data frames.

This module defines typed dictionaries for representing semantic models,
which describe collections of tables with their relationships and metadata.
"""

from __future__ import annotations

from enum import StrEnum
from types import NoneType
from typing import Annotated, Any, Literal, Required, TypedDict

from agent_platform.core.payloads.data_connection import (
    DataConnectionsInspectRequest,
    DataConnectionsInspectResponse,
)


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
    VERIFIED_QUERY_MISSING_SQL_FIELD = "verified_query_missing_sql_field"
    """Raised when a verified query is missing the SQL field."""
    VERIFIED_QUERY_REFERENCES_MISSING_TABLES = "verified_query_references_missing_tables"
    """Raised when a verified query references tables that do not exist in the semantic
    data model."""
    VERIFIED_QUERY_REFERENCES_DATA_FRAME = "verified_query_references_data_frame"
    """Raised when a verified query references a data frame that is not backed by a data connection
    nor a file reference."""
    VERIFIED_QUERY_SQL_VALIDATION_FAILED = "verified_query_sql_validation_failed"
    """Raised when a verified query validation fails due to an unexpected error."""
    VERIFIED_QUERY_MISSING_NLQ_FIELD = "verified_query_missing_nlq_field"
    """Raised when a verified query is missing the NLQ field."""
    VERIFIED_QUERY_MISSING_NAME_FIELD = "verified_query_missing_name_field"
    """Raised when a verified query is missing the name field."""
    VERIFIED_QUERY_NAME_VALIDATION_FAILED = "verified_query_name_validation_failed"
    """Raised when a verified query name validation fails."""
    VERIFIED_QUERY_NAME_NOT_UNIQUE = "verified_query_name_not_unique"
    """Raised when a verified query name is not unique within the semantic data model."""


class ValidationMessage(TypedDict):
    """A validation message."""

    message: Annotated[str, "A human-readable message describing the validation error or warning"]
    level: Annotated[
        ValidationMessageLevel, "The level of the validation message (error or warning)"
    ]
    kind: Annotated[ValidationMessageKind, "The kind of the validation message"]


class CortexSearchService(TypedDict, total=False):
    """Configuration for Cortex Search Service integration."""

    service: Annotated[str, "The name of the Cortex Search Service"]
    literal_column: Annotated[
        str | None, "The column in the Cortex Search Service that contains the literal values"
    ]
    database: Annotated[
        str | None,
        "The database where the Cortex Search Service is located. "
        "Defaults to base_table's database",
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
    description: Annotated[
        str | None, "A brief description about this dimension, including what data it has"
    ]
    unique: Annotated[
        bool | None, "A boolean value that indicates this dimension has unique values"
    ]
    sample_values: Annotated[
        list[str | int | float | bool | NoneType] | None,
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
    errors: Annotated[
        list[ValidationMessage] | None, "Validation errors for this dimension, if any"
    ]


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
        list[str | int | float | bool | NoneType] | None,
        """Sample values of this column, if any. Add any values that are likely to be
        referenced in the user questions. This field is optional""",
    ]
    errors: Annotated[
        list[ValidationMessage] | None, "Validation errors for this time dimension, if any"
    ]


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
    description: Annotated[
        str | None, "A brief description about this measure, including what data this column has"
    ]
    unique: Annotated[bool | None, "A boolean value that indicates this column has unique values"]
    sample_values: Annotated[
        list[str | int | float | bool | NoneType] | None,
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
        "A brief description about this filter, including details of what this filter is "
        "typically used for",
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
    description: Annotated[
        str | None, "A brief description of this metric, including what data this column has"
    ]
    sample_values: Annotated[
        list[str | int | float | bool | NoneType] | None,
        "Sample values of this column, if any. Add any values that are likely to be "
        "referenced in the user questions",
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
    data_connection_name: Annotated[
        str | None, "Name of the data connection (portable export/import)"
    ]
    file_reference: Annotated[
        FileReference | None, "File reference (thread_id, file_ref, sheet_name) for a file"
    ]


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
        "A list of equal columns from each of the left table and right table "
        "representing the join path",
    ]
    join_type: Annotated[str, "Either left_outer or inner"]
    relationship_type: Annotated[str, "Either many_to_one or one_to_one"]


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
    base_table: Required[
        Annotated[BaseTable, "A fully qualified name of the underlying base table in the database"]
    ]

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
    time_dimensions: Annotated[
        list[TimeDimension] | None, "A list of time dimension columns in this table"
    ]
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


class VerifiedQuery(TypedDict, total=False):
    """A verified query represents a validated SQL query saved from a data frame."""

    name: Required[
        Annotated[str, "The name of the data frame that was saved as a validated query."]
    ]
    nlq: Required[
        Annotated[
            str,
            "The NLQ (Natural Language Question) that the validated query answers "
            "(from the data frame description).",
        ]
    ]
    verified_at: Required[Annotated[str, "The ISO date-time string when the query was verified."]]
    verified_by: Required[Annotated[str, "The user ID of the user who verified the query."]]
    sql: Required[Annotated[str, "The full SQL query that was used to create the data frame."]]

    sql_errors: Annotated[
        list[ValidationMessage] | None, "Validation errors for the SQL query, if any"
    ]
    nlq_errors: Annotated[list[ValidationMessage] | None, "Validation errors for the NLQ, if any"]
    name_errors: Annotated[list[ValidationMessage] | None, "Validation errors for the name, if any"]


class SemanticDataModel(TypedDict, total=False):
    """A semantic model represents a collection of tables with their relationships."""

    # Required fields
    name: Required[
        Annotated[
            str,
            """A descriptive name for this semantic model. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with Snowflake reserved
        keywords""",
        ]
    ]

    # Optional fields
    description: Annotated[
        str | None,
        "A description of this semantic model, including details of what kind of analysis "
        "it's useful for",
    ]
    tables: Annotated[list[LogicalTable], "A list of logical tables in this semantic model"]
    relationships: Annotated[list[Relationship] | None, "A list of joins between logical tables"]
    errors: Annotated[
        list[ValidationMessage], "Validation errors for this semantic data model, if any"
    ]
    verified_queries: Annotated[
        list[VerifiedQuery] | None,
        "A list of validated queries that were saved from data frames "
        "created from SQL computations.",
    ]
    metadata: Annotated[
        SemanticDataModelMetadata | None,
        """Metadata container for inspection snapshots, schemas, and other metadata.
        Stores data directly within the SDM JSON payload without extra storage tables.""",
    ]
