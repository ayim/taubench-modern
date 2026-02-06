"""File-based query executor strategy.

This module implements the FileBasedQueryExecutor strategy for executing queries
against file-based data sources (CSV, Excel) with logical-to-physical column translation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlglot import exp
    from sqlglot.expressions import Expression

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel, Dependencies
    from agent_platform.server.data_frames.data_node import DataNodeResult
    from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

logger = structlog.get_logger(__name__)


def update_table_names(
    main_sql_ast: Expression,
    table_name_to_expr: dict[str, str],
) -> Expression:
    """Update table names in the SQL AST based on the provided mapping.

    Args:
        main_sql_ast: The sqlglot AST to modify
        table_name_to_expr: Mapping of SDM table names to actual table names

    Returns:
        The modified AST with table names updated
    """
    from sqlglot import exp

    if not table_name_to_expr:
        return main_sql_ast  # Nothing to change

    for table in main_sql_ast.find_all(exp.Table):
        if table.name in table_name_to_expr:
            table.set("this", exp.Identifier(this=table_name_to_expr[table.name]))
    return main_sql_ast


def update_column_table_qualifiers(
    main_sql_ast: Expression,
    table_name_to_expr: dict[str, str],
) -> Expression:
    """Update table qualifiers in column references based on table name mappings.

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
        table_name_to_expr: Mapping of SDM table names to actual table names

    Returns:
        The modified AST with column table qualifiers updated
    """
    from sqlglot import exp

    if not table_name_to_expr:
        return main_sql_ast  # Nothing to change

    # Update all column table qualifiers
    for column in main_sql_ast.find_all(exp.Column):
        if column.table and column.table in table_name_to_expr:
            column.set(
                "table",
                exp.to_identifier(table_name_to_expr[column.table]),
            )

    return main_sql_ast


def _find_column_mapping_for_column(
    column_name: str,
    table_name: str | None,
    table_column_mappings: dict[str, dict[str, str]],
) -> str | None:
    """Find the physical expression for a column name from SDM mappings.

    Args:
        column_name: The column name from the SQL query
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
            logging.getLogger(__name__).warning(
                f"Ambiguous column reference '{column_name}' found in multiple tables: "
                f"{table_names}. All map to the same expression, using: {matches[0][1]}"
            )
            return matches[0][1]
        else:
            # Different expressions, cannot safely map
            logging.getLogger(__name__).warning(
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
        column_name: The column name from the query
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
        # If the column is directly in SELECT list, add an alias to preserve the column name
        elif _is_in_select_list(column):
            alias_expr = exp.alias_(physical_expr, column_name)
            column.replace(alias_expr)
        else:
            # For other contexts (WHERE, GROUP BY, inside functions, etc.),
            # just replace with the physical expression without aliasing
            column.replace(physical_expr)
    except Exception:
        # If parsing fails, log and skip this column
        logging.getLogger(__name__).exception(
            f"Failed to parse physical expression for column {column_name}: {physical_expr_str}",
        )


def update_column_references(
    main_sql_ast: Expression,
    table_column_mappings: dict[str, dict[str, str]],
    table_name_to_expr: dict[str, str] | None = None,
    data_frame_names: set[str] | None = None,
) -> Expression:
    """Update column references in SQL AST to replace column names with physical expressions.

    This function walks through column references in the AST and replaces them with their
    corresponding physical expressions from the semantic data model.

    Args:
        main_sql_ast: The sqlglot AST to modify
        table_column_mappings: Mapping of table names to their column mappings
            {table_name: {column_name: physical_expression}}
        table_name_to_expr: Optional mapping of SDM table names to actual table names
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

    # Build a reverse mapping if we have table name mappings
    actual_to_table_name: dict[str, str] = {}
    if table_name_to_expr:
        actual_to_table_name = {actual: table_name for table_name, actual in table_name_to_expr.items()}

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

            # After resolving alias, check if we need to map back to SDM table name
            # This is critical when table names have been rewritten before column rewriting
            if table_name in actual_to_table_name:
                table_name = actual_to_table_name[table_name]

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


def apply_table_and_column_transformations(
    sql_query: str,
    dialect: str,
    sql_computation_data_frames: list[PlatformDataFrame],
    data_frame_names: set[str],
    table_name_to_expr: dict[str, str],
    table_name_to_column_names_to_expr: dict[str, dict[str, str]],
) -> str:
    """Apply table name and column reference transformations to SQL query.

    This function handles logical-to-physical name translation for:
    1. Table names (SDM logical names → physical table names)
    2. Column table qualifiers
    3. Column references (logical column names → physical expressions)

    This is used for file-based SDM tables where we need to map user-friendly
    names to actual file column headers.

    Args:
        sql_query: The SQL query (may include CTEs)
        dialect: SQL dialect
        sql_computation_data_frames: List of dependent sql_computation data frames
        data_frame_names: Set of data frame names to exclude from SDM column mapping
        table_name_to_expr: Mapping from SDM table names to actual table names
        table_name_to_column_names_to_expr: Column name to physical expression mappings

    Returns:
        Transformed SQL query string
    """
    import sqlglot

    # Parse and transform SQL
    sql_ast = sqlglot.parse_one(sql_query, dialect=dialect)
    sql_ast = update_table_names(sql_ast, table_name_to_expr)
    sql_ast = update_column_table_qualifiers(sql_ast, table_name_to_expr)
    sql_ast = update_column_references(
        sql_ast,
        table_name_to_column_names_to_expr,
        table_name_to_expr,
        data_frame_names,
    )
    return sql_ast.sql(dialect=dialect, pretty=True)


class FileBasedQueryExecutor:
    """Strategy for executing queries against file-based SDM tables (CSV/Excel).

    This strategy:
    1. Materializes files into DuckDB tables
    2. Builds CTEs for nested data frames
    3. Applies logical-to-physical column translation
    4. Executes translated SQL in DuckDB
    """

    def can_handle(self, data_frame: PlatformDataFrame, dependencies: Dependencies) -> bool:
        """File-based queries require sources with file_reference or in-memory data frames.

        A query should use FileBasedQueryExecutor if any source in the dependency tree:
        1. Has a file_reference (CSV/Excel files), OR
        2. Is a data frame reference (in-memory or nested file-based computation), OR
        3. Is a semantic data model table without data_connection_id

        This check inspects the actual data sources rather than relying on backend
        implementation details.
        """
        all_sources_with_names = dependencies.get_all_data_frame_sources_with_names_recursive()

        for _table_name, source in all_sources_with_names:
            if source.source_type == "semantic_data_model" and source.base_table:
                # Check if this is a file-based table
                if source.base_table.get("file_reference") is not None:
                    return True

            elif source.source_type == "data_frame":
                # Data frame reference - could be in-memory or file
                return True

        # If no sources found, default to FileBasedQueryExecutor
        if not all_sources_with_names:
            return True

        return False

    def _build_table_and_column_mappings(
        self,
        dependencies: Dependencies,
    ) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        """Build table name and column name mappings from data frame sources.

        Returns:
            Tuple of (table_name_to_expr, table_name_to_column_names_to_expr)
        """
        table_name_to_expr: dict[str, str] = {}
        table_name_to_column_names_to_expr: dict[str, dict[str, str]] = {}

        for table_name, df_source in dependencies.get_all_data_frame_sources_with_names_recursive():
            if df_source.column_names_to_expr:
                table_name_to_column_names_to_expr[table_name] = df_source.column_names_to_expr
                logger.info(
                    "Added column mappings for table",
                    table_name=table_name,
                    num_mappings=len(df_source.column_names_to_expr),
                )
            else:
                logger.warning(
                    "No column mappings for file-based table",
                    table_name=table_name,
                )

        return table_name_to_expr, table_name_to_column_names_to_expr

    async def _materialize_file_and_dataframe_sources(
        self,
        dependencies: Dependencies,
        kernel: DataFramesKernel,
        con: AsyncIbisConnection,
        table_name_to_expr: dict[str, str],
    ) -> None:
        """Materialize file-based tables and in-memory data frames into DuckDB.

        Args:
            dependencies: Dependency graph
            kernel: DataFrameKernel instance
            con: DuckDB connection
            table_name_to_expr: Mutable dict to populate with table name mappings
        """
        from collections.abc import Coroutine
        from typing import Any

        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        name_to_coro: dict[str, Coroutine[Any, Any, DataNodeResult]] = {}
        name_to_node: dict[str, DataNodeResult] = {}

        # Materialize in-memory and file data frames
        for df in dependencies._iter_recursive_data_frames():
            assert df.input_id_type in ("in_memory", "file")
            name_to_coro[df.name] = kernel.resolve_data_frame(df)

        # Process SDM sources with file_reference or data frame references
        for table_name, df_source in dependencies._iter_recursive_data_frame_sources_with_names():
            if df_source.source_type == "semantic_data_model" and df_source.base_table is not None:
                if df_source.base_table.get("file_reference") is not None:
                    # File-based table - need to materialize
                    name_to_coro[table_name] = kernel._resolve_file_data_source(df_source, table_name)
                else:
                    # Data frame reference within SDM
                    base_table = df_source.base_table
                    if not base_table:
                        logger.critical(
                            "Base table is None for semantic data model",
                            df_source=str(df_source),
                            table_name=table_name,
                        )
                        continue
                    data_frame_name = base_table.get("table")
                    if not data_frame_name:
                        logger.critical(
                            "'table' name is None for semantic data model",
                            df_source=str(df_source),
                            table_name=table_name,
                            base_table=base_table,
                        )
                        continue
                    # Get the data frame by name from the thread
                    name_to_data_frame = await kernel._get_name_to_data_frame()
                    if data_frame_name not in name_to_data_frame:
                        raise PlatformHTTPError(
                            error_code=ErrorCode.NOT_FOUND,
                            message=f"Data frame '{data_frame_name}' referenced in semantic data model "
                            f"not found in thread {kernel._tid}",
                        )
                    df = name_to_data_frame[data_frame_name]
                    # Resolve the data frame and map SDM table name to actual data frame name
                    name_to_coro[data_frame_name] = kernel.resolve_data_frame(df)
                    # Map SDM table name to actual data frame name for SQL queries
                    table_name_to_expr[table_name] = data_frame_name

        # Ensure we're using DuckDB for file operations
        if name_to_coro:
            if con.name != "duckdb":
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        f"Only duckdb is supported for materializing in-memory, file and "
                        f"computed data frames. Current backend: {con.name}"
                    ),
                )

        # Materialize all files and data frames
        import asyncio

        results = await asyncio.gather(*name_to_coro.values())
        for variable_name, result in zip(name_to_coro.keys(), results, strict=True):
            name_to_node[variable_name] = result

        # Create DuckDB tables from materialized data
        for variable_name, node in name_to_node.items():
            await con.create_table(variable_name, node.to_ibis())

    async def execute(
        self,
        kernel: DataFramesKernel,
        data_frame: PlatformDataFrame,
        con: AsyncIbisConnection,
        dependencies: Dependencies,
    ) -> DataNodeResult:
        """Execute file-based query with translation."""
        from .query_execution_base import build_sql_query_with_ctes, execute_sql_and_create_result

        logger.info(
            "Executing file-based query with translation",
            data_frame_name=data_frame.name,
            dialect=data_frame.sql_dialect,
        )

        sql_query = data_frame.computation
        assert sql_query

        # Step 1: Build table and column mappings
        table_name_to_expr, table_name_to_column_names_to_expr = self._build_table_and_column_mappings(dependencies)

        # Step 2: Materialize file-based tables and in-memory data frames
        await self._materialize_file_and_dataframe_sources(dependencies, kernel, con, table_name_to_expr)

        # Step 3: Build query with CTEs
        sql_computation_data_frames = list(dependencies._iter_recursive_sql_computation_data_frames())
        sql_with_ctes = build_sql_query_with_ctes(data_frame, sql_computation_data_frames)

        # Step 4: Apply table/column transformations
        dialect = data_frame.sql_dialect or "duckdb"  # Default to duckdb for file-based queries

        # Collect all data frame names (both regular DFs and those that will become CTEs)
        # These should be excluded from SDM column mapping rewrites
        data_frame_names: set[str] = set()
        for df in dependencies._iter_recursive_data_frames():
            data_frame_names.add(df.name)
        for df in sql_computation_data_frames:
            data_frame_names.add(df.name)

        if not table_name_to_column_names_to_expr:
            # No SDM tables with column mappings - just data frame references
            logger.info(
                "No SDM column mappings (data frame references only)",
                data_frame_name=data_frame.name,
            )

            # Still apply table name transformations if present
            if table_name_to_expr:
                full_sql_query_str = apply_table_and_column_transformations(
                    sql_with_ctes,
                    dialect,
                    sql_computation_data_frames,
                    data_frame_names,
                    table_name_to_expr,
                    table_name_to_column_names_to_expr={},
                )
            else:
                full_sql_query_str = sql_with_ctes

            full_sql_query_logical_str = full_sql_query_str
        else:
            # Have SDM tables with column mappings - apply full transformations
            logger.info(
                "Applying column name to physical expression translation",
                data_frame_name=data_frame.name,
                tables_with_mappings=list(table_name_to_column_names_to_expr.keys()),
            )

            # Build physical SQL with translation
            full_sql_query_str = apply_table_and_column_transformations(
                sql_with_ctes,
                dialect,
                sql_computation_data_frames,
                data_frame_names,
                table_name_to_expr,
                table_name_to_column_names_to_expr,
            )

            # Build SQL without column translation (for debugging)
            full_sql_query_logical_str = apply_table_and_column_transformations(
                sql_with_ctes,
                dialect,
                sql_computation_data_frames,
                data_frame_names,
                table_name_to_expr={},
                table_name_to_column_names_to_expr={},
            )

        # Step 5: Execute the query
        return await execute_sql_and_create_result(
            con,
            data_frame,
            full_sql_query_str,
            full_sql_query_logical_str,
        )
