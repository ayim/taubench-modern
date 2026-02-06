"""SQL manipulation utilities for non-strategy code.

This module contains SQL utilities used by non-strategy code:
- validate_sql_query(): Validates SQL queries for safety
- get_destructive_reasons(): Checks for destructive SQL operations
  (used by validate_sql_query and DatabaseQueryExecutor)
- extract_variable_names_required_from_sql_computation(): Extracts table references from SQL
- Utility functions for result type determination (used by API layer and DML execution)

Note: Strategy-specific SQL manipulation functions have been moved:
- CTE building functions → query_execution_base.py
- Table/column transformation functions → file_based_query_executor.py
"""

from __future__ import annotations

import logging
import typing

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from sqlglot import exp
    from sqlglot.expressions import Expression

    from agent_platform.core.semantic_data_model.types import ResultType

# SQL keywords that indicate destructive operations
DESTRUCTIVE_KEYS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "TRUNCATE",
    "CREATE",
    "ALTER",
    "DROP",
    "RENAME",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXECUTE",
    "COPY",
    "LOAD",
    "REFRESH",
    "VACUUM",
    "OPTIMIZE",
    "ANALYZE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "SET",
    "USE",
}

# Read-only top-level statements
READONLY_TOPLEVEL = {"SELECT", "UNION", "EXCEPT", "INTERSECT", "VALUES", "WITH"}

# DML operations that can be allowed for verified queries when allow_mutate=True
# Note: DDL operations (CREATE, DROP, ALTER, TRUNCATE, etc.) are NEVER allowed
ALLOWED_MUTATING_TOPLEVEL = {"INSERT", "UPDATE", "DELETE"}


def _root_key(e: exp.Expression) -> str:
    """Extract the root statement key from a SQL expression.

    Unwraps WITH, SUBQUERY, and PAREN wrappers to get to the actual statement type.
    """
    from sqlglot import exp

    while isinstance(e, exp.With | exp.Subquery | exp.Paren):
        e = e.this
    return (e.key or "").upper()


def _contains_destructive(e: exp.Expression) -> str | None:
    """Walk the SQL AST looking for any destructive operations."""
    for node in e.walk():
        k = (node.key or "").upper()
        if k in DESTRUCTIVE_KEYS:
            return k
    return None


def get_destructive_reasons(stmt: exp.Expression, allow_mutate: bool = False) -> list[str]:
    """Check if SQL statement contains destructive operations.

    This function is used by both validate_sql_query() and DatabaseQueryExecutor.

    Args:
        stmt: The parsed SQL statement
        allow_mutate: If True, allows INSERT/UPDATE/DELETE operations but still
                     blocks DDL (CREATE, DROP, ALTER, TRUNCATE).
                     This should only be set to True for verified queries.
                     Defaults to False for security.

    Returns:
        List of reasons why the statement is destructive, or empty list if allowed.
    """
    reasons: list[str] = []
    root = _root_key(stmt)

    # Determine valid top-level statements based on allow_mutate
    if allow_mutate:
        valid_toplevel = READONLY_TOPLEVEL | ALLOWED_MUTATING_TOPLEVEL
    else:
        valid_toplevel = READONLY_TOPLEVEL

    if root not in valid_toplevel:
        if allow_mutate:
            reasons.append(f"Only read-only or DML (INSERT/UPDATE/DELETE) top-levels are allowed. Found: {root}")
        else:
            reasons.append(f"Only read-only top-levels are allowed. Found non-read-only top-level: {root}")
        return reasons

    # If allow_mutate is True and root is a DML operation, it's allowed
    if allow_mutate and root in ALLOWED_MUTATING_TOPLEVEL:
        return reasons

    # Standard read-only check for SELECT/UNION/etc
    which = _contains_destructive(stmt)
    if which is not None:
        reasons.append(f"Only read-only statements are allowed. Found destructive clause: {which}")
        return reasons
    return reasons


