from __future__ import annotations

import asyncio
import typing
from typing import Any

from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import ValidationMessage
from agent_platform.server.kernel.ibis_utils import DataConnectionInspectorError

if typing.TYPE_CHECKING:
    import asyncio

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        ColumnInfo,
        DataConnectionsInspectRequest,
        DataConnectionsInspectResponse,
        TableInfo,
        TableToInspect,
    )
    from agent_platform.server.kernel.ibis_async_proxy import (
        AsyncIbisConnection,
        AsyncIbisTable,
    )

logger = get_logger(__name__)

# Sentinel key used to indicate a table-level error (as opposed to column-level errors)
# in the validation results dictionary
TABLE_VALIDATION_ERROR_KEY = "__TABLE_VALIDATION_ERROR__"

# Maximum length for sample values to avoid storing huge strings in database
MAX_SAMPLE_VALUE_LENGTH = 1024

# Connection pool size for concurrent column inspection
# This limits the number of concurrent database connections used when inspecting columns
CONNECTION_POOL_SIZE = 5

# Maximum time to wait for row count query (seconds)
ROW_COUNT_TIMEOUT = 10.0


class TableNotFoundError(DataConnectionInspectorError):
    """Error raised when a table is not found in the connection."""

    def __init__(self, table_name: str, details: str):
        super().__init__(f"Table {table_name} not found: {details}")
        self.table_name = table_name
        self.details = details


