"""Utilities for handling SQL query parameters in verified queries.

This module provides functions for:
- Extracting parameter placeholders from SQL queries
- Validating parameter definitions match SQL parameters
- Safely substituting parameters into SQL queries using sqlglot AST
  manipulation

"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, get_args

from agent_platform.core.semantic_data_model.types import (
    Dimension,
    Fact,
    Metric,
    QueryParameter,
    QueryParameterDataType,
    SemanticDataModel,
    TimeDimension,
)

if TYPE_CHECKING:
    from sqlglot import exp

# Type alias for parameter deduplication key
# (value, param_name) - ensures we only deduplicate when
# the same value appears in the same column context
type _ParameterKey = tuple[int | float | bool | str, str]


@dataclass(frozen=True)
class ExtractedParameter:
    """Parameter extracted from SQL with contextual information.

    This is used internally during parameterization to track both the parameter
    details and the source context (table and column names) from the SQL.
    """

    name: str
    """Parameter name used in SQL placeholder (e.g., 'country' for :country)"""

    data_type: QueryParameterDataType
    """Data type of the parameter"""

    example_value: str | int | float | bool | None
    """Example value extracted from the SQL literal"""

    base_column_name: str | None
    """The column name from SQL (e.g., 'country' from WHERE country = 'USA'), None for function-only contexts"""

    base_table_name: str | None
    """The table name from SQL if available (e.g., 'users' from users.id = 123)"""


def enrich_parameter_descriptions_from_sdm(
    parameters: list[ExtractedParameter],
    semantic_data_model: SemanticDataModel,
    alias_to_table: dict[str, str] | None = None,
) -> list[QueryParameter]:
    """Enrich parameter descriptions using column metadata from semantic data model.

    This function converts ExtractedParameters to QueryParameters, using the
    table and column context to find matching descriptions in the SDM.

    Only enriches descriptions when we have both table and column names for certainty.
    If table name is missing (unqualified column), the default description is used.

    Args:
        parameters: List of extracted parameters with SQL context
        semantic_data_model: Semantic data model containing table and column metadata
        alias_to_table: Optional mapping from table aliases to actual table names

    Returns:
        List of QueryParameters with enriched descriptions where possible
    """
    # Build a mapping from (table_name, column_name) to descriptions
    # Key is (table_name, column_name), value is description
    table_column_to_description: dict[tuple[str, str], str] = {}

    tables = semantic_data_model.tables or []

    for table in tables:
        table_name = table.get("name", "")

        # Helper function to process columns
        def process_columns(columns: Sequence[Dimension | TimeDimension | Fact | Metric] | None, tbl_name: str) -> None:
            if not columns:
                return
            for col in columns:
                col_name = col.get("name")
                description = col.get("description")
                if col_name and description:
                    # Store with table context
                    table_column_to_description[(tbl_name, col_name)] = description

        # Process all column types
        process_columns(table.get("dimensions"), table_name)
        process_columns(table.get("time_dimensions"), table_name)
        process_columns(table.get("facts"), table_name)
        process_columns(table.get("metrics"), table_name)

    # Convert ExtractedParameters to QueryParameters with enriched descriptions
    enriched_parameters = []

    for param in parameters:
        description = "Please provide description for this parameter"

        # Only enrich if we have both table and column names (absolute certainty)
        if param.base_table_name and param.base_column_name:
            # Resolve alias to actual table name if available
            actual_table_name = param.base_table_name
            if alias_to_table and param.base_table_name in alias_to_table:
                actual_table_name = alias_to_table[param.base_table_name]

            table_column_key = (actual_table_name, param.base_column_name)
            if table_column_key in table_column_to_description:
                description = table_column_to_description[table_column_key]

        # Create QueryParameter with enriched description
        query_param = QueryParameter(
            name=param.name,
            data_type=param.data_type,
            description=description,
            example_value=param.example_value,
        )
        enriched_parameters.append(query_param)

    return enriched_parameters


@dataclass(frozen=True)
class ParameterValidationResult:
    """Result of validating parameter definitions against SQL query.

    Note: Field-level validation (required fields, data_type validity,
    example_value matching) is done separately by Pydantic in
    verified_query_validator.py. This class only handles SQL matching
    validation (parameters in SQL vs definitions).
    """

    missing_in_definitions: list[str]
    """Parameters found in SQL but not in parameter definitions"""

    extra_in_definitions: list[str]
    """Parameters in definitions but not used in SQL"""


def validate_parameter_definitions(
    sql_query: str,
    parameters: list[QueryParameter],
    dialect: str,
) -> ParameterValidationResult:
    """Validate that parameter definitions match parameters in SQL.

    This function only validates SQL matching (parameters in SQL vs
    definitions). Field-level validation (required fields, data_type
    validity, example_value matching) should be done separately using
    Pydantic before calling this function.

    Args:
        sql_query: The SQL query with :param_name placeholders
        parameters: List of QueryParameter Pydantic models (field-validated)
        dialect: SQL dialect to use for parsing (e.g., 'postgres', 'mysql',
            'snowflake', 'redshift', 'databricks').

    Returns:
        ParameterValidationResult with SQL matching validation details
    """
    from agent_platform.core.semantic_data_model.utils import extract_parameters_from_sql

    # Extract parameters from SQL
    sql_param_names = set(extract_parameters_from_sql(sql_query, dialect=dialect))

    # Get defined parameter names from Pydantic models
    defined_param_names = {p.name for p in parameters if p.name}

    # Find mismatches
    missing_in_defs = sorted(sql_param_names - defined_param_names)
    extra_in_defs = sorted(defined_param_names - sql_param_names)

    return ParameterValidationResult(
        missing_in_definitions=missing_in_defs,
        extra_in_definitions=extra_in_defs,
    )


@dataclass(frozen=True)
class ParameterizationResult:
    """Result of parameterizing a SQL query.

    Contains the parameterized SQL query with constants replaced by named
    parameters, along with the extracted parameter definitions with context.
    """

    parameterized_sql: str
    """SQL query with constants replaced by :param_name placeholders"""

    parameters: list[ExtractedParameter]
    """List of extracted parameters with names, types, values, and SQL context"""

    alias_to_table: dict[str, str]
    """Mapping from table aliases to actual table names (for resolving aliases)"""


def _extract_column_from_expression(expr: exp.Expression) -> tuple[exp.Column | None, str | None]:
    """Recursively extract column and function name from an expression.

    Handles:
    - Direct columns: country → (Column, None)
    - Aggregate functions: sum(amount) → (Column, "sum"), count(*) → (None, "count")
    - Scalar functions: ROUND(price) → (Column, "round"), UPPER(name) → (Column, "upper")
    - Arithmetic expressions: price * 1.1 → (Column, None)

    Args:
        expr: Expression to search for columns and functions

    Returns:
        Tuple of (column_node, function_name) where both can be None
    """
    from sqlglot import exp

    # Direct column reference
    if isinstance(expr, exp.Column):
        return (expr, None)

    # Function calls (both aggregate and scalar) - capture function name
    if isinstance(expr, exp.Func):
        # Get the function name from the class name
        func_name = type(expr).__name__.lower()  # "Round" -> "round", "Sum" -> "sum"

        # Try to find a column inside the function
        for child in expr.iter_expressions():
            if isinstance(child, exp.Column):
                return (child, func_name)

        # No column found (e.g., count(*), NOW()) - return function name only
        return (None, func_name)

    # For other expressions (arithmetic, etc.), find column recursively
    for child in expr.iter_expressions():
        if isinstance(child, exp.Column):
            return (child, None)

    return (None, None)


def _extract_column_and_table_from_node(node: exp.Expression) -> tuple[str | None, str | None, str | None] | None:
    """Extract column name, table name, and function name from AST node.

    Tries to find the column/function being compared in the SQL expression.
    Returns None if no context is found (indicating the literal should not
    be parameterized, e.g., function arguments like ROUND(x, 2)).

    Supports:
    - Direct column comparisons: WHERE country = 'USA' → ("country", None, None)
    - Aggregate comparisons: HAVING sum(amount) > 1000 → ("amount", None, "sum")
    - Aggregate without column: HAVING count(*) > 10 → (None, None, "count")
    - Scalar function comparisons: WHERE ROUND(price) > 100 → ("price", None, "round")
    - Expression comparisons: WHERE price * 1.1 > 100 → ("price", None, None)

    Args:
        node: The AST node (literal or boolean)

    Returns:
        Tuple of (column_name, table_name, function_name) where all can be None.
        Returns None if the literal should not be parameterized.
        At least one of column_name or function_name must be non-None for a
        valid result. Both names are returned as-is from the SQL.
    """
    from sqlglot import exp

    # Try to find the column/function being compared
    # Walk up the parent chain to find comparison or predicate
    parent = node.parent
    column_node = None
    function_name = None

    # Look for comparison operations (=, >, <, >=, <=, !=, etc.)
    if parent and isinstance(
        parent,
        exp.EQ | exp.GT | exp.LT | exp.GTE | exp.LTE | exp.NEQ | exp.Like,
    ):
        # Get the other side of the comparison
        for child in parent.args.values():
            if child != node:
                column_node, function_name = _extract_column_from_expression(child)
                if column_node or function_name:
                    break

    # Look for IN clause: column IN (value1, value2, ...)
    # Literals in IN clauses are wrapped in Tuple -> In structure
    if not column_node and not function_name:
        current = parent
        # Walk up to find In node (might be through Tuple or other wrappers)
        while current and not isinstance(current, exp.In):
            current = current.parent
            if not current:
                break

        if current and isinstance(current, exp.In):
            # Extract column/function from the IN expression
            column_node, function_name = _extract_column_from_expression(current.this)

    # Look for BETWEEN clause: column BETWEEN value1 AND value2
    if not column_node and not function_name and parent and isinstance(parent, exp.Between):
        column_node, function_name = _extract_column_from_expression(parent.this)

    # Extract column name and table if we have a column node
    column_name = None
    table_name = None
    if column_node:
        column_name = column_node.name
        table_name = column_node.table if hasattr(column_node, "table") and column_node.table else None

    # Return if we have at least column or function context
    if column_name or function_name:
        return (column_name, table_name, function_name)

    # No column or function context found - this literal is likely a function
    # argument or other structural parameter that shouldn't be parameterized
    return None


def _make_param_name(column_name: str | None, function_name: str | None = None) -> str:
    """Convert a column name and/or function name to a valid parameter name.

    Generates parameter names based on available context:
    - Column + Function: sum(revenue) → "sum_revenue"
    - Function only: count(*) → "count"
    - Column only: country → "country"

    Cleans names using slugify and ensures valid identifiers.

    Args:
        column_name: The column name from SQL (can be None)
        function_name: The function name from SQL (can be None)

    Returns:
        A valid parameter name (slugified, no leading numbers)

    Raises:
        ValueError: If both column_name and function_name are None
    """
    from sema4ai.common.text import slugify

    if not column_name and not function_name:
        raise ValueError("At least one of column_name or function_name must be provided")

    # Build the parameter name
    if function_name and column_name:
        # Both available: combine them (e.g., "sum_revenue")
        base_name = f"{function_name}_{column_name}"
    elif function_name:
        # Function only (e.g., "count" from count(*))
        base_name = function_name
    else:
        # Column only (e.g., "country")
        base_name = column_name

    # At this point, base_name is guaranteed to be str due to the check above
    assert base_name is not None, "base_name should not be None after validation"

    # Clean up the name using slugify and replace hyphens with underscores
    # slugify handles unicode, special chars, and lowercasing
    param_name = slugify(base_name).replace("-", "_")

    # Ensure it doesn't start with a number
    if param_name and param_name[0].isdigit():
        param_name = f"param_{param_name}"

    return param_name


def _is_datetime_string(value: str) -> bool:
    """Check if a string value looks like a datetime.

    Uses actual datetime parsing rather than regex patterns.
    Conservative approach - only returns True if we're confident it's a date.

    Args:
        value: The string to check

    Returns:
        True if the string can be parsed as a datetime, False otherwise
    """
    from datetime import datetime

    # Only consider strings that look like dates (start with digits)
    if not value or not value[0].isdigit():
        return False

    # Try common datetime formats
    datetime_formats = [
        "%Y-%m-%d",  # 2021-01-01
        "%Y-%m-%d %H:%M:%S",  # 2021-01-01 12:30:45
        "%Y-%m-%dT%H:%M:%S",  # 2021-01-01T12:30:45 (ISO)
        "%Y-%m-%dT%H:%M:%S.%f",  # 2021-01-01T12:30:45.123456
        "%Y/%m/%d",  # 2021/01/01
        "%m/%d/%Y",  # 01/01/2021
        "%d/%m/%Y",  # 01/01/2021
    ]

    for fmt in datetime_formats:
        try:
            datetime.strptime(value, fmt)
            return True
        except (ValueError, TypeError):
            continue

    # Try ISO format parsing (handles timezone info)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        pass

    return False


def _infer_parameter_type_and_value(
    node: exp.Expression,
) -> tuple[QueryParameterDataType, int | float | bool | str] | None:
    """Infer parameter type and value from a literal or boolean node.

    Args:
        node: AST node (exp.Literal or exp.Boolean)

    Returns:
        Tuple of (param_type, param_value) or None only if string conversion
        fails. Unrecognized literal types and errors default to string type.
    """
    from sqlglot import exp
    from structlog import get_logger

    logger = get_logger(__name__)

    try:
        if isinstance(node, exp.Boolean):
            # Handle boolean literals (TRUE/FALSE)
            return ("boolean", node.this)

        if isinstance(node, exp.Literal):
            # Check if it's a number
            if node.is_number:
                # Try to determine if it's integer or float
                try:
                    int_value = int(node.this)
                    float_value = float(node.this)
                    # If converting to int and back to float equals the
                    # original, it's an integer
                    if float_value == int_value:
                        return ("integer", int_value)
                    else:
                        return ("float", float_value)
                except (ValueError, TypeError):
                    # If conversion fails, default to float
                    return ("float", float(node.this))
            elif node.is_string:
                # Check if the string looks like a datetime
                param_value = str(node.this)
                if _is_datetime_string(param_value):
                    return ("datetime", param_value)
                else:
                    return ("string", param_value)
            else:
                # Other literal types (dates, timestamps, etc.)
                # Try to detect if it's a datetime
                param_value = str(node.this)
                if _is_datetime_string(param_value):
                    return ("datetime", param_value)
                else:
                    return ("string", param_value)

        # Fallback for any other expression type - treat as string
        return ("string", str(node.this))
    except Exception as e:
        # If any unexpected error occurs during type inference, default to
        # string type to allow parameterization to continue
        logger.debug(
            "Failed to infer parameter type from AST node, defaulting to string",
            error=str(e),
            error_type=type(e).__name__,
            node_type=type(node).__name__,
        )
        try:
            return ("string", str(node.this))
        except Exception:
            # If even string conversion fails, skip this literal
            return None


def _create_and_add_parameter(
    node: exp.Expression,
    value_to_param: dict[_ParameterKey, ExtractedParameter],
) -> str | None:
    """Create and add a parameter from an AST node with deduplication.

    This function combines type inference, name generation, and deduplication
    into a single operation. It will:
    1. Infer the parameter type and value from the node
    2. Generate a base parameter name from column and/or function context
    3. Check if this (value, base_name) combination already exists
    4. If yes, reuse the existing parameter name
    5. If no, add a suffix if base_name is taken, then create new parameter
    6. Return the parameter name to use for the placeholder

    Parameter names are generated based on context:
    - Column comparison: WHERE country = 'USA' → :country
    - Function comparison: HAVING count(*) > 10 → :count
    - Combined: HAVING sum(revenue) > 1000 → :sum_revenue
    - Scalar function: WHERE ROUND(price) > 100 → :round_price

    Args:
        node: The AST node (literal or boolean)
        value_to_param: Deduplication map keyed by (value, param_name)

    Returns:
        Parameter name to use for placeholder, or None if the literal
        should not be parameterized (e.g., function arguments like
        ROUND(price, 2) where 2 is the precision argument, not a filter value)
    """
    from structlog import get_logger

    logger = get_logger(__name__)

    try:
        # Infer parameter type and value from the node
        type_and_value = _infer_parameter_type_and_value(node)
        if type_and_value is None:
            return None

        param_type, param_value = type_and_value

        # Extract column, table, and function names from SQL AST
        column_table_function = _extract_column_and_table_from_node(node)

        # If no column or function context found, skip this literal
        # (it's likely a function argument or structural value)
        if column_table_function is None:
            return None

        base_column_name, base_table_name, function_name = column_table_function

        # Convert column and/or function name to a valid parameter name
        base_param_name = _make_param_name(base_column_name, function_name)

        # First, check if this exact (value, base_name) already exists
        # This handles deduplication: same value in same column context
        base_dedup_key: _ParameterKey = (param_value, base_param_name)
        if base_dedup_key in value_to_param:
            # Already exists - reuse the existing parameter name
            return value_to_param[base_dedup_key].name

        # Not a duplicate - need to create a new parameter
        # Check if base_param_name is already used for a DIFFERENT value
        used_param_names = {param.name for param in value_to_param.values()}

        param_name = base_param_name
        suffix = 1
        while param_name in used_param_names:
            param_name = f"{base_param_name}_{suffix}"
            suffix += 1

        # Resolve table alias to actual table name if available
        # This is done at enrichment time, so we store the raw table name/alias here
        parameter = ExtractedParameter(
            name=param_name,
            data_type=param_type,
            example_value=param_value,
            base_column_name=base_column_name,
            base_table_name=base_table_name,  # May be alias, resolved during enrichment
        )

        # Store with dedup key using the FINAL param_name
        final_dedup_key: _ParameterKey = (param_value, param_name)
        value_to_param[final_dedup_key] = parameter

        return param_name
    except Exception as e:
        # If any error occurs during parameter creation, skip this literal
        logger.debug(
            "Failed to create parameter from AST node, skipping",
            error=str(e),
            error_type=type(e).__name__,
            node_type=type(node).__name__,
        )
        return None


def _standardize_placeholder_format(parameterized_sql: str, dialect: str, parameter_names: list[str]) -> str:
    """Convert dialect-specific placeholder formats to :param format.

    When sqlglot generates SQL with placeholders, it uses dialect-specific
    formats:
    - Postgres/Redshift/TimescaleDB/Pgvector: %(param)s (psycopg2 format)
    - BigQuery: @param
    - DuckDB: $param
    - Snowflake/MySQL/Oracle/SQLite/Databricks: :param (already standard)

    This function standardizes all formats to :param for consistency by
    performing precise string replacements based on dialect-specific formats.

    Args:
        parameterized_sql: SQL with dialect-specific placeholders
        dialect: SQL dialect name
        parameter_names: List of parameter names that were extracted

    Returns:
        SQL with standardized :param placeholders
    """
    # Dialects that already use :param format don't need conversion
    if dialect in ("snowflake", "mysql", "oracle", "sqlite", "databricks"):
        return parameterized_sql

    # If no parameters, nothing to convert
    if not parameter_names:
        return parameterized_sql

    # Sort parameter names by length (longest first) to avoid
    # partial replacements when names overlap (e.g., @param and @param_1)
    sorted_names = sorted(parameter_names, key=len, reverse=True)

    # Determine the placeholder format template based on dialect
    placeholder_template: str | None = None

    if dialect in ("postgres", "redshift", "timescaledb", "pgvector"):
        placeholder_template = "%({param_name})s"
    elif dialect == "bigquery":
        placeholder_template = "@{param_name}"
    elif dialect == "duckdb":
        placeholder_template = "${param_name}"

    # If no template defined, dialect doesn't need conversion
    if placeholder_template is None:
        return parameterized_sql

    # Convert each placeholder based on dialect-specific format
    result = parameterized_sql
    for param_name in sorted_names:
        old_format = placeholder_template.format(param_name=param_name)
        new_format = f":{param_name}"
        result = result.replace(old_format, new_format)

    return result


def _build_alias_to_table_mapping(sql_ast: exp.Expression) -> dict[str, str]:
    """Build a mapping from table aliases to actual table names.

    Args:
        sql_ast: Parsed SQL AST

    Returns:
        Dictionary mapping alias -> actual table name
    """
    from sqlglot import exp

    alias_to_table: dict[str, str] = {}

    # Find all Table nodes with aliases
    for table_node in sql_ast.find_all(exp.Table):
        table_name = table_node.name
        alias = table_node.alias

        if alias and table_name:
            alias_to_table[alias] = table_name

    return alias_to_table


def parameterize_sql_query(
    sql_query: str,
    dialect: str,
) -> ParameterizationResult:
    """Extract constants from SQL query and convert to parameterized query.

    This function analyzes a SQL query, identifies all literal constants
    (numbers, strings, booleans, dates), and replaces them with named
    parameter placeholders. It returns both the parameterized query and
    the parameter definitions with inferred types.

    Parameter names are generated based on the comparison context:
    - Column comparisons: WHERE country = 'USA' → :country
    - Aggregate functions: HAVING sum(revenue) > 1000 → :sum_revenue
    - Aggregate without column: HAVING count(*) > 10 → :count
    - Scalar functions: WHERE ROUND(price) > 100 → :round_price
    - Arithmetic expressions: WHERE price * 1.1 > 100 → :price

    Literals that are NOT parameterized:
    - Function arguments: ROUND(price, 2) - the 2 remains literal
    - CASE THEN/ELSE values: CASE WHEN age < 18 THEN 'minor' - 'minor' remains literal
    - SELECT list literals: SELECT 'constant' - remains literal
    - NULL values: WHERE col IS NULL - remains literal

    Args:
        sql_query: The SQL query to parameterize
        dialect: SQL dialect to use for parsing (e.g., 'postgres', 'mysql',
            'snowflake', 'redshift', 'databricks')

    Returns:
        ParameterizationResult containing the parameterized SQL and
        parameter definitions

    Raises:
        ValueError: If SQL parsing fails, AST manipulation fails, or SQL
            regeneration fails

    Examples:
        Basic WHERE clause:
        >>> result = parameterize_sql_query(
        ...     "SELECT * FROM users WHERE id = 123 AND name = 'John'",
        ...     dialect="postgres"
        ... )
        >>> result.parameterized_sql
        "SELECT * FROM users WHERE id = :id AND name = :name"
        >>> len(result.parameters)
        2
        >>> result.parameters[0].name
        'id'
        >>> result.parameters[1].name
        'name'

        HAVING with aggregates:
        >>> result = parameterize_sql_query(
        ...     "SELECT country, sum(revenue) FROM sales GROUP BY country HAVING sum(revenue) > 1000",
        ...     dialect="postgres"
        ... )
        >>> result.parameters[0].name
        'sum_revenue'
    """
    import sqlglot
    from sqlglot import exp
    from structlog import get_logger

    logger = get_logger(__name__)

    # Parse SQL into AST
    expressions = sqlglot.parse(sql_query, dialect=dialect)
    if not expressions or not expressions[0]:
        raise ValueError(f"Failed to parse SQL query: {sql_query!r}")

    sql_ast = expressions[0]

    # Build alias to table name mapping (will be used during enrichment)
    alias_to_table = _build_alias_to_table_mapping(sql_ast)

    # Track extracted parameters and deduplicate by (value, param_name)
    value_to_param: dict[_ParameterKey, ExtractedParameter] = {}

    # Store alias mapping for later use during enrichment
    # We'll attach it to the result

    # Find all literal and boolean nodes in the AST using find_all
    # Process both Literal nodes (strings, numbers, dates) and Boolean nodes
    for node in sql_ast.find_all(
        (exp.Literal, exp.Boolean)  # type: ignore[arg-type]
    ):
        try:
            # Create and add parameter (with deduplication)
            param_name = _create_and_add_parameter(node, value_to_param)

            # Skip if this literal should not be parameterized
            if param_name is None:
                continue

            # Replace the node with a placeholder in the AST
            placeholder = exp.Placeholder(this=param_name)
            node.replace(placeholder)
        except Exception as e:
            # If processing this literal fails, log and skip it
            # This allows partial parameterization even if some
            # literals cause issues
            logger.warning(
                "Failed to parameterize literal in SQL query, skipping",
                error=str(e),
                error_type=type(e).__name__,
                node_type=type(node).__name__,
            )
            continue

    # Generate parameterized SQL from the modified AST
    # Must pass dialect to preserve dialect-specific SQL syntax
    parameterized_sql = sql_ast.sql(dialect=dialect, pretty=True)

    # Extract parameters from the deduplication map
    parameters = list(value_to_param.values())

    # Get parameter names for placeholder standardization
    parameter_names = [p.name for p in parameters]

    # Standardize placeholder format to :param across all dialects
    # This is safe because we control the input (we just generated it)
    parameterized_sql = _standardize_placeholder_format(parameterized_sql, dialect, parameter_names)

    return ParameterizationResult(
        parameterized_sql=parameterized_sql,
        parameters=parameters,
        alias_to_table=alias_to_table,
    )


def substitute_sql_parameters_safe(
    sql: str,
    param_values: dict[str, int | float | bool | str],
    param_definitions: list[QueryParameter],
    dialect: str,
) -> str:
    """Safely substitute parameters in SQL using sqlglot AST manipulation.

    This function uses sqlglot to parse the SQL, locate parameter
    placeholders, and replace them with properly escaped and typed literal
    values. This provides protection against SQL injection and handles
    dialect-specific quoting rules.

    IMPORTANT: All required parameters must be explicitly provided in
    param_values. The example_value in parameter definitions is NOT used as
    a default. Extra parameters in param_values (not in param_definitions)
    are silently ignored.

    Args:
        sql: SQL query with :param_name placeholders
        param_values: Dictionary of parameter names to typed values
            (int, float, bool, or str only). Extra parameters not defined
            in param_definitions are ignored.
        param_definitions: List of parameter definitions with types
        dialect: SQL dialect (postgres, mysql, snowflake, etc.)

    Returns:
        SQL with parameters safely substituted

    Raises:
        ValueError: If required parameters are missing, type conversion
            fails, or parameter type is invalid

    Examples:
        >>> param_defs = [
        ...     QueryParameter(
        ...         name="user_id",
        ...         data_type="integer",
        ...         description="User ID"
        ...     )
        ... ]
        >>> substitute_sql_parameters_safe(
        ...     "SELECT * FROM users WHERE id = :user_id",
        ...     {"user_id": 456},
        ...     param_defs,
        ...     "postgres"
        ... )
        'SELECT * FROM users WHERE id = 456'

        >>> # Multiple occurrences of same parameter are all replaced
        >>> substitute_sql_parameters_safe(
        ...     "SELECT * FROM users WHERE id = :user_id OR "
        ...     "parent_id = :user_id",
        ...     {"user_id": 456},
        ...     param_defs,
        ...     "postgres"
        ... )
        'SELECT * FROM users WHERE id = 456 OR parent_id = 456'
    """
    import sqlglot
    from sqlglot import exp
    from sqlglot.errors import ParseError

    # Build parameter type map
    param_type_map = {p.name: p.data_type for p in param_definitions}
    param_name_set = {p.name for p in param_definitions}

    # Validate all required parameters are provided
    # NO fallback to example_value - all parameters must be explicitly
    # provided
    missing_params = param_name_set - set(param_values.keys())
    if missing_params:
        raise ValueError(
            f"Required parameter(s) not provided: "
            f"{', '.join(sorted(missing_params))}. "
            f"All parameters must be explicitly provided."
        )

    # Note: Extra parameters in param_values are silently ignored.
    # Only parameters defined in param_definitions are used for substitution.

    # Parse SQL into AST
    try:
        expressions = sqlglot.parse(sql, dialect=dialect)
    except ParseError as e:
        raise ValueError(f"Failed to parse SQL query for parameter substitution: {e}") from e

    if not expressions or not expressions[0]:
        raise ValueError("Failed to parse SQL query")

    sql_ast = expressions[0]

    # Find and replace all parameter placeholders
    # NOTE: If a parameter appears multiple times in SQL (e.g., :user_id
    # appears twice), find_all returns all occurrences and we replace each
    # one with the same value.
    for placeholder in sql_ast.find_all(exp.Placeholder):
        param_name = placeholder.this

        # Validate parameter is defined
        if param_name not in param_name_set:
            raise ValueError(
                f"Parameter '{param_name}' found in SQL but not in "
                f"parameter definitions. "
                f"Defined parameters: {', '.join(sorted(param_name_set))}"
            )

        # Validate parameter value is provided
        if param_name not in param_values:
            raise ValueError(
                f"Parameter '{param_name}' found in SQL but value not "
                f"provided. Required parameters must be explicitly provided."
            )

        param_value = param_values[param_name]
        # Must exist due to validation above
        param_type = param_type_map[param_name]

        # Validate param_type is consistent with QueryParameterDataType
        # This ensures we stay in sync with the core type definition
        valid_types = get_args(QueryParameterDataType)
        if param_type not in valid_types:
            raise ValueError(
                f"Invalid parameter type '{param_type}' for parameter "
                f"'{param_name}'. Must be one of: {', '.join(valid_types)}"
            )

        # Convert and validate parameter value based on type
        # Use match/case for clear type handling
        try:
            match param_type:
                case "integer":
                    typed_value = int(param_value)
                    literal = exp.Literal.number(typed_value)
                case "float":
                    typed_value = float(param_value)
                    literal = exp.Literal.number(typed_value)
                case "boolean":
                    typed_value = bool(param_value)
                    literal = exp.Boolean(this=typed_value)
                case "string":
                    typed_value = str(param_value)
                    literal = exp.Literal.string(typed_value)
                case "datetime":
                    # For datetime, keep as string and let database parse it
                    # sqlglot will properly quote it
                    typed_value = str(param_value)
                    literal = exp.Literal.string(typed_value)
                case _:
                    # This should never happen due to validation above, but
                    # keeping for safety
                    raise ValueError(
                        f"Unsupported parameter type '{param_type}' for "
                        f"parameter '{param_name}'. Must be one of: "
                        f"{', '.join(valid_types)}"
                    )

        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to convert parameter '{param_name}' with value {param_value!r} to type '{param_type}': {e}"
            ) from e

        # Replace the placeholder node with the literal in the AST
        placeholder.replace(literal)

    # Generate SQL from the modified AST
    # This will have all parameters replaced with properly escaped values
    substituted_sql = sql_ast.sql(dialect=dialect, pretty=False)

    return substituted_sql