def extract_variable_names_required_from_sql_computation(sql_ast: Expression) -> set[str]:
    import sqlglot.expressions

    tables = sql_ast.find_all(sqlglot.expressions.Table)

    required_variable_names = {t.name for t in tables if t.name}
    cte_tables = sql_ast.find_all(sqlglot.expressions.CTE)
    for cte in cte_tables:
        required_variable_names.discard(cte.alias)
    return required_variable_names


def get_mutation_type(sql_query: str, dialect: str | None) -> str | None:
    """Return the mutation type if the SQL is a mutation, else None.

    Args:
        sql_query: The SQL query to analyze
        dialect: The SQL dialect to use for parsing

    Returns:
        'INSERT', 'UPDATE', or 'DELETE' if the query is a mutation, None otherwise.
    """
    import sqlglot

    try:
        expressions = sqlglot.parse(sql_query, dialect=dialect)
        if len(expressions) != 1 or expressions[0] is None:
            return None

        root = _root_key(expressions[0])
        if root in ALLOWED_MUTATING_TOPLEVEL:
            return root
        return None
    except Exception:
        return None


def has_returning_clause(sql_query: str, dialect: str | None) -> bool:
    """Check if a SQL query has a RETURNING clause.

    Args:
        sql_query: The SQL query to analyze
        dialect: The SQL dialect to use for parsing

    Returns:
        True if the query has a RETURNING clause, False otherwise.
    """
    import sqlglot
    from sqlglot import exp

    try:
        expressions = sqlglot.parse(sql_query, dialect=dialect)
        if len(expressions) != 1 or expressions[0] is None:
            return False

        # Look for RETURNING clause in the AST
        return expressions[0].find(exp.Returning) is not None
    except Exception:
        return False


def determine_result_type(sql_query: str, dialect: str | None) -> ResultType:
    """Determine the result type of a SQL query.

    Args:
        sql_query: The SQL query to analyze
        dialect: The SQL dialect to use for parsing

    Returns:
        ResultType.TABLE if the query returns rows (SELECT, or mutation with RETURNING)
        ResultType.ROWS_AFFECTED if the query is a mutation without RETURNING
    """
    from agent_platform.core.semantic_data_model.types import ResultType

    mutation_type = get_mutation_type(sql_query, dialect)

    if mutation_type is None:
        # Not a mutation (SELECT, UNION, etc.) - returns a table
        return ResultType.TABLE

    # It's a mutation - check for RETURNING clause
    if has_returning_clause(sql_query, dialect):
        return ResultType.TABLE

    return ResultType.ROWS_AFFECTED


def validate_sql_query(
    sql_query: str,
    dialect: str | None,
    allow_mutate: bool = False,
) -> Expression:
    """Validate the SQL query and return the AST.

    sqlglot can parse SQL queries with :param_name placeholders directly,
    so no parameter substitution is needed before parsing.

    Args:
        sql_query: The SQL query to validate (may contain :param_name)
        dialect: The SQL dialect to use for parsing. If None, uses a
            permissive internal sqlglot dialect.
        allow_mutate: If True, allows INSERT/UPDATE/DELETE operations.
            Defaults to False for security. Only set to True for verified queries.

    Returns:
        The parsed sqlglot AST expression

    Raises:
        PlatformError: If the query is invalid or contains disallowed
            operations

    Example:
        >>> validate_sql_query(
        ...     "SELECT * FROM users WHERE country = :country",
        ...     dialect=None
        ... )
    """
    import sqlglot

    from agent_platform.core.errors.base import PlatformError

    # Parse and validate the SQL directly (sqlglot can parse :param_name placeholders)
    expressions = sqlglot.parse(sql_query, dialect=dialect)
    if len(expressions) != 1:
        raise PlatformError(
            message=(f"SQL query must be a single expression. Found: {len(expressions)} SQL query: {sql_query!r}")
        )

    expr = expressions[0]
    if expr is None or not hasattr(expr, "key"):
        raise PlatformError(message=f"SQL query is not a valid expression: {sql_query!r}")

    reasons = get_destructive_reasons(expr, allow_mutate=allow_mutate)
    if reasons:
        raise PlatformError(message=(f"Unable to create data frame from SQL query: {sql_query} (Errors: {reasons})"))
    return expr
