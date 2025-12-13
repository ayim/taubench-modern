from __future__ import annotations

import logging
import typing
from typing import Any

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from sqlglot import exp
    from sqlglot.expressions import Expression

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

READONLY_TOPLEVEL = {"SELECT", "UNION", "EXCEPT", "INTERSECT", "VALUES", "WITH"}


def _root_key(e: exp.Expression) -> str:
    # Unwrap wrappers to get to the "real" statement
    from sqlglot import exp

    while isinstance(e, exp.With | exp.Subquery | exp.Paren):
        e = e.this
    return (e.key or "").upper()


def _contains_destructive(e: exp.Expression) -> str | None:
    # Walk the whole tree looking for any destructive node
    for node in e.walk():
        k = (node.key or "").upper()
        if k in DESTRUCTIVE_KEYS:
            return k
    return None


def get_destructive_reasons(stmt: exp.Expression) -> list[str]:
    """
    Returns reasons for why the statement is destructive.
    """
    reasons: list[str] = []
    root = _root_key(stmt)
    if root not in READONLY_TOPLEVEL:
        reasons.append(f"Only read-only top-levels are allowed. Found non-read-only top-level: {root}")
        return reasons
    which = _contains_destructive(stmt)
    if which is not None:
        reasons.append(f"Only read-only statements are allowed. Found destructive clause: {which}")
        return reasons
    return reasons


def build_ctes(name_to_cte_ast: dict[str, Expression]) -> list[exp.CTE]:
    from sqlglot import exp

    # Build CTE expressions: WITH name AS (<parsed query>)
    ctes = [
        exp.CTE(
            this=p,  # the subquery AST
            alias=exp.TableAlias(this=exp.to_identifier(name)),
        )
        for name, p in name_to_cte_ast.items()
    ]
    return ctes


def update_with_clause(main_sql_ast: Expression, ctes: list[exp.CTE]) -> Expression:
    """
    Update the with clause of the main sql ast with the new CTEs.

    IMPORTANT: Data frame CTEs are prepended before user-defined CTEs to ensure
    that user CTEs can reference data frames without forward-reference errors.
    This is critical for Postgres and other databases that don't allow
    forward references in WITH clauses.
    """
    from sqlglot import exp

    if not ctes:
        return main_sql_ast  # Nothing to change

    existing_with = main_sql_ast.args.get("with")
    if existing_with is not None:
        # Prepend the data frame CTEs before existing user CTEs
        # This ensures data frames are available to user-defined CTEs
        existing_with.set("expressions", ctes + existing_with.expressions)
    else:
        main_sql_ast.set("with", exp.With(expressions=ctes, recursive=False))
    return main_sql_ast


def update_table_names(
    main_sql_ast: Expression,
    logical_table_name_to_actual_table_name: dict[str, str],
) -> Expression:
    """
    Update the table name of the main sql ast with the new table name.
    """
    from sqlglot import exp

    if not logical_table_name_to_actual_table_name:
        return main_sql_ast  # Nothing to change

    for table in main_sql_ast.find_all(exp.Table):
        if table.name in logical_table_name_to_actual_table_name:
            table.set("this", exp.Identifier(this=logical_table_name_to_actual_table_name[table.name]))
    return main_sql_ast


def update_column_table_qualifiers(
    main_sql_ast: Expression,
    logical_table_name_to_actual_table_name: dict[str, str],
) -> Expression:
    """
    Update table qualifiers in column references from logical to physical table names.

    This is critical for MySQL and other databases that require table qualifiers in
    column references to match the actual table names in FROM/JOIN clauses.

    This function should be called AFTER update_table_names() to fix column qualifiers.

    Complete transformation flow:
        1. Original: SELECT Invoices.document_id FROM Invoices
        2. After update_table_names():
           SELECT Invoices.document_id FROM invoice_documents (BROKEN)
        3. After update_column_table_qualifiers():
           SELECT invoice_documents.document_id FROM invoice_documents (FIXED)

    Args:
        main_sql_ast: The sqlglot AST to modify
        logical_table_name_to_actual_table_name: Mapping of logical to physical table names

    Returns:
        The modified AST with column table qualifiers updated
    """
    from sqlglot import exp

    if not logical_table_name_to_actual_table_name:
        return main_sql_ast  # Nothing to change

    # Update all column table qualifiers
    for column in main_sql_ast.find_all(exp.Column):
        if column.table and column.table in logical_table_name_to_actual_table_name:
            column.set(
                "table",
                exp.to_identifier(logical_table_name_to_actual_table_name[column.table]),
            )

    return main_sql_ast


