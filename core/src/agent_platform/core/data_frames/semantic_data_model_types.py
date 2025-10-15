"""Semantic model data structures for data frames.

This module defines typed dictionaries for representing semantic models,
which describe collections of tables with their relationships and metadata.
"""

from types import NoneType
from typing import Annotated, TypedDict


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


class FileReference(TypedDict, total=False):
    """A file reference represents a file reference."""

    thread_id: Annotated[str, "The thread_id of the file"]
    file_ref: Annotated[str, "The file_ref of the file"]
    sheet_name: Annotated[str | None, "The sheet name of the file"]


class BaseTable(TypedDict, total=False):
    """A base table represents fully qualified table names.

    Note that as an extension to the default snowflake model we provide a way
    to reference either a data connection or a file reference in the following way:

    For a database, the `data_connection_id` must be specified with the id of the data connection.
        In this case the database/schema/table must be specified as usual

    For a file, the `file_reference` must be specified with the thread_id and file_ref of the file.
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

    # The real table name is required for all use cases, for files, the table is the data frame name
    # (this is the name that the SQL must reference the table by, it must be a valid SQL identifier)
    table: Annotated[
        str,
        """Name of the table (or data frame name for a file). It must be a valid SQL identifier
        and is used to reference this table in the SQL queries.""",
    ]

    # For data connections the data_connection_id is required
    data_connection_id: Annotated[str | None, "ID of the data connection"]
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
    name: Annotated[
        str,
        """A descriptive name for this table. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with Snowflake
        reserved keywords""",
    ]
    base_table: Annotated[
        BaseTable, "A fully qualified name of the underlying base table in the database"
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


class SemanticDataModel(TypedDict, total=False):
    """A semantic model represents a collection of tables with their relationships."""

    # Required fields
    name: Annotated[
        str,
        """A descriptive name for this semantic model. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with Snowflake reserved
        keywords""",
    ]

    # Optional fields
    description: Annotated[
        str | None,
        "A description of this semantic model, including details of what kind of analysis "
        "it's useful for",
    ]
    tables: Annotated[list[LogicalTable] | None, "A list of logical tables in this semantic model"]
    relationships: Annotated[list[Relationship] | None, "A list of joins between logical tables"]
