"""Semantic model data structures for as we want the LLM generator to see it."""

from __future__ import annotations

import warnings
from types import NoneType
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, Field

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

if TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition

Category = Literal["dimension", "fact", "metric", "time_dimension"]
EnhancementMode = Literal["full", "tables", "columns"]

CATEGORY_TO_COLUMN_GROUP: dict[Category, str] = {
    "dimension": "dimensions",
    "fact": "facts",
    "metric": "metrics",
    "time_dimension": "time_dimensions",
}


class ColumnForLLM(BaseModel):
    """A column in a table."""

    # Required fields
    name: Annotated[
        str,
        """A descriptive name for this column. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with SQL
        reserved keywords. It can be changed to a more business-friendly name
        (the actual name of the column in the database is kept in the `expr` field).""",
    ]
    expr: Annotated[
        str,
        """The SQL expression for this column. This could be a reference to a physical
        column or a SQL expression with one or more columns from the underlying base table.
        It MUST NOT be changed.
        """,
    ]
    data_type: Annotated[
        str | None,
        """The SQL data type of this column. It MUST NOT be changed.""",
    ] = None

    category: Annotated[
        Category | None,
        """
        The category of the column. It can be changed if the current name or description
        match a better category.

        It can be a `dimension`, `fact`, `metric`, or `time_dimension`.

        - `dimension`: describes categorical values such as state, user_type, platform, etc.

            Use when it's categorical/descriptive context you'll group or filter by
            (e.g., product_name, customer_id, region).
            Dimensions answer who/what/where/how and provide labels for facts.

        - `fact`: describes numerical values, such as revenue, impressions, and salary.

            Use when it's a row-level numeric value observed for each event/entity
            (e.g., quantity, unit_price, net_revenue = price * (1-discount)).
            Facts are unaggregated measures stored/calculated.
            (In newer docs, “facts” are what some tools call “measures”.)

        - `metric`: describes quantifiable measures of business performance.

            Use when it's a business KPI that aggregates (often over facts) across rows
            e.g., total_revenue = SUM(net_revenue), avg_order_value = AVG(order_total),
            or a composite like margin %. Define metrics at the most granular level so
            they can roll up by any dimension.

        - `time_dimension`: describes time values, such as sale_date, created_at, and year.

            Use when it's temporal context you'll use to slice trends (e.g., order_date, ship_month,
            or even a computed duration like DATEDIFF(...)). Time dimensions enable period
            aggregations and time based analyses (day/week/month/year, etc.). MUST NOT be changed.
        """,
    ] = None

    # Optional fields
    synonyms: Annotated[
        list[str] | None,
        """A list of other terms/phrases used to refer to this dimension.
        Must be unique across all synonyms in this semantic model. The list of synonyms can
        be changed if the current name or description have better synonyms.""",
    ] = None
    description: Annotated[
        str | None,
        """A brief description about this column, including what data it has. Can be changed
        if the current description can be improved.""",
    ] = None
    unique: Annotated[
        bool | None,
        "A boolean value that indicates this column has unique values. MUST NOT be changed.",
    ] = None
    sample_values: Annotated[
        list[str | int | float | bool | NoneType] | None,
        """Sample values of this column, if any. Add any value that is likely to be
        referenced in the user questions. MUST NOT be changed.""",
    ] = None


# Ignore warning: UserWarning: Field name "schema" in "BaseTable"
# shadows an attribute in parent "BaseModel"

warnings.filterwarnings(
    "ignore",
    message='Field name "schema" in "BaseTable" shadows an attribute in parent "BaseModel"',
)


class BaseTable(BaseModel):
    """A base table represents represents the actual table in the database.
    MUST NOT be changed.
    """

    schema: str | None = Field(alias="schema", description="Name of the schema. MUST NOT be changed.", default=None)

    table: Annotated[
        str,
        "The real name of the table. MUST NOT be changed.",
    ]