def _find_column_mapping_for_column(
    column_name: str,
    table_name: str | None,
    table_column_mappings: dict[str, dict[str, str]],
) -> str | None:
    """Find the physical expression for a logical column name.

    Args:
        column_name: The logical column name
        table_name: The table name (if known)
        table_column_mappings: Mapping of table names to their column mappings

    Returns:
        The physical expression, or None if no mapping is found
    """
    # Try to find a mapping for this column
    if table_name and table_name in table_column_mappings:
        # We have an explicit table reference
        return table_column_mappings[table_name].get(column_name)

    # No explicit table, search all tables for this column name
    # (only if there's exactly one match across all tables to avoid ambiguity)
    matches = []
    for tbl_name, col_map in table_column_mappings.items():
        if column_name in col_map:
            matches.append((tbl_name, col_map[column_name]))

    if len(matches) == 1:
        return matches[0][1]

    if len(matches) > 1:
        # Check if all matches map to the same expression
        unique_exprs = set(match[1] for match in matches)
        table_names = ", ".join(match[0] for match in matches)

        if len(unique_exprs) == 1:
            # All matches map to the same expression, so we can safely use it
            logger.warning(
                f"Ambiguous column reference '{column_name}' found in multiple tables: "
                f"{table_names}. All map to the same expression, using: {matches[0][1]}"
            )
            return matches[0][1]
        else:
            # Different expressions, cannot safely map
            logger.warning(
                f"Ambiguous column reference '{column_name}' found in multiple tables: "
                f"{table_names}. Columns map to different expressions. Column will not be mapped."
            )

    return None


def _is_in_select_list(column: exp.Column) -> bool:
    """Check if a column is directly in a SELECT clause (not nested in functions/expressions).

    Args:
        column: The sqlglot Column node to check

    Returns:
        True if the column is directly in a SELECT list, False otherwise
    """
    from sqlglot import exp

    # Walk up the tree to find the parent context
    node = column
    while node.parent:
        parent = node.parent

        # If we hit an Alias first, check if that alias is in the SELECT
        if isinstance(parent, exp.Alias):
            # The alias is already there, don't add another
            return False

        # If we hit a Select node, check if our node is directly in its expressions
        if isinstance(parent, exp.Select):
            # Check if the column (or its immediate parent) is in the SELECT expressions
            return node in parent.expressions or any(
                node == expr or (isinstance(expr, exp.Alias) and node == expr.this) for expr in parent.expressions
            )

        # If we hit any of these contexts, we're definitely not in a SELECT list
        # - Func: inside a function call like MAX(col)
        # - Where: in a WHERE clause
        # - Group: in a GROUP BY clause
        # - Order: in an ORDER BY clause
        # - Having: in a HAVING clause
        # - Join: in a JOIN clause (either the join itself or its ON condition)
        # - EQ/NEQ/GT/LT/etc: comparison operators (often in JOIN ON or WHERE)
        if isinstance(
            parent,
            exp.Func
            | exp.Where
            | exp.Group
            | exp.Order
            | exp.Having
            | exp.Join
            | exp.EQ
            | exp.NEQ
            | exp.GT
            | exp.GTE
            | exp.LT
            | exp.LTE
            | exp.Is
            | exp.Like
            | exp.ILike
            | exp.In,
        ):
            return False

        node = parent

    return False


def _qualify_all_columns_in_expression(expr: Expression, table_qualifier: str) -> None:
    """Recursively qualify all column references in an expression with a table qualifier.

    This is critical for computed expressions in multi-table queries. For example, if we have:
    - Original: e1.full_name
    - Physical expr: "first_name || ' ' || last_name"

    We need to qualify ALL columns in the expression:
    - Result: e1.first_name || ' ' || e1.last_name

    Without this, the query becomes ambiguous in JOINs or self-joins.

    Args:
        expr: The expression AST to qualify
        table_qualifier: The table name/alias to use (e.g., "e1", "pcb")
    """
    from sqlglot import exp

    # Walk all Column nodes in the expression and add the qualifier
    for col in expr.find_all(exp.Column):
        if not col.table:  # Only qualify if not already qualified
            col.set("table", exp.to_identifier(table_qualifier))


def _replace_column_with_expression(
    column: exp.Column,
    column_name: str,
    physical_expr_str: str,
) -> None:
    """Replace a column reference with a physical expression.

    Args:
        column: The sqlglot Column node
        column_name: The logical column name
        physical_expr_str: The physical expression as a string
    """
    import sqlglot
    from sqlglot import exp

    try:
        physical_expr = sqlglot.parse_one(physical_expr_str)

        parent = column.parent

        # If the original column has a table qualifier, we need to apply it to ALL
        # columns in the physical expression (critical for multi-table queries)
        if column.table:
            _qualify_all_columns_in_expression(physical_expr, column.table)

        # If the column already has an alias parent, just replace the column itself
        if parent and isinstance(parent, exp.Alias):
            parent.set("this", physical_expr)
        # If the column is directly in SELECT list, add an alias to preserve the logical name
        elif _is_in_select_list(column):
            alias_expr = exp.alias_(physical_expr, column_name)
            column.replace(alias_expr)
        else:
            # For other contexts (WHERE, GROUP BY, inside functions, etc.),
            # just replace with the physical expression without aliasing
            column.replace(physical_expr)
    except Exception:
        # If parsing fails, log and skip this column
        logger.exception(
            f"Failed to parse physical expression for column {column_name}: {physical_expr_str}",
        )


