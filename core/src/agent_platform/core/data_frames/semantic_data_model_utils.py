from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter


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
    # For named placeholders, the 'this' attribute contains the parameter
    # name as a string. Only named placeholders are supported (e.g.,
    # :param_name)
    param_names = {placeholder.this for placeholder in sql_ast.find_all(exp.Placeholder)}

    return sorted(param_names)


def extract_missing_parameters(
    sql: str,
    dialect: str,
    existing_parameters: list[QueryParameter] | None,
) -> list[QueryParameter]:
    """Extract parameters from SQL that are not already defined.

    Returns a list of auto-generated QueryParameter objects for parameters
    found in the SQL query that don't have existing definitions.

    Args:
        sql: The SQL query containing :param_name placeholders
        dialect: SQL dialect for parsing (e.g., "postgres", "snowflake")
        existing_parameters: Already-defined parameters to exclude from results

    Returns:
        List of new QueryParameter objects with default values for parameters
        found in SQL but not in existing_parameters.
    """
    # We implement this as a standalone function because we callers often don't
    # yet have a valid VerifiedQuery instance they can use to call methods on.
    provided_params_by_name = {p.name: p for p in (existing_parameters or [])}

    # Raises error if invalid SQL
    extracted_param_names = extract_parameters_from_sql(sql, dialect=dialect)

    new_params: list[QueryParameter] = []
    for param_name in extracted_param_names:
        if param_name not in provided_params_by_name:
            # Auto-generate parameter definition with placeholder values
            new_params.append(
                QueryParameter(
                    name=param_name,
                    data_type="string",  # Safe default
                    example_value=None,
                    description="Please provide description for this parameter",
                )
            )

    return new_params