class DataConnectionInspector:
    """Inspector for extracting metadata from data connections using ibis."""

    def __init__(
        self,
        data_connection: DataConnection,
        request: DataConnectionsInspectRequest,
    ):
        self.data_connection = data_connection
        self.request = request
        self._connection: Any | None = None
        self._connection_pool: asyncio.Queue[AsyncIbisConnection] | None = None
        self._pool_connections: list[AsyncIbisConnection] = []

    @property
    async def connection(self) -> AsyncIbisConnection:
        if self._connection is None:
            self._connection = await self.create_ibis_connection(self.data_connection)
        return self._connection

    async def __aenter__(self) -> DataConnectionInspector:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any | None,
    ) -> bool | None:
        """Async context manager exit - closes all connections."""
        await self.close()
        return None  # Don't suppress exceptions

    async def close(self) -> None:
        """Close all connections (main connection and connection pool).

        This method is called automatically when using the context manager.
        Can also be called explicitly for cleanup.
        """
        # Close connection pool
        await self.close_connection_pool()

        # Close main connection
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception as e:
                logger.warning(
                    "Error closing main connection",
                    error=str(e),
                    error_type=type(e).__name__,
                )
            finally:
                self._connection = None

    async def _get_connection_pool(self) -> asyncio.Queue[AsyncIbisConnection]:
        """Get or create the connection pool for concurrent column inspection.

        The pool is created lazily on first use and reused across multiple table/column operations.
        """
        if self._connection_pool is None:
            self._connection_pool = asyncio.Queue(maxsize=CONNECTION_POOL_SIZE)
            # Create connections upfront
            for _ in range(CONNECTION_POOL_SIZE):
                conn = await self.create_ibis_connection(self.data_connection)
                self._pool_connections.append(conn)
                await self._connection_pool.put(conn)
        return self._connection_pool

    async def close_connection_pool(self) -> None:
        """Close all connections in the connection pool.

        Should be called when done with all column inspection operations to free resources.
        """
        if self._pool_connections:
            for conn in self._pool_connections:
                try:
                    await conn.close()
                except Exception as e:
                    logger.warning(
                        "Error closing connection from pool",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
            self._pool_connections.clear()
            self._connection_pool = None

    async def inspect_connection(
        self,
    ) -> DataConnectionsInspectResponse:
        """
        Inspect a data connection and return table/column metadata.

        Returns:
            DataConnectionsInspectResponse with table and column information
        """
        import time

        from agent_platform.core.payloads.data_connection import (
            DataConnectionsInspectResponse,
        )

        connection = await self.connection

        # Get all tables if none specified
        if not self.request.tables_to_inspect:
            initial_time = time.monotonic()
            logger.info("Collecting tables to inspect")
            tables_to_inspect = await self._get_all_tables(connection)
            logger.info(f"Got all tables in {time.monotonic() - initial_time:.2f} seconds")
        else:
            tables_to_inspect = self.request.tables_to_inspect

        table_infos = []
        if self.request.inspect_columns:
            for i, table_spec in enumerate(tables_to_inspect):
                initial_time = time.monotonic()
                logger.info(f"Inspecting table {table_spec.name} ({i + 1} of {len(tables_to_inspect)})")
                table_info = await self._inspect_table(connection, table_spec)
                logger.info(
                    f"Inspected table {table_spec.name} ({i + 1} of {len(tables_to_inspect)}) in "
                    f"{time.monotonic() - initial_time:.2f} seconds"
                )
                table_infos.append(table_info)

        return DataConnectionsInspectResponse(tables=table_infos)

    @classmethod
    async def create_ibis_connection(cls, data_connection: DataConnection) -> AsyncIbisConnection:
        from agent_platform.server.kernel.ibis_utils import create_ibis_connection

        return await create_ibis_connection(data_connection)

    async def _get_table(self, table_spec: TableToInspect) -> AsyncIbisTable:
        """
        Get a table from the connection.

        Returns:
            AsyncIbisTable: Async table wrapper if the table is found.

        Raises:
            TableNotFoundError: If the table is not found.
        """
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        connection: AsyncIbisConnection = await self.connection
        try:
            table: AsyncIbisTable = await connection.table(table_spec.name)
        except IbisDbCallNotInWorkerThreadError as e:
            raise e
        except Exception as e:
            # Extract full error details from exception chain
            error_details = str(e)
            if e.__cause__:
                # Include the underlying database error (e.g., Snowflake ProgrammingError)
                error_details = f"{error_details}\n\nCaused by: {e.__cause__!s}"
            raise TableNotFoundError(table_spec.name, error_details) from e
        return table

    async def _validate_table(self, table_spec: TableToInspect) -> ValidationMessage | None:
        """
        Validate a table and return a structured error if it is not found or an error
        occurs accessing it. If a table is provided, it will be used instead of
        getting it from the connection.
        """
        from agent_platform.core.data_frames.semantic_data_model_types import (
            ValidationMessageKind,
            ValidationMessageLevel,
        )
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        try:
            # Just try to see if the table is there.
            table = await self._get_table(table_spec)
            _ = table.columns
        except IbisDbCallNotInWorkerThreadError as e:
            raise e
        except TableNotFoundError as e:
            return ValidationMessage(
                message=str(e),
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.DATA_CONNECTION_TABLE_NOT_FOUND,
            )
        except Exception as e:
            return ValidationMessage(
                message=f"Error accessing table: {e!s}",
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.DATA_CONNECTION_TABLE_ACCESS_ERROR,
            )
        return None

    async def validate_tables_exist(self) -> dict[str, ValidationMessage]:
        """
        Validate that tables specified in the request exist in the connection.

        Returns:
            Dictionary mapping table names to structured validation messages.
        """
        # Check if tables are specified in the request
        if not self.request.tables_to_inspect:
            raise ValueError("No tables specified in request for validation")

        errors: dict[str, ValidationMessage] = {}
        # Validate each table in the request
        for table_spec in self.request.tables_to_inspect:
            error = await self._validate_table(table_spec)
            if error:
                errors[table_spec.name] = error

        return errors

    async def _validate_column_expression(
        self, table: AsyncIbisTable, column_expression: str
    ) -> ValidationMessage | None:
        """Extracted for testing purposes."""
        from agent_platform.core.data_frames.semantic_data_model_types import (
            ValidationMessageKind,
            ValidationMessageLevel,
        )
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        try:
            await table.select(column_expression).limit(0).execute()
        except IbisDbCallNotInWorkerThreadError as e:
            raise e
        except Exception as e:
            return ValidationMessage(
                message=f"Invalid column expression: {e!s}",
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.DATA_CONNECTION_COLUMN_INVALID_EXPRESSION,
            )
        return None

    async def validate_column_expressions(self) -> dict[str, dict[str, ValidationMessage]]:
        """
        Validate that column expressions specified in the request can be evaluated.

        All tables in the request must have columns_to_inspect specified, otherwise
        a ValueError is raised (columns from the schema are always valid, so there's
        nothing to validate).

        Returns:
            Dictionary mapping table names to a dict of column names to structured
            validation messages. Empty dict if all columns are valid. If a table is not
            found, the error will be stored in the `_table` key and columns will not be
            validated.
        """
        # Check if tables are specified in the request
        if not self.request.tables_to_inspect:
            raise ValueError("No tables specified in request for validation")

        # Ensure all tables have columns to validate
        for table_spec in self.request.tables_to_inspect:
            if table_spec.columns_to_inspect is None:
                raise ValueError(f"Table '{table_spec.name}' has no columns_to_inspect specified for validation")

        errors: dict[str, dict[str, ValidationMessage]] = {}

        # Validate columns for each table in the request
        for table_spec in self.request.tables_to_inspect:
            table_errors: dict[str, ValidationMessage] = {}
            columns_to_validate = table_spec.columns_to_inspect
            assert columns_to_validate is not None  # Already checked above

            error = await self._validate_table(table_spec)
            if error:
                errors[table_spec.name] = {TABLE_VALIDATION_ERROR_KEY: error}
                continue

            table = await self._get_table(table_spec)  # already validated above

            # Validate each column expression
            for column_expr in columns_to_validate:
                # Check if it's a simple column name first
                if column_expr in table.columns:
                    continue

                # Try to evaluate the expression by selecting it
                error = await self._validate_column_expression(table, column_expr)
                if error:
                    table_errors[column_expr] = error

            # Only add to errors dict if there are column errors
            if table_errors:
                errors[table_spec.name] = table_errors

        return errors

    @classmethod
    async def _get_all_tables(cls, connection: AsyncIbisConnection) -> list[TableToInspect]:
        """Get all tables from the connection."""
        from agent_platform.core.payloads.data_connection import TableToInspect

        tables = await connection.list_tables()

        # Get schema and database info once (connection-level properties, not per-table)
        # Note: Some backends (like MySQL) execute queries when accessing these properties,
        # so we must use worker threads and handle gracefully if not available.
        schema = None
        database = None

        # Try to get current_schema (may not exist or may fail)
        # Note: Some backends (e.g., PostgreSQL) don't expose current_schema as an attribute
        try:
            schema = await connection.get_current_schema()
        except (AttributeError, Exception) as e:
            logger.debug(
                "Could not retrieve current_schema from connection (expected for some backends)",
                backend=type(connection).__name__,
                error=str(e),
            )

        # Try to get current_database (may not exist or may fail)
        # Note: Some backends don't expose current_database as an attribute
        try:
            database = await connection.get_current_database()
        except (AttributeError, Exception) as e:
            logger.debug(
                "Could not retrieve current_database from connection (expected for some backends)",
                backend=type(connection).__name__,
                error=str(e),
            )

        # Create table specs using the same schema/database for all tables
        table_specs = []
        for table_name in tables:
            table_specs.append(
                TableToInspect(
                    name=table_name,
                    database=database,
                    schema=schema,
                )
            )

        return table_specs

    async def _fetch_distinct_column_samples(
        self, table: AsyncIbisTable, column_name: str, n_sample_rows: int
    ) -> list[Any]:
        """Fetch distinct sample values for a single column from the database.

        Uses DISTINCT + LIMIT to get unique values directly from the database.
        No client-side processing needed - the database handles uniqueness.

        Args:
            table: The async table wrapper
            column_name: Name of the column to sample
            n_sample_rows: Number of distinct values to fetch

        Returns:
            List of sample values (may contain None)
        """
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        try:
            # Let the database handle uniqueness with DISTINCT
            # This pushes the work to the database instead of doing it client-side
            query = table.select(column_name).distinct().limit(n_sample_rows)
            result = await query.to_pyarrow_unsafe()
            samples = result[column_name].to_pylist()
            logger.debug(
                "Fetched distinct column samples",
                column=column_name,
                requested=n_sample_rows,
                received=len(samples),
            )
            return samples
        except IbisDbCallNotInWorkerThreadError as e:
            raise e
        except Exception as e:
            logger.warning(
                "Failed to fetch distinct column samples",
                column=column_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    async def _inspect_table(self, connection: AsyncIbisConnection, table_spec: TableToInspect) -> TableInfo:
        """Inspect a specific table and return its metadata."""
        from agent_platform.core.payloads.data_connection import TableInfo

        # Use _get_table to get proper error handling with TableNotFoundError
        # We use the main connection for getting table metadata (schema, column names)
        table = await self._get_table(table_spec)
        column_names = table.columns

        # Filter columns to inspect based on request
        columns_to_inspect = [
            col for col in column_names if table_spec.columns_to_inspect is None or col in table_spec.columns_to_inspect
        ]

        # Sample columns concurrently using instance-level connection pool to avoid transaction nesting
        columns: list[ColumnInfo] = []
        if columns_to_inspect:
            # Use instance-level connection pool (created lazily, reused across tables)
            connection_pool = await self._get_connection_pool()

            # Create tasks for all columns
            tasks = [
                self._inspect_column_with_pool_connection(table_spec, table, column_name, connection_pool)
                for column_name in columns_to_inspect
            ]
            column_results = await asyncio.gather(*tasks)

            # Process results - _inspect_column_with_pool_connection always returns ColumnInfo
            for _column_name, result in zip(columns_to_inspect, column_results, strict=True):
                columns.append(result)

        return TableInfo(
            name=table_spec.name,
            database=table_spec.database,
            schema=table_spec.schema,
            description=None,  # TODO: Add description extraction if available
            columns=columns,
        )

    async def _inspect_column_with_pool_connection(
        self,
        table_spec: TableToInspect,
        table: AsyncIbisTable,
        column_name: str,
        connection_pool: asyncio.Queue[AsyncIbisConnection],
    ) -> ColumnInfo:
        """Inspect a single column using a connection from the pool to avoid transaction nesting.

        This method acquires a connection from the pool, uses it for inspection,
        then returns it to the pool. This prevents transaction nesting errors while
        efficiently reusing connections.

        If an error occurs during inspection, returns a ColumnInfo with data_type="unknown"
        and sample_values=None rather than raising an exception.

        Args:
            table_spec: Specification of the table being inspected
            table: The async table wrapper from the main connection (used for column type lookup)
            column_name: Name of the column to inspect
            connection_pool: Queue containing available connections from the pool

        Returns:
            ColumnInfo - always returns a ColumnInfo, even if inspection partially failed
        """
        from agent_platform.core.payloads.data_connection import ColumnInfo

        # Acquire a connection from the pool
        pool_connection = await connection_pool.get()
        column_type = "unknown"  # Default to unknown, will be updated if we can determine it
        try:
            # Get the table from the pool connection (separate from main connection to avoid transaction nesting)
            pool_table = await pool_connection.table(table_spec.name)

            # Get column type from the original table (no I/O, just metadata)
            try:
                column_type = str(await table[column_name].type())
            except Exception as e:
                # Fallback: try from pool table if original fails
                if "255003" in str(e) or "Arrow" in str(e):
                    logger.warning(
                        "Arrow error for column, marking column with 'unknown' type",
                        column=column_name,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    column_type = "unknown"
                else:
                    try:
                        column_type = str(await pool_table[column_name].type())
                    except Exception:
                        # If both attempts fail, default to "unknown"
                        column_type = "unknown"

            # Fetch samples using the pool connection
            try:
                column_info = await self._inspect_column(pool_table, column_name)
                # Update the column type (in case we got it from pool_table)
                return ColumnInfo(
                    name=column_info.name,
                    data_type=column_type,
                    sample_values=column_info.sample_values,
                    primary_key=column_info.primary_key,
                    unique=column_info.unique,
                    description=column_info.description,
                    synonyms=column_info.synonyms,
                )
            except Exception as e:
                # If inspection fails, return a ColumnInfo with unknown type and no samples
                logger.warning(
                    "Error inspecting column, returning ColumnInfo with unknown type",
                    table=table_spec.name,
                    column=column_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return ColumnInfo(
                    name=column_name,
                    data_type=column_type,
                    sample_values=None,
                    primary_key=None,
                    unique=None,
                    description=None,
                    synonyms=None,
                )
        except Exception as e:
            # If we can't even get the table or connection, return a minimal ColumnInfo
            logger.warning(
                "Error accessing table for column inspection, returning ColumnInfo with unknown type",
                table=table_spec.name,
                column=column_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return ColumnInfo(
                name=column_name,
                data_type=column_type,
                sample_values=None,
                primary_key=None,
                unique=None,
                description=None,
                synonyms=None,
            )
        finally:
            # Return the connection to the pool
            await connection_pool.put(pool_connection)

    def _sanitize_sample_value(self, value: Any) -> Any | None:
        """
        Sanitize a sample value to ensure it can be stored in PostgreSQL JSONB.

        - Filters out values with null bytes (\x00) which cannot be stored in PostgreSQL text/JSONB.
          These commonly appear in MySQL spatial/binary data types (POINT, GEOMETRY, BLOB, etc.)
        - Truncates long strings to max 1024 characters to avoid storing huge values

        Args:
            value: Sample value to sanitize

        Returns:
            Sanitized value, or None if the value contains binary data (null bytes)
        """
        if isinstance(value, str):
            # Check for null bytes - indicates binary data, return None
            if "\x00" in value:
                return None

            # Truncate long strings to avoid storing huge values in database
            if len(value) > MAX_SAMPLE_VALUE_LENGTH:
                return value[:MAX_SAMPLE_VALUE_LENGTH]

        return value

    async def _inspect_column(
        self,
        table: AsyncIbisTable,
        column_name: str,
    ) -> ColumnInfo:
        """Inspect a specific column and return its metadata.

        Fetches distinct sample values directly from the database using DISTINCT + LIMIT.
        No client-side re-sampling or deduplication needed.
        """
        from agent_platform.core.payloads.data_connection import ColumnInfo
        from agent_platform.server.data_frames.data_node import (
            convert_to_valid_json_types,
        )

        try:
            column_type = str(await table[column_name].type())
        except Exception as e:
            # For Snowflake, if .type() fails with Arrow error, use a fallback
            # Error 255003: "Conversion from Snowflake VARIANT/OBJECT/ARRAY to Arrow not supported"
            if "255003" in str(e) or "Arrow" in str(e):
                logger.warning(
                    "Arrow error for column, marking column with 'unknown' type",
                    column=column_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                column_type = "unknown"
            else:
                raise

        # Fetch distinct samples directly from database if sampling is requested
        sample_values: list[Any] | None = None
        if self.request.n_sample_rows > 0:
            raw_samples = await self._fetch_distinct_column_samples(table, column_name, self.request.n_sample_rows)
            # Only sanitize (remove null bytes, truncate long strings) and convert to JSON types
            # Database already handled uniqueness with DISTINCT, but truncation could create duplicates,
            # so we use a set to deduplicate while preserving first-seen order
            seen: set[Any] = set()
            sample_values = []
            for v in raw_samples:
                if v is not None:
                    converted = convert_to_valid_json_types(v)
                    sanitized = self._sanitize_sample_value(converted)
                    if sanitized is not None and sanitized not in seen:
                        seen.add(sanitized)
                        sample_values.append(sanitized)

        return ColumnInfo(
            name=column_name,
            data_type=column_type,
            sample_values=sample_values,
            primary_key=None,  # TODO: Add primary key extraction if available
            unique=None,  # TODO: Add unique if available
            description=None,  # TODO: Add description extraction if available
            synonyms=None,  # TODO: Add synonyms if available
        )

    async def fetch_table_row_count(self, table_spec: TableToInspect) -> int | None:
        """Fetch row count for a specific table with timeout and error handling.

        Args:
            table_spec: Specification of the table to profile

        Returns:
            Row count as integer, or None if fetch fails or times out

        Raises:
            TableNotFoundError: If the table is not found.
        """
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        try:
            table = await self._get_table(table_spec)
            row_count = await asyncio.wait_for(
                table.execute_count(),
                timeout=ROW_COUNT_TIMEOUT,
            )
            return row_count
        except (IbisDbCallNotInWorkerThreadError, TableNotFoundError):
            # Re-raise immediately - these errors should propagate
            raise
        except (TimeoutError, Exception) as e:
            # Log with appropriate message based on exception type
            if isinstance(e, TimeoutError):
                logger.warning(
                    "Row count query timed out",
                    table=table_spec.name,
                    timeout=ROW_COUNT_TIMEOUT,
                )
            else:
                logger.warning(
                    "Failed to fetch row count",
                    table=table_spec.name,
                    error=str(e),
                    error_type=type(e).__name__,
                )

            return None

    async def fetch_column_sample(
        self, table_spec: TableToInspect, column_name: str, n_sample_rows: int = 10
    ) -> tuple[str, list[Any] | None]:
        """Fetch sample values for a single column in a table.

        Args:
            table_spec: Specification of the table to profile
            column_name: Name of the column to fetch samples for
            n_sample_rows: Number of sample values to fetch (default: 10)

        Returns:
            Tuple of (data_type, sample_values)
            - data_type: Column data type as string
            - sample_values: List of sample values, or None if fetch fails

        Raises:
            TableNotFoundError: If the table is not found.
        """
        try:
            table = await self._get_table(table_spec)

            # Verify column exists
            if column_name not in table.columns:
                logger.warning(
                    "Column not found in table",
                    table=table_spec.name,
                    column=column_name,
                )
                return "unknown", None

            # Get column type
            try:
                data_type = str(await table[column_name].type())
            except Exception as e:
                logger.warning(
                    "Failed to get column type",
                    table=table_spec.name,
                    column=column_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                data_type = "unknown"

            # Fetch samples
            sample_values = await self._fetch_distinct_column_samples(table, column_name, n_sample_rows)

            return data_type, sample_values
        except TableNotFoundError:
            # Re-raise immediately - this error should propagate
            raise
        except Exception as e:
            logger.warning(
                "Failed to fetch column sample",
                table=table_spec.name,
                column=column_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return "unknown", None