class LogicalTableBase(BaseModel):
    """A base class for logical tables that share common fields."""

    # Required fields
    name: Annotated[
        str,
        """A descriptive name for this table. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with SQL
        reserved keywords. Can be changed if the current name can be improved.""",
    ]
    base_table: Annotated[
        BaseTable,
        "A fully qualified name of the underlying base table in the database. MUST NOT be changed.",
    ]

    # Optional fields
    synonyms: Annotated[
        list[str] | None,
        "A list of other terms/phrases used to refer to this table. "
        "It must be unique across synonyms within the logical table. Can be changed if the current "
        "synonyms can be improved.",
    ] = None
    description: Annotated[
        str | None,
        "A description of this table. Can be changed if the current description can be improved.",
    ] = None


class LogicalTable(LogicalTableBase):
    """A logical table represents a view over a physical database table or view."""

    columns: Annotated[
        list[ColumnForLLM] | None,
        "A list of columns in this table with their categories (dimension, fact, metric, time_dimension).",
    ] = None


# This is the same schema as LogicalTable without columns, allowing an LLM to generate enhancements
# for the table's metadata only without being distracted by the need to generate column info.
class LogicalTableMetadataForLLM(LogicalTableBase):
    """A logical table represents a view over a physical database table or view (metadata only)."""


class SemanticDataModelForLLM(BaseModel):
    """A semantic model represents a collection of tables with their relationships."""

    # Required fields
    name: Annotated[
        str,
        """A descriptive, domain-specific name for this semantic model that clearly indicates
        what business domain or data subject it represents. The name should be human-readable,
        concise (generally < 25 characters), and should NOT use underscores or snake_case.

        Examples of GOOD names: 'Product Catalog', 'Sales Analytics', 'Customer Orders'
        Examples of BAD names: 'Semantic_Data_Model', 'Data_Model', 'Model', 'Product_Catalog'

        Can be changed if the current name can be improved to better reflect the domain.""",
    ]

    # Optional fields
    description: Annotated[
        str | None,
        "A description of this semantic model, including details of what kind of analysis "
        "it's useful for. Can be changed if the current description can be improved.",
    ] = None
    tables: Annotated[list[LogicalTable] | None, "A list of logical tables in this semantic model"]


def create_semantic_data_model_for_llm_from_semantic_data_model(
    semantic_data_model: SemanticDataModel,
) -> SemanticDataModelForLLM:
    """
    Change the full semantic data model to a semantic data model just for the LLM generator to use.

    Changes are:
    - We don't need the full base table information.
    - Instead of `dimensions`/`facts`/`time_dimensions`/'metrics' we want to have `columns` which
      is a list of columns and each column has a `category` field which is the category of the
      column.
    - We don't need the `cortex_search_service` field.
    - We don't have the filters.
    - We use Pydantic instead of TypedDict.
    """
    import typing

    # Convert tables
    llm_tables = []
    tables = semantic_data_model.tables or []
    for table in tables:
        base_table = table.get("base_table")
        if not base_table:
            continue
        # Create simplified base table (only schema and table, no data_connection_id,
        # file_reference, database)
        base_table_name = base_table.get("table")
        if not base_table_name:
            continue

        table_name = table.get("name")
        if not table_name:
            continue

        base_table = BaseTable(schema=base_table.get("schema"), table=base_table_name)

        # Convert all column types to unified columns with categories
        all_columns = []

        # Convert dimensions
        for group in CATEGORY_TO_COLUMN_GROUP.values():
            columns_info = table.get(group) or []
            for item in columns_info:
                column = ColumnForLLM(
                    name=item.get("name"),
                    expr=item.get("expr"),
                    data_type=item.get("data_type"),
                    # Just remove the last `s` to make it compatible.
                    category=typing.cast(Category, group[:-1]),
                    synonyms=item.get("synonyms"),
                    description=item.get("description"),
                    unique=item.get("unique"),
                    sample_values=item.get("sample_values"),
                )
                all_columns.append(column)

        # Create logical table for LLM
        logical_table = LogicalTable(
            name=table_name,
            base_table=base_table,
            synonyms=table.get("synonyms"),
            description=table.get("description"),
            columns=sorted(all_columns, key=lambda x: x.name),
        )
        llm_tables.append(logical_table)

    # Create the semantic data model for LLM
    return SemanticDataModelForLLM(
        name=semantic_data_model.name or "",
        description=semantic_data_model.description,
        tables=llm_tables,
    )


