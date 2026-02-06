"""Base components for query execution strategies.

This module provides the foundational protocol and shared utilities for query execution:
- QueryExecutionStrategy protocol defining the strategy interface
- Shared helper functions used by multiple strategies
- CTE building functions used by both database and file-based executors
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from sqlglot import exp
    from sqlglot.expressions import Expression

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.data_frames.data_node import DataNodeResult
    from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

    from .data_frames_kernel import Dependencies

logger = structlog.get_logger(__name__)


class QueryExecutionStrategy(Protocol):
    """Protocol for query execution strategies.

    Strategies are stateless and implement the Strategy pattern for handling
    different query execution paths based on data source types.
    """

    def can_handle(self, data_frame: PlatformDataFrame, dependencies: Dependencies) -> bool:
        """Check if this strategy can handle the given query.

        Args:
            data_frame: The data frame with SQL query to execute
            dependencies: The Dependencies object with resolved sources

        Returns:
            True if this strategy can handle the query, False otherwise
        """
        ...

    async def execute(
        self,
        kernel: DataFramesKernel,
        data_frame: PlatformDataFrame,
        con: AsyncIbisConnection,
        dependencies: Dependencies,
    ) -> DataNodeResult:
        """Execute the query and return results.

        Args:
            kernel: The DataFramesKernel instance
            data_frame: The data frame with SQL query to execute
            con: The database connection
            dependencies: The Dependencies object with resolved sources

        Returns:
            DataNodeResult with query results

        Raises:
            PlatformError: If execution fails
        """
        ...


def enhance_sql_error_message(error_msg: str, dialect: str | None) -> str:
    """Enhance SQL error messages with actionable guidance for LLMs.

    Args:
        error_msg: The original error message from the database
        dialect: The SQL dialect being used

    Returns:
        Enhanced error message with contextual guidance
    """
    enhanced_error = error_msg

    # Column not found errors - guide LLM to check SDM
    column_not_found = "column" in error_msg.lower() and (
        "does not exist" in error_msg.lower() or "not found" in error_msg.lower()
    )
    if column_not_found:
        enhanced_error += (
            "\n\nAction: Check the column names in the semantic data model. "
            "The column name might be different than expected. "
            "Review the available columns and their data types in the table definition."
        )

    # Set-returning function errors - guide to LATERAL JOIN (PostgreSQL-specific)
    elif "set-returning function" in error_msg.lower() and "aggregate" in error_msg.lower() and dialect == "postgres":
        enhanced_error += (
            "\n\nAction: Use LATERAL JOIN to unnest the array before aggregation. "
            "Pattern: FROM table t, LATERAL (SELECT AGG(field) "
            "FROM json_array_elements(...) x) AS agg"
        )

    return enhanced_error


async def execute_sql_and_create_result(
    con: AsyncIbisConnection,
    data_frame: PlatformDataFrame,
    full_sql_query_str: str,
    full_sql_query_logical_str: str,
) -> DataNodeResult:
    """Execute SQL query and wrap result in DataNodeResult.

    Args:
        con: The database connection
        data_frame: The data frame with SQL query to execute
        full_sql_query_str: The physical SQL query to execute
        full_sql_query_logical_str: The logical SQL query (for debugging)

    Returns:
        DataNodeResult with query results

    Raises:
        PlatformError: If execution fails with enhanced error message
    """
    from agent_platform.core.errors.base import PlatformError
    from agent_platform.server.data_frames.data_node import DataNodeFromIbisResult

    try:
        result = await con.sql(full_sql_query_str, dialect=data_frame.sql_dialect)

        df = DataNodeFromIbisResult(
            data_frame,
            result,
            full_sql_query_str=full_sql_query_str,
            full_sql_query_logical_str=full_sql_query_logical_str,
        )
        return df
    except Exception as e:
        error_msg = str(e)
        enhanced_error = enhance_sql_error_message(error_msg, data_frame.sql_dialect)

        logger.error(
            "Error executing SQL query",
            error=error_msg,
            data_frame_name=data_frame.name,
            sql_query=data_frame.computation,
            full_sql_query_str=full_sql_query_str,
            full_sql_query_logical_str=full_sql_query_logical_str,
            enhanced_error=enhanced_error,
        )
        raise PlatformError(message=f"Error executing SQL query: {enhanced_error}") from e


def build_ctes(name_to_cte_ast: dict[str, Expression]) -> list[exp.CTE]:
    """Build CTE (Common Table Expression) AST nodes from query ASTs.

    Args:
        name_to_cte_ast: Mapping of CTE names to their parsed query ASTs

    Returns:
        List of CTE expression nodes
    """
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
    """Update the WITH clause of SQL AST with new CTEs.

    IMPORTANT: Data frame CTEs are prepended before user-defined CTEs to ensure
    that user CTEs can reference data frames without forward-reference errors.
    This is critical for Postgres and other databases that don't allow
    forward references in WITH clauses.

    Args:
        main_sql_ast: The main SQL query AST
        ctes: List of CTE nodes to add

    Returns:
        Updated SQL AST with CTEs added
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