def update_column_references(
    main_sql_ast: Expression,
    table_column_mappings: dict[str, dict[str, str]],
    logical_table_name_to_actual_table_name: dict[str, str] | None = None,
    data_frame_names: set[str] | None = None,
) -> Expression:
    """Update column references in SQL AST to replace logical names with physical expressions.

    This function walks through column references in the AST and replaces them with their
    corresponding physical expressions from the semantic data model.

    Args:
        main_sql_ast: The sqlglot AST to modify
        table_column_mappings: Mapping of table names to their column mappings
            {table_name: {logical_column: physical_expression}}
        logical_table_name_to_actual_table_name: Optional mapping of logical to actual table
            names
        data_frame_names: Optional set of data frame names that should be excluded from
            column mapping rewrites. This prevents SDM column mappings from being applied
            to columns that belong to derived data frames.

    Returns:
        The modified AST with column references updated

    Examples:
        If table "customers" has mapping {"full_name": "first_name || ' ' || last_name"},
        then "SELECT full_name FROM customers" becomes
        "SELECT first_name || ' ' || last_name AS full_name FROM customers"
    """
    from sqlglot import exp

    if not table_column_mappings:
        return main_sql_ast  # Nothing to change

    # Build a reverse mapping if we have logical-to-actual table names
    actual_to_logical_table: dict[str, str] = {}
    if logical_table_name_to_actual_table_name:
        actual_to_logical_table = {
            actual: logical for logical, actual in logical_table_name_to_actual_table_name.items()
        }

    # Note: We don't build a global alias_to_table here because aliases can be reused
    # in different scopes (e.g., "so" in multiple CTEs). Instead, we resolve aliases
    # dynamically for each column by walking up to find the relevant FROM/JOIN context.

    # Collect names of CTEs - we should NOT apply column mappings to CTE references
    # because CTEs define their own column names in their output
    cte_names: set[str] = set()
    # Check for WITH clause
    with_clause = main_sql_ast.args.get("with")
    if with_clause and hasattr(with_clause, "expressions"):
        for cte in with_clause.expressions:
            if hasattr(cte, "alias") and cte.alias:
                cte_names.add(cte.alias)

    # Collect SELECT output column names to avoid rewriting them in ORDER BY
    # When ORDER BY references a SELECT output column, use the output name, not rewrite it
    select_output_names: set[str] = set()
    for select_node in main_sql_ast.find_all(exp.Select):
        for expr in select_node.expressions:
            if isinstance(expr, exp.Alias) and hasattr(expr, "alias"):
                # Explicit alias: SELECT col AS alias_name
                select_output_names.add(expr.alias)
            elif isinstance(expr, exp.Column):
                # Implicit output name: SELECT col (output name is col)
                select_output_names.add(expr.name)

    # Walk through all column references in the AST
    for column in main_sql_ast.find_all(exp.Column):
        column_name = column.name
        if not column_name:
            continue

        # Check if this is an unqualified reference to a SELECT output column (e.g., in ORDER BY)
        # If so, don't rewrite it - use the output name as-is
        if not column.table and column_name in select_output_names:
            # Check if we're in an ORDER BY context
            is_order_by_alias = False
            node = column
            while node.parent:
                parent = node.parent
                if isinstance(parent, exp.Order | exp.Ordered):
                    # This is an ORDER BY reference to a SELECT alias - don't rewrite
                    is_order_by_alias = True
                    break
                if isinstance(parent, exp.Select):
                    # Reached SELECT without hitting ORDER BY
                    break
                node = parent
            if is_order_by_alias:
                continue

        # Check if this column references a CTE (even without explicit table qualifier)
        # For unqualified columns, check if the SELECT queries FROM a CTE
        is_unqualified_cte_ref = False
        if not column.table:
            # Unqualified column - check if we're selecting FROM a CTE
            node = column
            while node.parent:
                parent = node.parent
                if isinstance(parent, exp.Select):
                    # Check FROM clause
                    from_clause = parent.args.get("from")
                    if from_clause and hasattr(from_clause, "this"):
                        from_table = from_clause.this
                        if isinstance(from_table, exp.Table) and from_table.name in cte_names:
                            # Querying FROM a CTE - don't rewrite unqualified columns
                            is_unqualified_cte_ref = True
                    # Stop at first SELECT
                    break
                node = parent

        if is_unqualified_cte_ref:
            continue

        # Check if this column references a data frame (even without explicit table qualifier)
        # For unqualified columns, check if the SELECT queries FROM a data frame
        is_unqualified_df_ref = False
        if not column.table and data_frame_names:
            # Unqualified column - check if we're selecting FROM a data frame
            node = column
            while node.parent:
                parent = node.parent
                if isinstance(parent, exp.Select):
                    # Check FROM clause
                    from_clause = parent.args.get("from")
                    if from_clause and hasattr(from_clause, "this"):
                        from_table = from_clause.this
                        if isinstance(from_table, exp.Table) and from_table.name in data_frame_names:
                            # Querying FROM a data frame - don't rewrite unqualified columns
                            is_unqualified_df_ref = True
                    # Stop at first SELECT
                    break
                node = parent

        if is_unqualified_df_ref:
            continue

        # Determine which table this column belongs to
        table_name = None
        if column.table:
            # Column has an explicit table reference (e.g., "pcb.product_id")
            table_ref = column.table

            # Check if this explicitly references a CTE - if so, skip rewriting
            # CTEs define their own output column names
            if table_ref in cte_names:
                continue

            # Resolve the alias by finding the table definition in the column's scope
            # Walk up to find the SELECT, then check its FROM/JOIN clauses
            resolved_table_name = None
            node = column
            while node.parent and resolved_table_name is None:
                parent = node.parent
                if isinstance(parent, exp.Select):
                    # Check FROM clause
                    from_clause = parent.args.get("from")
                    if from_clause and hasattr(from_clause, "this"):
                        from_table = from_clause.this
                        if isinstance(from_table, exp.Table):
                            if from_table.alias == table_ref:
                                resolved_table_name = from_table.name
                                break
                    # Check JOIN clauses
                    joins = parent.args.get("joins") or []
                    for join in joins:
                        if hasattr(join, "this") and isinstance(join.this, exp.Table):
                            if join.this.alias == table_ref:
                                resolved_table_name = join.this.name
                                break
                    # Stop at first SELECT - don't walk past it
                    break
                node = parent

            # If we found the table through alias resolution, use it
            if resolved_table_name:
                # Check if the alias resolves to a CTE name
                if resolved_table_name in cte_names:
                    continue  # Skip - this is a CTE reference via alias
                table_name = resolved_table_name
            else:
                # No alias found, use table_ref directly
                table_name = table_ref

            # After resolving alias, check if we need to map to logical table name
            # This is critical when table names have been rewritten before column rewriting
            if table_name in actual_to_logical_table:
                table_name = actual_to_logical_table[table_name]

        # Check if this table is a data frame - if so, skip column mapping
        # Data frames have their own column names and shouldn't have SDM mappings applied
        if data_frame_names and table_name and table_name in data_frame_names:
            continue

        # Find the mapping for this column
        column_mapping = _find_column_mapping_for_column(column_name, table_name, table_column_mappings)

        # If we found a mapping and it's different from the column name, replace it
        if column_mapping and column_mapping != column_name:
            _replace_column_with_expression(column, column_name, column_mapping)

    return main_sql_ast


