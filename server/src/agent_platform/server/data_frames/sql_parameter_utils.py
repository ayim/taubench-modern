"""Utilities for handling SQL query parameters in verified queries.

This module provides functions for:
- Extracting parameter placeholders from SQL queries
- Validating parameter definitions match SQL parameters
- Safely substituting parameters into SQL queries using sqlglot AST manipulation

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from agent_platform.core.data_frames.semantic_data_model_types import (
    QueryParameter,
    QueryParameterDataType,
)


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


def extract_parameters_from_sql(
    sql_query: str,
    dialect: str,
) -> list[str]:
    """Extract :param_name placeholders from SQL query using sqlglot AST.

    Detects parameters in the format :param_name (named parameters) by parsing
    the SQL query into an AST and walking it to find parameter placeholders.

    Args:
        sql_query: The SQL query to analyze
        dialect: SQL dialect to use for parsing (e.g., 'postgres', 'mysql',
            'snowflake', 'redshift', 'databricks').

    Returns:
        Sorted list of unique parameter names found in the query

    Raises:
        ValueError: If SQL parsing fails

    Examples:
        >>> extract_parameters_from_sql(
        ...     "SELECT * FROM users WHERE id = :user_id",
        ...     dialect="postgres"
        ... )
        ['user_id']

        >>> extract_parameters_from_sql(
        ...     "SELECT * FROM orders WHERE date >= :start_date "
        ...     "AND date <= :end_date",
        ...     dialect="postgres"
        ... )
        ['end_date', 'start_date']
    """
    import sqlglot
    from sqlglot import exp
    from sqlglot.errors import ParseError

    # Parse SQL into AST
    try:
        expressions = sqlglot.parse(sql_query, dialect=dialect)
    except ParseError as e:
        raise ValueError(f"Failed to parse SQL query: {sql_query!r}") from e

    if not expressions or not expressions[0]:
        raise ValueError(f"Failed to parse SQL query: {sql_query!r}")

    sql_ast = expressions[0]

    # sqlglot parses :param_name as Placeholder nodes
    # For named placeholders, the 'this' attribute contains the parameter name as a string
    # Only named placeholders are supported (e.g., :param_name)
    param_names = {placeholder.this for placeholder in sql_ast.find_all(exp.Placeholder)}

    return sorted(param_names)


def validate_parameter_definitions(
    sql_query: str,
    parameters: list[QueryParameter],
    dialect: str,
) -> ParameterValidationResult:
    """Validate that parameter definitions match parameters in SQL.

    This function only validates SQL matching (parameters in SQL vs definitions).
    Field-level validation (required fields, data_type validity, example_value
    matching) should be done separately using Pydantic before calling this function.

    Args:
        sql_query: The SQL query with :param_name placeholders
        parameters: List of QueryParameter Pydantic models (field-validated)
        dialect: SQL dialect to use for parsing (e.g., 'postgres', 'mysql',
            'snowflake', 'redshift', 'databricks').

    Returns:
        ParameterValidationResult with SQL matching validation details
    """
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


def substitute_sql_parameters_safe(
    sql: str,
    param_values: dict[str, int | float | bool | str],
    param_definitions: list[QueryParameter],
    dialect: str,
) -> str:
    """Safely substitute parameters in SQL using sqlglot AST manipulation.

    This function uses sqlglot to parse the SQL, locate parameter placeholders,
    and replace them with properly escaped and typed literal values. This provides
    protection against SQL injection and handles dialect-specific quoting rules.

    IMPORTANT: All required parameters must be explicitly provided in param_values.
    The example_value in parameter definitions is NOT used as a default.
    Extra parameters in param_values (not in param_definitions) are silently ignored.

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
        ValueError: If required parameters are missing, type conversion fails,
            or parameter type is invalid

    Examples:
        >>> param_defs = [
        ...     QueryParameter(name="user_id", data_type="integer", description="User ID")
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
        ...     "SELECT * FROM users WHERE id = :user_id OR parent_id = :user_id",
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
    # NO fallback to example_value - all parameters must be explicitly provided
    missing_params = param_name_set - set(param_values.keys())
    if missing_params:
        raise ValueError(
            f"Required parameter(s) not provided: {', '.join(sorted(missing_params))}. "
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
    # NOTE: If a parameter appears multiple times in SQL (e.g., :user_id appears twice),
    # find_all returns all occurrences and we replace each one with the same value.
    for placeholder in sql_ast.find_all(exp.Placeholder):
        param_name = placeholder.this

        # Validate parameter is defined
        if param_name not in param_name_set:
            raise ValueError(
                f"Parameter '{param_name}' found in SQL but not in parameter definitions. "
                f"Defined parameters: {', '.join(sorted(param_name_set))}"
            )

        # Validate parameter value is provided
        if param_name not in param_values:
            raise ValueError(
                f"Parameter '{param_name}' found in SQL but value not provided. "
                f"Required parameters must be explicitly provided."
            )

        param_value = param_values[param_name]
        param_type = param_type_map[param_name]  # Must exist due to validation above

        # Validate param_type is consistent with QueryParameterDataType
        # This ensures we stay in sync with the core type definition
        valid_types = get_args(QueryParameterDataType)
        if param_type not in valid_types:
            raise ValueError(
                f"Invalid parameter type '{param_type}' for parameter '{param_name}'. "
                f"Must be one of: {', '.join(valid_types)}"
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
                    # This should never happen due to validation above, but keeping for safety
                    raise ValueError(
                        f"Unsupported parameter type '{param_type}' for parameter '{param_name}'. "
                        f"Must be one of: {', '.join(valid_types)}"
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