def build_sql_query_with_ctes(
    data_frame: PlatformDataFrame,
    sql_computation_data_frames: list[PlatformDataFrame],
) -> str:
    """Build SQL query with CTEs for nested sql_computation data frames.

    This function handles:
    1. Building CTEs for dependent sql_computation data frames
    2. Dialect transpilation for CTE queries if needed
    3. Adding WITH clause to main query

    No table/column transformations are applied - this is pure CTE building.

    Args:
        data_frame: The main data frame with SQL query
        sql_computation_data_frames: List of dependent sql_computation data frames (in dependency order)

    Returns:
        SQL query string with CTEs added

    Raises:
        PlatformHTTPError: If CTE queries are invalid or dialect transpilation fails
    """
    import sqlglot

    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    sql_query = data_frame.computation
    assert sql_query is not None

    # If no dependencies, return query as-is
    if not sql_computation_data_frames:
        return sql_query

    name_to_cte_ast: dict[str, Any] = {}
    target_dialect = data_frame.sql_dialect  # The dialect we're targeting for the final SQL

    # Build CTE for each dependent sql_computation data frame
    for df in sql_computation_data_frames:
        if df.computation is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.PRECONDITION_FAILED,
                message=f"SQL computation data frame has no computation: {df.name}",
            )

        expressions = sqlglot.parse(df.computation, dialect=df.sql_dialect)
        if len(expressions) != 1:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=(
                    f"SQL query must be a single expression. Found: {len(expressions)} SQL query: {df.computation!r}"
                ),
            )
        if expressions[0] is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"SQL query is not a valid expression. Found: {expressions[0]} SQL query: {df.computation!r}",
            )

        cte_sql_ast = expressions[0]

        # Transpile to target dialect if there's a mismatch
        if df.sql_dialect != target_dialect:
            logger.info(
                "Transpiling nested data frame SQL to target dialect",
                df_name=df.name,
                source_dialect=df.sql_dialect,
                target_dialect=target_dialect,
            )
            try:
                transpiled_sql = cte_sql_ast.sql(dialect=target_dialect)
                cte_sql_ast = sqlglot.parse_one(transpiled_sql, dialect=target_dialect)
            except Exception as e:
                logger.error(
                    "Failed to transpile nested data frame SQL to target dialect",
                    df_name=df.name,
                    source_dialect=df.sql_dialect,
                    target_dialect=target_dialect,
                    error=str(e),
                )
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        f"Cannot transpile data frame '{df.name}' from dialect "
                        f"'{df.sql_dialect}' to '{target_dialect}'. "
                        f"Error: {e}"
                    ),
                ) from e

        name_to_cte_ast[df.name] = cte_sql_ast

    # Build CTEs and add to main query
    ctes = build_ctes(name_to_cte_ast=name_to_cte_ast)
    main_sql_ast = sqlglot.parse_one(sql_query, dialect=data_frame.sql_dialect)
    main_sql_ast = update_with_clause(main_sql_ast, ctes)
    return main_sql_ast.sql(dialect=data_frame.sql_dialect, pretty=True)
