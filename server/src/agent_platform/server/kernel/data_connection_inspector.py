import asyncio
import typing
from typing import Any

from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import ValidationMessage
from agent_platform.server.kernel.ibis_utils import DataConnectionInspectorError

if typing.TYPE_CHECKING:
    import pyarrow
    from ibis import Table

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        ColumnInfo,
        DataConnectionsInspectRequest,
        DataConnectionsInspectResponse,
        TableInfo,
        TableToInspect,
    )

logger = get_logger(__name__)

# Sentinel key used to indicate a table-level error (as opposed to column-level errors)
# in the validation results dictionary
TABLE_VALIDATION_ERROR_KEY = "__TABLE_VALIDATION_ERROR__"


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
    async def connection(self) -> Any:
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
                logger.info(
                    f"Inspecting table {table_spec.name} ({i + 1} of {len(tables_to_inspect)})"
                )
                table_info = await self._inspect_table(connection, table_spec)
                logger.info(
                    f"Inspected table {table_spec.name} ({i + 1} of {len(tables_to_inspect)}) in "
                    f"{time.monotonic() - initial_time:.2f} seconds"
                )
                table_infos.append(table_info)

        return DataConnectionsInspectResponse(tables=table_infos)

    @classmethod
    async def create_ibis_connection(cls, data_connection: "DataConnection") -> Any:
        from agent_platform.server.kernel import ibis_utils

        return await ibis_utils.create_ibis_connection(data_connection)

    async def _get_table(self, table_spec: "TableToInspect") -> "Table":
        """
        Get a table from the connection.

        Returns:
            Table: Table object if the table is found.

        Raises:

        """
        import ibis

        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        connection = await self.connection
        try:
            # Try to get the table
            table = await asyncio.to_thread(connection.table, table_spec.name)
        except IbisDbCallNotInWorkerThreadError as e:
            raise e
        except Exception as e:
            raise TableNotFoundError(table_spec.name, str(e)) from e
        return typing.cast(ibis.Table, table)

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
        self, table: "Table", column_expression: str
    ) -> ValidationMessage | None:
        """Extracted for testing purposes."""
        from agent_platform.core.data_frames.semantic_data_model_types import (
            ValidationMessageKind,
            ValidationMessageLevel,
        )
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        try:
            await asyncio.to_thread(table.select(column_expression).limit(0).execute)
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
                raise ValueError(
                    f"Table '{table_spec.name}' has no columns_to_inspect specified for validation"
                )

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
    async def _get_all_tables(cls, connection: Any) -> "list[TableToInspect]":
        """Get all tables from the connection."""
        from agent_platform.core.payloads.data_connection import TableToInspect

        # Get list of tables from ibis (blocking I/O operation)
        tables = await asyncio.to_thread(connection.list_tables)

        table_specs = []
        for table_name in tables:
            # For most databases, we can get schema info from the connection
            schema = None
            database = None

            if hasattr(connection, "current_schema"):
                schema = connection.current_schema
            if hasattr(connection, "current_database"):
                database = connection.current_database

            table_specs.append(
                TableToInspect(
                    name=table_name,
                    database=database,
                    schema=schema,
                )
            )

        return table_specs

    def _select_with_limit(self, table, columns_to_inspect, n_sample_rows):
        """
        Note: extracted just so that we can mock it easily for testing
        purposes (to simulate errors when inspecting columns).

        This method does NOT need asyncio.to_thread because it only constructs
        an ibis expression (lazy evaluation, no I/O). The actual I/O happens
        when the expression is executed via .to_pyarrow() which IS wrapped.
        """
        return table.select(columns_to_inspect).limit(n_sample_rows)

    async def _inspect_table(  # noqa: C901,PLR0912
        self, connection: Any, table_spec: "TableToInspect"
    ) -> "TableInfo":
        """Inspect a specific table and return its metadata."""
        import pyarrow

        from agent_platform.core.payloads.data_connection import TableInfo
        from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

        # Get the table reference (blocking I/O)
        table = await asyncio.to_thread(connection.table, table_spec.name)

        # Get column information
        columns = []
        columns_to_inspect = []

        # Get column names from table schema (blocking I/O)
        schema = await asyncio.to_thread(table.schema)
        column_names = schema.names

        for column_name in column_names:
            # Skip columns if specific columns are requested and this one isn't in the list
            if (
                table_spec.columns_to_inspect is not None
                and column_name not in table_spec.columns_to_inspect
            ):
                continue
            columns_to_inspect.append(column_name)

        sample_table: pyarrow.Table | dict[str, pyarrow.Table | None] | None = None
        if columns_to_inspect:
            # Execute query to get sample values
            try:
                sample_query = self._select_with_limit(
                    table, columns_to_inspect, self.request.n_sample_rows
                )

                # For Snowflake, use raw cursor to avoid Arrow format issues
                # with VARIANT/OBJECT types
                from agent_platform.server.utils.snowflake_utils import (
                    execute_snowflake_query_raw,
                    is_snowflake_backend,
                )

                if is_snowflake_backend(sample_query):
                    sample_table = await execute_snowflake_query_raw(sample_query)
                else:
                    sample_table_arrow: pyarrow.Table = await asyncio.to_thread(
                        sample_query.to_pyarrow
                    )
                    sample_table = sample_table_arrow
            except IbisDbCallNotInWorkerThreadError as e:
                raise e
            except Exception as e:
                logger.error(f"Error inspecting table {table_spec.name}: {e!r}")

                # Ok, we haven't able to do a select with many columns (something went wrong),
                # let's try columns one by one -- note: this error can be expected if there's an
                # issue with the column type (for instance, if the column is an int but ibis
                # got it as a string).
                #
                # Example:
                # Error inspecting table film column release_year column type: unknown(
                #   DataType(this=Type.USERDEFINED, kind=year)): ArrowTypeError("Expected bytes,
                #   got a 'int' object")
                from agent_platform.server.utils.snowflake_utils import (
                    execute_snowflake_query_raw,
                    is_snowflake_backend,
                )

                sample_table_dict: dict[str, pyarrow.Table | None] = {}
                for column_name in columns_to_inspect:
                    try:
                        sample_query = table.select(column_name).limit(self.request.n_sample_rows)
                        if is_snowflake_backend(sample_query):
                            result = await execute_snowflake_query_raw(sample_query)
                            sample_table_dict[column_name] = result
                        else:
                            sample_table_dict[column_name] = await asyncio.to_thread(
                                sample_query.to_pyarrow
                            )
                    except IbisDbCallNotInWorkerThreadError as e:
                        raise e
                    except Exception as e:
                        # Get column type in a non-blocking way
                        def _get_col_type(col_name=column_name):
                            return table[col_name].type()

                        try:
                            col_type = await asyncio.to_thread(_get_col_type)
                        except Exception:
                            col_type = "unknown"
                        logger.error(
                            f"Error inspecting table {table_spec.name} column {column_name} "
                            f"column type: {col_type}: {e!r}"
                        )
                        sample_table_dict[column_name] = None
                sample_table = sample_table_dict

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

    async def _inspect_column(
        self,
        table: Any,
        column_name: str,
        sample_table: "pyarrow.Table | dict[str, pyarrow.Table | None] | None",
    ) -> "ColumnInfo":
        """Inspect a specific column and return its metadata."""
        from agent_platform.core.payloads.data_connection import ColumnInfo
        from agent_platform.server.data_frames.data_node import (
            convert_to_valid_json_types,
        )

        # Get column type (blocking I/O)
        try:
            column_type = await asyncio.to_thread(lambda: str(table[column_name].type()))
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
                # Remove None values
                sample_values = [
                    convert_to_valid_json_types(v) for v in arrow_sample_values if v is not None
                ]
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