class TablesOutputSchema(BaseModel):
    """A schema for a list of tables."""

    tables: Annotated[list[LogicalTableMetadataForLLM], "A list of logical tables in this semantic model"]


class TableToColumnsOutputSchema(BaseModel):
    """A schema for a dictionary of table names to columns."""

    table_to_columns: Annotated[dict[str, list[ColumnForLLM]], "A dictionary of table names to columns"]


LLMOutputSchemas = SemanticDataModelForLLM | TablesOutputSchema | TableToColumnsOutputSchema


def create_semantic_data_model_enhancement_tool() -> ToolDefinition:
    """Create a ToolDefinition for semantic data model enhancement (full mode).

    Returns:
        A ToolDefinition that the LLM can call to provide the enhanced semantic data model.
    """
    from agent_platform.core.tools.tool_definition import ToolDefinition

    return ToolDefinition(
        name="enhance_semantic_data_model",
        description=(
            "Provide the enhanced semantic data model with improved table names, descriptions, "
            "synonyms, and column categorization. Return the complete enhanced model including "
            "all tables and columns."
        ),
        input_schema=SemanticDataModelForLLM.model_json_schema(mode="serialization"),
        category="internal-tool",
    )


def create_tables_enhancement_tool() -> ToolDefinition:
    """Create a ToolDefinition for table metadata enhancement.

    Returns:
        A ToolDefinition that the LLM can call to provide enhanced table metadata.
    """
    from agent_platform.core.tools.tool_definition import ToolDefinition

    return ToolDefinition(
        name="enhance_tables",
        description=(
            "Provide the enhanced table metadata. Return a list of tables with improved names, "
            "descriptions, and synonyms. Do not include column information."
        ),
        input_schema=TablesOutputSchema.model_json_schema(mode="serialization"),
        category="internal-tool",
    )


def create_columns_enhancement_tool() -> ToolDefinition:
    """Create a ToolDefinition for column enhancement.

    Returns:
        A ToolDefinition that the LLM can call to provide enhanced column information.
    """
    from agent_platform.core.tools.tool_definition import ToolDefinition

    return ToolDefinition(
        name="enhance_columns",
        description=(
            "Provide the enhanced columns. Return a mapping of table names to lists of improved "
            "columns with better names, descriptions, synonyms, and categorization."
        ),
        input_schema=TableToColumnsOutputSchema.model_json_schema(mode="serialization"),
        category="internal-tool",
    )


def get_enhancement_tool(mode: EnhancementMode) -> ToolDefinition:
    """Get the appropriate enhancement tool for the given mode.

    Args:
        mode: The enhancement mode ("full", "tables", or "columns").

    Returns:
        The ToolDefinition for the specified mode.

    Raises:
        ValueError: If the mode is not recognized.
    """
    if mode == "full":
        return create_semantic_data_model_enhancement_tool()
    elif mode == "tables":
        return create_tables_enhancement_tool()
    elif mode == "columns":
        return create_columns_enhancement_tool()
    else:
        raise ValueError(f"Unknown enhancement mode: {mode}")


class QualityCheckResponse(BaseModel):
    """Quality check response for semantic data model enhancement."""

    passed: Annotated[
        bool,
        Field(description="Whether the enhancement quality check passed (True) or failed (False)."),
    ]

    improvement_request: Annotated[
        str | None,
        Field(
            description=(
                "If quality check failed, a detailed explanation of what needs to be improved. "
                "Required if passed=False, otherwise should be None."
            ),
            default=None,
        ),
    ]


def create_quality_check_tool() -> ToolDefinition:
    """Create a ToolDefinition for quality check responses.

    Returns:
        A ToolDefinition that the LLM can call to provide quality check feedback.
    """
    from agent_platform.core.tools.tool_definition import ToolDefinition

    return ToolDefinition(
        name="provide_quality_response",
        description=(
            "Provide feedback on whether the semantic data model enhancement meets "
            "quality standards. Set passed=true if the enhancements are sufficient, "
            "or passed=false with a detailed improvement_request if further "
            "improvements are needed."
        ),
        input_schema=QualityCheckResponse.model_json_schema(mode="serialization"),
        category="internal-tool",
    )
