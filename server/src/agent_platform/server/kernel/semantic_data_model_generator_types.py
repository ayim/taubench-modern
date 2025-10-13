"""Semantic model data structures for as we want the LLM generator to see it."""

import warnings
from types import NoneType
from typing import Annotated, Literal

import yaml
from pydantic.fields import Field
from pydantic.main import BaseModel

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel


class Column(BaseModel):
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
        Literal["dimension", "fact", "metric", "time_dimension"] | None,
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

    schema: str | None = Field(
        alias="schema", description="Name of the schema. MUST NOT be changed.", default=None
    )

    table: Annotated[
        str,
        "The real name of the table. MUST NOT be changed.",
    ]


class LogicalTable(BaseModel):
    """A logical table represents a view over a physical database table or view."""

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
    columns: Annotated[
        list[Column] | None,
        "A list of columns in this table with their categories (dimension, fact, metric, "
        "time_dimension).",
    ] = None


class SemanticDataModelForLLM(BaseModel):
    """A semantic model represents a collection of tables with their relationships."""

    # Required fields
    name: Annotated[
        str,
        """A descriptive name for this semantic model. Must be unique and follow the
        unquoted identifiers requirements. It also cannot conflict with SQL reserved
        keywords. Can be changed if the current name can be improved.""",
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
    tables = semantic_data_model.get("tables") or []
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
        groups: list[Literal["dimensions", "facts", "time_dimensions", "metrics"]] = [
            "dimensions",
            "facts",
            "time_dimensions",
            "metrics",
        ]

        for group in groups:
            columns_info = table.get(group) or []
            for item in columns_info:
                column = Column(
                    name=item.get("name"),
                    expr=item.get("expr"),
                    data_type=item.get("data_type"),
                    # Just remove the last `s` to make it compatible.
                    category=typing.cast(
                        Literal["dimension", "fact", "time_dimension", "metric"], group[:-1]
                    ),
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
        name=semantic_data_model.get("name") or "",
        description=semantic_data_model.get("description"),
        tables=llm_tables,
    )


def update_semantic_data_model_with_semantic_data_model_from_llm(  # noqa: PLR0912, C901
    semantic_data_model: SemanticDataModel,
    semantic_data_model_for_llm: SemanticDataModelForLLM,
) -> None:
    """
    Update the semantic data model with the semantic data model for LLM.

    We should go over the changes and update the references in the existing semantic data model.

    The references are:
    - A table should be referenced by the `base_table.schema` and `base_table.table` fields to
      update the synonyms, description and name accordingly.
    - A column should be referenced by the table + the `expr` field to update accordingly.
    - A table may be moved from one group (dimensions, facts, time_dimensions, metrics) to another
      based on the category found for the column.

    While doing this we should also collect possible errors in a list.

    Some possible errors are:
    - If a table in semantic_data_model_for_llm does not have a reference, we should add an error
      saying so (and skip it).
    - If a column in semantic_data_model_for_llm does not have a reference, we should add an error
      saying so (and skip it).

    At the end, we should not have any additional tables or columns (but all existing ones
    should be updated and put in the correct group).
    """
    errors = []

    # Update semantic model name and description
    if semantic_data_model_for_llm.name:
        semantic_data_model["name"] = semantic_data_model_for_llm.name
    if semantic_data_model_for_llm.description is not None:
        semantic_data_model["description"] = semantic_data_model_for_llm.description

    # Get existing tables from the semantic data model
    existing_tables = semantic_data_model.get("tables") or []

    # Create a mapping of (schema, table) -> existing table for quick lookup
    existing_table_map = {}
    for table in existing_tables:
        base_table = table.get("base_table", {})
        schema = base_table.get("schema")
        table_name = base_table.get("table")
        if table_name:
            key = (schema, table_name)
            existing_table_map[key] = table

    # Process each table from the LLM model
    llm_tables = semantic_data_model_for_llm.tables or []
    for llm_table in llm_tables:
        base_table = llm_table.base_table
        schema = base_table.schema
        table_name = base_table.table

        # Find the corresponding existing table
        key = (schema, table_name)
        existing_table = existing_table_map.get(key)

        if not existing_table:
            errors.append(
                f"Table with schema '{schema}' and table '{table_name}' "
                "not found in existing semantic data model"
            )
            continue

        # Update table properties
        if llm_table.name:
            existing_table["name"] = llm_table.name
        if llm_table.description is not None:
            existing_table["description"] = llm_table.description
        if llm_table.synonyms is not None:
            existing_table["synonyms"] = llm_table.synonyms

        # Process columns from the LLM model
        if llm_table.columns:
            _update_table_columns(existing_table, llm_table.columns, errors)

    # Check for tables in LLM model that weren't found in existing model
    llm_table_keys = set()
    for llm_table in llm_tables:
        base_table = llm_table.base_table
        key = (base_table.schema, base_table.table)
        llm_table_keys.add(key)

    # Report any tables that were in LLM model but not found in existing model
    for key in llm_table_keys:
        if key not in existing_table_map:
            schema, table_name = key
            errors.append(
                f"Table with schema '{schema}' and table '{table_name}' from LLM model "
                "not found in existing semantic data model"
            )


def _update_table_columns(existing_table: dict, llm_columns: list[Column], errors: list) -> None:  # noqa: PLR0912, C901
    """Update table columns based on LLM model columns."""
    # Get all existing columns from all groups
    all_existing_columns = []
    column_groups = ["dimensions", "facts", "time_dimensions", "metrics"]

    for group in column_groups:
        columns = existing_table.get(group) or []
        for col in columns:
            col["_group"] = group  # Track which group it came from
            all_existing_columns.append(col)

    # Create a mapping of (expr) -> existing column for quick lookup
    existing_column_map = {}
    for col in all_existing_columns:
        expr = col.get("expr")
        if expr:
            existing_column_map[expr] = col

    # Process each column from the LLM model
    for llm_column in llm_columns:
        expr = llm_column.expr

        # Find the corresponding existing column
        existing_column = existing_column_map.get(expr)

        if not existing_column:
            errors.append(f"Column with expr '{expr}' not found in existing semantic data model")
            continue

        # Update column properties
        if llm_column.name:
            existing_column["name"] = llm_column.name
        if llm_column.description is not None:
            existing_column["description"] = llm_column.description
        if llm_column.synonyms is not None:
            existing_column["synonyms"] = llm_column.synonyms

        # Check if column needs to be moved to a different group based on category
        current_group = existing_column.get("_group")
        target_group = _get_target_group_for_category(llm_column.category)

        if current_group != target_group:
            # Remove from current group
            current_group_columns = existing_table.get(current_group, [])
            current_group_columns.remove(existing_column)

            # Add to target group
            if target_group not in existing_table:
                existing_table[target_group] = []
            existing_table[target_group].append(existing_column)

    # Remove the temporary _group field
    for column in all_existing_columns:
        column.pop("_group", None)

    # Clean up empty groups
    for group in column_groups:
        if group in existing_table and not existing_table[group]:
            del existing_table[group]


def _get_target_group_for_category(category: str | None) -> str:
    """Get the target group name for a given category."""
    if category is None:
        return "dimensions"
    category_to_group = {
        "dimension": "dimensions",
        "fact": "facts",
        "time_dimension": "time_dimensions",
        "metric": "metrics",
    }
    return category_to_group.get(category, "dimensions")


OUTPUT_SCHEMA_FORMAT: str = yaml.dump(
    SemanticDataModelForLLM.model_json_schema(mode="serialization"),
    default_flow_style=False,
    sort_keys=False,
)
