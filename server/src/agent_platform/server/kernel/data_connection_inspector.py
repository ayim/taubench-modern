import typing
from typing import Any

from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import ValidationMessage
from agent_platform.server.kernel.ibis_utils import DataConnectionInspectorError

if typing.TYPE_CHECKING:
    import pyarrow

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
        data_connection: "DataConnection",
        request: "DataConnectionsInspectRequest",
    ):
        self.data_connection = data_connection
        self.request = request
        self._connection: Any | None = None

    @property
    async def connection(self) -> "AsyncIbisConnection":
        if self._connection is None:
            self._connection = await self.create_ibis_connection(self.data_connection)
        return self._connection

    async def inspect_connection(
        self,
    ) -> "DataConnectionsInspectResponse":
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
    async def create_ibis_connection(cls, data_connection: "DataConnection") -> "AsyncIbisConnection":
        from agent_platform.server.kernel.ibis_utils import create_ibis_connection

        return await create_ibis_connection(data_connection)

    async def _get_table(self, table_spec: "TableToInspect") -> "AsyncIbisTable":
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
            raise TableNotFoundError(table_spec.name, str(e)) from e
        return table

    async def _validate_table(self, table_spec: "TableToInspect") -> ValidationMessage | None:
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
        self, table: "AsyncIbisTable", column_expression: str
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
    async def _get_all_tables(cls, connection: "AsyncIbisConnection") -> "list[TableToInspect]":
        """Get all tables from the connection."""
        from agent_platform.core.payloads.data_connection import TableToInspect

        tables = await connection.list_tables()

        table_specs = []
        for table_name in tables:
            # For most databases, we can get schema info from the connection
            # Note: Some backends (like MySQL) execute queries when accessing these properties,
            # so we must use worker threads and handle gracefully if not available.
            schema = None
            database = None

            # Try to get current_schema (may not exist or may fail)
            try:
                schema = await connection.get_current_schema()
            except (AttributeError, Exception) as e:
                logger.info(
                    "Could not retrieve current_schema from connection",
                    backend=type(connection).__name__,
                    error=str(e),
                )

            # Try to get current_database (may not exist or may fail)
            try:
                database = await connection.get_current_database()
            except (AttributeError, Exception) as e:
                logger.info(
                    "Could not retrieve current_database from connection",
                    backend=type(connection).__name__,
                    error=str(e),
                )

            table_specs.append(
                TableToInspect(
                    name=table_name,
                    database=database,
                    schema=schema,
                )
            )

        return table_specs

    def _select_with_limit(
        self,
        table: "AsyncIbisTable",
        columns_to_inspect: list[str],
        n_sample_rows: int,
    ) -> "AsyncIbisTable":
        """Build a select query with limit.

        Note: extracted just so that we can mock it easily for testing
        purposes (to simulate errors when inspecting columns).

        This method does NOT need asyncio.to_thread because it only constructs
        an ibis expression (lazy evaluation, no I/O). The actual I/O happens
        when the expression is executed via .to_pyarrow() which IS wrapped.
        """
        return table.select(columns_to_inspect).limit(n_sample_rows)

    async def _fetch_sample_data_for_all_columns(
        self, table: "AsyncIbisTable", columns_to_inspect: list[str]
    ) -> "pyarrow.Table":
        """Fetch sample data for all columns at once.

        Args:
            table: The async table wrapper
            columns_to_inspect: List of column names to inspect

        Returns:
            PyArrow table with sample data

        Raises:
            Exception: If query execution fails
        """
        # Build query using async proxy (returns AsyncIbisExpression)
        sample_query = self._select_with_limit(table, columns_to_inspect, self.request.n_sample_rows)
        # Use async proxy's to_pyarrow which handles backend routing
        return await sample_query.to_pyarrow()

    async def _fetch_sample_data_per_column(
        self, table: "AsyncIbisTable", columns_to_inspect: list[str], table_name: str
    ) -> dict[str, "pyarrow.Table | None"]:
        """Fetch sample data for each column individually (fallback when bulk fetch fails).

        Args:
            table: The async table wrapper
            columns_to_inspect: List of column names to inspect
            table_name: Name of the table (for logging)

        Returns:
            Dictionary mapping column names to their sample data (or None if failed)
        """
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        sample_table_dict: dict[str, pyarrow.Table | None] = {}
        for column_name in columns_to_inspect:
            try:
                # Build query using async proxy (returns AsyncIbisExpression)
                sample_query = table.select(column_name).limit(self.request.n_sample_rows)
                # Use async proxy's to_pyarrow which handles backend routing
                result = await sample_query.to_pyarrow()
                sample_table_dict[column_name] = result
            except IbisDbCallNotInWorkerThreadError as e:
                raise e
            except Exception as e:
                # Get column type in a non-blocking way
                try:
                    col_type = await table[column_name].type()
                except Exception:
                    col_type = "unknown"
                logger.error(f"Error inspecting table {table_name} column {column_name} column type: {col_type}: {e!r}")
                sample_table_dict[column_name] = None
        return sample_table_dict

    async def _inspect_table(self, connection: "AsyncIbisConnection", table_spec: "TableToInspect") -> "TableInfo":
        """Inspect a specific table and return its metadata."""
        import pyarrow

        from agent_platform.core.payloads.data_connection import TableInfo
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        table = await connection.table(table_spec.name)
        column_names = table.columns

        # Filter columns to inspect based on request
        columns_to_inspect = [
            col for col in column_names if table_spec.columns_to_inspect is None or col in table_spec.columns_to_inspect
        ]

        # Fetch sample data if there are columns to inspect
        sample_table: pyarrow.Table | dict[str, pyarrow.Table | None] | None = None
        if columns_to_inspect:
            try:
                sample_table = await self._fetch_sample_data_for_all_columns(table, columns_to_inspect)
            except IbisDbCallNotInWorkerThreadError:
                raise
            except Exception as e:
                logger.error(f"Error inspecting table {table_spec.name}: {e!r}")
                # Fallback: try fetching columns one by one
                sample_table = await self._fetch_sample_data_per_column(table, columns_to_inspect, table_spec.name)

        # Inspect each column and collect metadata
        columns = []
        for column_name in columns_to_inspect:
            column_info = await self._inspect_column(table, column_name, sample_table)
            columns.append(column_info)

        return TableInfo(
            name=table_spec.name,
            database=table_spec.database,
            schema=table_spec.schema,
            description=None,  # TODO: Add description extraction if available
            columns=columns,
        )

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
        table: "AsyncIbisTable",
        column_name: str,
        sample_table: "pyarrow.Table | dict[str, pyarrow.Table | None] | None",
    ) -> "ColumnInfo":
        """Inspect a specific column and return its metadata."""
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
                    f"Arrow error for column {column_name}, marking column with 'unknown' type",
                    column=column_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                column_type = "unknown"
            else:
                raise
        if sample_table is not None:
            if isinstance(sample_table, dict):
                sample_table = sample_table[column_name]

            if not sample_table:
                sample_values = None
            else:
                arrow_sample_values = sample_table[column_name].to_pylist()
                # Convert to valid JSON types and sanitize (remove None and null bytes)
                sample_values = []
                for v in arrow_sample_values:
                    if v is not None:
                        converted = convert_to_valid_json_types(v)
                        sanitized = self._sanitize_sample_value(converted)
                        if sanitized is not None:
                            sample_values.append(sanitized)
        else:
            sample_values = None

        return ColumnInfo(
            name=column_name,
            data_type=column_type,
            sample_values=sample_values,
            primary_key=None,  # TODO: Add primary key extraction if available
            unique=None,  # TODO: Add unique if available
            description=None,  # TODO: Add description extraction if available
            synonyms=None,  # TODO: Add synonyms if available
        )
