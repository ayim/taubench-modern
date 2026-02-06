"""Database query executor strategy.

This module implements the DatabaseQueryExecutor strategy for executing queries
against database tables (Postgres, MySQL, Snowflake, etc.) without translation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel, Dependencies
    from agent_platform.server.data_frames.data_node import DataNodeResult
    from agent_platform.server.kernel.ibis.base import AsyncIbisConnection

logger = structlog.get_logger(__name__)


class DatabaseQueryExecutor:
    """Strategy for executing queries against database tables.

    This strategy:
    1. Validates SQL is safe (no destructive operations)
    2. Builds CTEs for nested sql_computation dataframes
    3. Executes SQL directly on the database connection
    4. No translation, no materialization
    """

    def can_handle(self, data_frame: PlatformDataFrame, dependencies: Dependencies) -> bool:
        """Database queries execute directly on database connections.

        A query should use DatabaseQueryExecutor if ALL sources in the dependency tree:
        1. Are semantic_data_model sources with data_connection_id, AND
        2. Have NO file_reference entries

        This check inspects the actual data sources rather than relying on backend
        implementation details.
        """
        all_sources_with_names = dependencies.get_all_data_frame_sources_with_names_recursive()

        # If no sources, cannot use database executor
        if not all_sources_with_names:
            return False

        # Check that ALL sources are database connections
        for _table_name, source in all_sources_with_names:
            # Data frame references require DuckDB materialization
            if source.source_type == "data_frame":
                return False

            # Check semantic data model sources
            if source.source_type == "semantic_data_model" and source.base_table:
                # Must have data_connection_id
                if source.base_table.get("data_connection_id") is None:
                    return False
                # Must NOT have file_reference
                if source.base_table.get("file_reference") is not None:
                    return False

        # All sources are database connections - we can use DatabaseQueryExecutor
        return True

    async def execute(
        self,
        kernel: DataFramesKernel,
        data_frame: PlatformDataFrame,
        con: AsyncIbisConnection,
        dependencies: Dependencies,
    ) -> DataNodeResult:
        """Execute database query, building CTEs for nested sql_computation dataframes."""
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        from .query_execution_base import build_sql_query_with_ctes, execute_sql_and_create_result
        from .sql_manipulation import get_destructive_reasons

        logger.info(
            "Executing database query directly (no translation)",
            data_frame_name=data_frame.name,
            dialect=data_frame.sql_dialect,
        )

        sql_query = data_frame.computation
        assert sql_query is not None

        # Get dependent sql_computation data frames that need CTEs
        sql_computation_data_frames = list(dependencies._iter_recursive_sql_computation_data_frames())

        # Build SQL with CTEs only (no table/column transformations for database queries)
        # The LLM already generates queries with correct physical table and column names
        full_sql_query = build_sql_query_with_ctes(
            data_frame,
            sql_computation_data_frames,
        )

        # Validate SQL is safe (no destructive operations)
        import sqlglot

        parsed_query = sqlglot.parse_one(full_sql_query, dialect=data_frame.sql_dialect)
        destructive_reasons = get_destructive_reasons(parsed_query)
        if destructive_reasons:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"SQL query contains destructive operations: {destructive_reasons}",
            )

        # Execute SQL directly - LLM already generated physical SQL
        return await execute_sql_and_create_result(
            con,
            data_frame,
            full_sql_query,
            full_sql_query,  # logical = physical for database queries
        )
