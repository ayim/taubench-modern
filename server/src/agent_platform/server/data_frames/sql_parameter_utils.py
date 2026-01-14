"""Utilities for handling SQL query parameters in verified queries.

This module provides functions for:
- Extracting parameter placeholders from SQL queries
- Validating parameter definitions match SQL parameters

Note:
    This module only handles parameter extraction and validation. Parameter
    substitution and execution are not yet implemented. Parameterized verified
    queries cannot be executed at this time.

"""

from __future__ import annotations

from dataclasses import dataclass

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter


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