def extract_variable_names_required_from_sql_computation(sql_ast: Any) -> set[str]:
    import sqlglot.expressions

    tables = sql_ast.find_all(sqlglot.expressions.Table)

    required_variable_names = {t.name for t in tables if t.name}
    cte_tables = sql_ast.find_all(sqlglot.expressions.CTE)
    for cte in cte_tables:
        required_variable_names.discard(cte.alias)
    return required_variable_names


def validate_sql_query(sql_query: str, dialect: str | None) -> Any:
    """
    Validate the SQL query and return the AST.

    If the dialect is None, it'll try to parse with a very permissive
    internal sqlglot dialect.
    """
    import sqlglot

    from agent_platform.core.errors.base import PlatformError

    expressions = sqlglot.parse(sql_query, dialect=dialect)
    if len(expressions) != 1:
        raise PlatformError(
            message=f"SQL query must be a single expression. Found: {len(expressions)} SQL query: {sql_query!r}"
        )

    expr = expressions[0]
    if expr is None or not hasattr(expr, "key"):
        raise PlatformError(message=f"SQL query is not a valid expression: {sql_query!r}")

    reasons = get_destructive_reasons(expr)
    if reasons:
        raise PlatformError(message=f"Unable to create data frame from SQL query: {sql_query} (Errors: {reasons})")
    return expr
