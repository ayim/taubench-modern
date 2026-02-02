import datetime
import typing
from abc import abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, Protocol

import structlog

if typing.TYPE_CHECKING:
    import pyarrow
    from sema4ai.actions import Row, Table

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_reader import DataReaderSheet
    from agent_platform.server.kernel.ibis import AsyncIbisTable

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Default page size for slice operations when limit is not specified.
# This prevents accidental loading of entire large datasets into memory.
DEFAULT_SLICE_LIMIT = 1000

# Maximum allowed limit for slice operations to prevent abuse.
# Use limit=-1 to explicitly fetch all rows (bypasses this cap).
MAX_SLICE_LIMIT = 100_000

# Default number of rows to return for sampling operations.
# This provides a reasonable sample size for previews and metadata operations.
DEFAULT_SAMPLE_ROWS = 100

# Maximum allowed rows for sampling operations to prevent memory exhaustion.
# Use num_samples=-1 to explicitly fetch all rows (bypasses this cap).
MAX_SAMPLE_ROWS = 1000


@dataclass(
    frozen=True,
    repr=True,
    eq=True,
    unsafe_hash=True,
    slots=True,
)
class SupportedIbisBackends:
    """
    We need to be able to make a "unique" object that represents the backend used
    to access the data.

    "duckdb" is meant for:
    - in memory data frames (as they're manterialized in duckdb)
    - files (also materialized in duckdb)

    "data-connection" is meant for data connections (i.e.: a database connection).
    Here, we also need to store the data_connection_id and database (we should be
    able to query a different schema from the same database, but for multiple
    databases we need to materialize those contents and do some federation).
    """

    backend: Literal["duckdb", "data-connection"]

    # The data_connection_id of the data connection
    data_connection_id: str | None = None


# Simple backends
DUCK_DB_BACKEND = SupportedIbisBackends(backend="duckdb")


# Backend based on the data connection
@lru_cache(maxsize=100)
def make_data_connection_backend(data_connection_id: str) -> SupportedIbisBackends:
    return SupportedIbisBackends(backend="data-connection", data_connection_id=data_connection_id)


SliceOutputFormat = Literal["json", "parquet", "table"]


def _find_columns_case_insensitive(requested_columns: list[str], available_columns: list[str]) -> list[str]:
    """
    Find column names in a case-insensitive manner.

    Args:
        requested_columns: List of column names to find
        available_columns: List of available column names

    Returns:
        List of actual column names (with correct casing) that match the requested columns

    Raises:
        PlatformError: If any requested columns cannot be found
    """
    from agent_platform.core.errors.base import PlatformError
    from agent_platform.core.errors.responses import ErrorCode

    # Build a mapping from lowercase column name to actual column name for
    # case-insensitive matching
    available_columns_lc_map = {col.lower(): col for col in available_columns}

    # Map requested column_names to their actual casing in the schema
    selected_columns = []
    missing_columns = []

    for col in requested_columns:
        col_lc = col.lower()
        if col_lc in available_columns_lc_map:
            selected_columns.append(available_columns_lc_map[col_lc])
        else:
            missing_columns.append(col)

    if missing_columns:
        raise PlatformError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(f"Columns not found: {missing_columns}. Available columns: {available_columns}"),
        )

    return selected_columns


def _convert_pyarrow_slice_to_format(
    result: "pyarrow.Table",
    offset: int | None,
    limit: int | None,
    column_names: list[str] | None,
    output_format: Literal["json", "parquet", "table", "list[Row]"],
    order_by: str | None,
) -> "bytes | Table | list[Row]":
    available_columns = result.schema.names

    # Apply order by
    if order_by:
        order_by, desc = _parse_order_by(order_by, available_columns)
        result = result.sort_by([(order_by, "descending" if desc else "ascending")])

    # Apply column selection
    if column_names is not None:
        selected_columns = _find_columns_case_insensitive(column_names, available_columns)
        result = result.select(selected_columns)

    # Apply row slicing
    if offset is None:
        offset = 0

    # Handle limit=-1 (fetch all rows) specially - this is the explicit way to request all rows
    if limit == -1:
        result = result[offset:]
    else:
        # Apply default limit if not specified (prevents accidental full table loads)
        if limit is None:
            logger.warning(
                "slice operation called without limit, using default",
                default_limit=DEFAULT_SLICE_LIMIT,
                hint="Pass limit=-1 to explicitly fetch all rows, or specify a limit.",
            )
            limit = DEFAULT_SLICE_LIMIT

        # Cap the limit to prevent abuse
        effective_limit = min(limit, MAX_SLICE_LIMIT)
        if effective_limit != limit:
            logger.info(
                "slice limit capped to maximum",
                requested_limit=limit,
                max_limit=MAX_SLICE_LIMIT,
            )

        result = result[offset : offset + effective_limit]

    return _convert_arrow_to_format(result, output_format)


def convert_pyarrow_slice_to_table_json_or_parquet(
    result: "pyarrow.Table",
    offset: int | None,
    limit: int | None,
    column_names: list[str] | None,
    output_format: Literal["json", "parquet", "table"],
    order_by: str | None,
) -> "bytes | Table":
    from sema4ai.actions import Table

    return typing.cast(
        bytes | Table,
        _convert_pyarrow_slice_to_format(result, offset, limit, column_names, output_format, order_by),
    )


def convert_pyarrow_slice_to_parquet(
    result: "pyarrow.Table",
    offset: int | None,
    limit: int | None,
    column_names: list[str] | None,
    order_by: str | None,
) -> "bytes":
    return typing.cast(
        bytes,
        _convert_pyarrow_slice_to_format(result, offset, limit, column_names, "parquet", order_by),
    )


def convert_pyarrow_slice_to_table(
    result: "pyarrow.Table",
    offset: int | None,
    limit: int | None,
    column_names: list[str] | None,
    order_by: str | None,
) -> "Table":
    from sema4ai.actions import Table

    return typing.cast(
        Table,
        _convert_pyarrow_slice_to_format(result, offset, limit, column_names, "table", order_by),
    )


def convert_pyarrow_slice_to_list_of_rows(
    result: "pyarrow.Table",
    offset: int | None,
    limit: int | None,
    column_names: list[str] | None,
    order_by: str | None,
) -> "list[Row]":
    from sema4ai.actions import Row

    return typing.cast(
        list[Row],
        _convert_pyarrow_slice_to_format(result, offset, limit, column_names, "list[Row]", order_by),
    )


async def _convert_ibis_slice_to_format(
    result: "AsyncIbisTable",
    offset: int,
    limit: int | None,
    column_names: list[str] | None,
    output_format: Literal["json", "parquet", "table"],
    order_by: str | None = None,
) -> "bytes | Table | list[Row]":
    available_columns = list(result.columns)
    if order_by:
        order_by, desc = _parse_order_by(order_by, available_columns)

        op = result[order_by].desc() if desc else result[order_by].asc()
        result = result.order_by(op)

    # Apply column selection (case-insensitive)
    if column_names is not None:
        selected_columns = _find_columns_case_insensitive(column_names, available_columns)
        result = result.select(selected_columns)

    # Normalize offset to 0 if not provided
    if offset is None:
        offset = 0

    # Apply row slicing using ibis operations
    # Handle limit=-1 (fetch all rows) specially - this is the explicit way to request all rows
    if limit == -1:
        result = result[offset:]
    else:
        # Apply default limit if not specified (prevents accidental full table loads)
        if limit is None:
            logger.warning(
                "slice operation called without limit, using default",
                default_limit=DEFAULT_SLICE_LIMIT,
                hint="Pass limit=-1 to explicitly fetch all rows, or specify a limit.",
            )
            limit = DEFAULT_SLICE_LIMIT

        # Cap the limit to prevent abuse
        effective_limit = min(limit, MAX_SLICE_LIMIT)
        if effective_limit != limit:
            logger.info(
                "slice limit capped to maximum",
                requested_limit=limit,
                max_limit=MAX_SLICE_LIMIT,
            )

        result = result[offset : offset + effective_limit]

    # Convert to pyarrow table using adapter (handles DECIMAL→float64 transformation)
    from agent_platform.server.kernel.ibis_table_adapter import IbisTableAdapter

    adapter = IbisTableAdapter(result)
    table = await adapter.to_pyarrow()
    return _convert_arrow_to_format(table, output_format)


def _parse_order_by(order_by: str, available_columns: list[str]) -> tuple[str, bool]:
    """
    Parses the order_by string and returns the column name and whether it's a descending order.
    """
    from agent_platform.core.errors.base import PlatformError

    desc = False
    try:
        # If it can be found, it's not a descending order (corner case:
        # a column that starts with a dash should be handled here).
        column = _find_columns_case_insensitive([order_by], available_columns)[0]
    except PlatformError:
        if order_by.startswith("-"):
            # If it starts with a dash and couldn't be found before, it
            # may be a descending order.
            desc = True
            order_by = order_by[1:]
            column = _find_columns_case_insensitive([order_by], available_columns)[0]
        else:
            raise
    return column, desc


def _convert_arrow_to_format(
    table: Any,
    output_format: Literal["json", "parquet", "table", "list[Row]"],
) -> "bytes | Table | list[Row]":
    import io
    import json

    import pyarrow.parquet

    # Convert to the requested format
    if output_format == "json":
        # Convert to list of dictionaries and then to JSON
        data = []
        columns = list(table)
        for row in zip(*columns, strict=True):
            row_data = {}
            for k, v in zip(table.schema.names, row, strict=True):
                row_data[k] = convert_to_valid_json_types(v.as_py())
            data.append(row_data)

        return json.dumps(data).encode("utf-8")
    elif output_format == "parquet":
        # Convert to parquet format
        buffer = io.BytesIO()
        pyarrow.parquet.write_table(table, buffer)
        return buffer.getvalue()
    elif output_format == "table":
        from sema4ai.actions import Table

        # pyarrow stores things column-based.
        rows = []
        columns = list(table)
        for row in zip(*columns, strict=True):
            rows.append(list(convert_to_valid_json_types(v.as_py()) for v in row))

        new_table = Table(
            columns=list(table.schema.names),
            rows=rows,
        )
        return new_table
    elif output_format == "list[Row]":
        # pyarrow stores things column-based.
        rows: list[Row] = []
        columns = list(table)
        for row in zip(*columns, strict=True):
            rows.append(list(convert_to_valid_json_types(v.as_py()) for v in row))

        return rows
    else:
        raise ValueError(f"Unsupported format: {output_format}")


_VALID_PY_TYPES = int | float | bool | str | None


def convert_to_valid_json_types(
    as_py: Any,
) -> str | int | float | bool | list | dict | None:
    import math

    # Handle NaN and Infinity values before checking type
    # These are not valid JSON values and must be converted to None (JSON null)
    if isinstance(as_py, float) and (math.isnan(as_py) or math.isinf(as_py)):
        return None

    if isinstance(as_py, _VALID_PY_TYPES):
        return as_py
    if isinstance(as_py, datetime.datetime):
        return as_py.isoformat()
    elif isinstance(as_py, bytes):
        # Decode bytes to string (e.g., from MySQL JSON extractions)
        # Use utf-8 with error handling for malformed data
        try:
            return as_py.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback to latin-1 which accepts all byte values
            return as_py.decode("latin-1")
    elif isinstance(as_py, list | tuple):
        return [convert_to_valid_json_types(v) for v in as_py]
    elif isinstance(as_py, dict):
        return {convert_to_valid_json_types(k): convert_to_valid_json_types(v) for k, v in as_py.items()}
    else:
        # Fallback to string (uuid, etc.)
        return str(as_py)


class DataNodeResult(Protocol):
    """
    A protocol for data node results.
    """

    @abstractmethod
    async def list_sample_rows(self, num_samples: int) -> "list[Row]":
        pass

    @abstractmethod
    async def num_rows(self) -> int:
        """Get the number of rows. This may do blocking I/O for some implementations."""

    @property
    @abstractmethod
    def num_columns(self) -> int:
        pass

    @property
    @abstractmethod
    def column_headers(self) -> list[str]:
        pass

    @property
    @abstractmethod
    def columns(self) -> dict[str, str]:
        """Column name -> type mapping.

        Note: Both column_headers and columns exist because fetching
        type information may not be lazy for all backends. Use
        column_headers when only names are needed.
        """

    @property
    @abstractmethod
    def platform_data_frame(self) -> "PlatformDataFrame":
        pass

    @abstractmethod
    def to_ibis(self) -> Any:
        """
        Returns something that can be bound to ibis (such
        as a pyarrow table or an ibis sql query).
        """

    @abstractmethod
    async def slice(
        self,
        offset: int = 0,
        limit: int | None = None,
        column_names: list[str] | None = None,
        *,
        output_format: SliceOutputFormat = "json",
        order_by: str | None = None,
    ) -> "bytes | Table":
        """
        Returns a slice of the data frame as bytes in the specified format.

        Args:
            offset: From which offset to start the slice (inclusive). If None, starts from 0.
            limit: The number of rows to slice. If None, goes to the end.
            column_names: List of column names to include. If None, includes all columns.
            output_format: Output format - either "json", "parquet", or "table".
            order_by: The column name to order by (use '-' prefix to order by descending order).
        Returns:
            The sliced data as bytes in the specified format.
        """


class DataNodeFromDataReaderSheet(DataNodeResult):
    def __init__(self, platform_data_frame: "PlatformDataFrame", reader_sheet: "DataReaderSheet"):
        self._platform_data_frame = platform_data_frame
        self._reader_sheet = reader_sheet

    async def list_sample_rows(self, num_samples: int) -> "list[Row]":
        return self._reader_sheet.list_sample_rows(num_samples)

    async def num_rows(self) -> int:
        return self._reader_sheet.num_rows

    @property
    def num_columns(self) -> int:
        return self._reader_sheet.num_columns

    @property
    def column_headers(self) -> list[str]:
        return self._reader_sheet.column_headers

    @property
    def columns(self) -> dict[str, str]:
        return self._reader_sheet.columns

    @property
    def platform_data_frame(self) -> "PlatformDataFrame":
        return self._platform_data_frame

    def to_ibis(self) -> "pyarrow.Table":
        return self._reader_sheet.to_ibis()

    async def slice(
        self,
        offset: int = 0,
        limit: int | None = None,
        column_names: list[str] | None = None,
        *,
        output_format: SliceOutputFormat = "json",
        order_by: str | None = None,
    ) -> "bytes | Table":
        table: pyarrow.Table = self._reader_sheet.to_ibis()

        return convert_pyarrow_slice_to_table_json_or_parquet(
            table, offset, limit, column_names, output_format, order_by
        )


class ParquetHandler:
    def __init__(self, parquet_contents: bytes):
        self._parquet_contents = parquet_contents
        self.__loaded_table: Any | None = None

    def _loaded_table(self) -> "Any":
        if self.__loaded_table is None:
            import io

            import pyarrow.parquet

            stream = io.BytesIO(self._parquet_contents)
            self.__loaded_table = pyarrow.parquet.read_table(stream)
        return self.__loaded_table

    def list_sample_rows(self, num_samples: int) -> "list[Row]":
        if num_samples == 0:
            return []
        table = self._loaded_table()

        # Handle num_samples=-1 (fetch all rows) specially - allows unlimited rows for explicit requests
        if num_samples == -1:
            return convert_pyarrow_slice_to_list_of_rows(table, None, None, None, None)

        # Cap num_samples to prevent memory exhaustion
        effective_limit = min(num_samples, MAX_SAMPLE_ROWS)

        # If effective limit still exceeds available rows, just return all rows
        if effective_limit >= table.num_rows:
            return convert_pyarrow_slice_to_list_of_rows(table, None, None, None, None)
        else:
            assert effective_limit > 0, "effective_limit must be > 0"
            return convert_pyarrow_slice_to_list_of_rows(table, 0, effective_limit, None, None)

    def num_rows(self) -> int:
        return self._loaded_table().num_rows

    def num_columns(self) -> int:
        return self._loaded_table().num_columns

    def column_headers(self) -> list[str]:
        return list(self._loaded_table().column_names)

    @property
    def columns(self) -> dict[str, str]:
        table = self._loaded_table()
        return {field.name: str(field.type) for field in table.schema}

    def get_table(self) -> "pyarrow.Table":
        return self._loaded_table()


class DataNodeFromInMemoryDataFrame(DataNodeResult):
    def __init__(self, platform_data_frame: "PlatformDataFrame"):
        self._platform_data_frame = platform_data_frame
        self.__loaded_table: Any | None = None
        if self._platform_data_frame.parquet_contents is None:
            raise ValueError("Parquet contents are required for in-memory data frames")
        self._parquet_contents: bytes = self._platform_data_frame.parquet_contents
        self._parquet_handler = ParquetHandler(self._parquet_contents)

    async def list_sample_rows(self, num_samples: int) -> "list[Row]":
        return self._parquet_handler.list_sample_rows(num_samples)

    async def num_rows(self) -> int:
        return self._parquet_handler.num_rows()

    @property
    def num_columns(self) -> int:
        return self._parquet_handler.num_columns()

    @property
    def column_headers(self) -> list[str]:
        return self._parquet_handler.column_headers()

    @property
    def columns(self) -> dict[str, str]:
        return self._parquet_handler.columns

    @property
    def platform_data_frame(self) -> "PlatformDataFrame":
        return self._platform_data_frame

    def to_ibis(self) -> "pyarrow.Table":
        return self._parquet_handler.get_table()

    async def slice(
        self,
        offset: int = 0,
        limit: int | None = None,
        column_names: list[str] | None = None,
        *,
        output_format: SliceOutputFormat = "json",
        order_by: str | None = None,
    ) -> "bytes | Table":
        table = self._parquet_handler.get_table()

        return convert_pyarrow_slice_to_table_json_or_parquet(
            table, offset, limit, column_names, output_format, order_by
        )


class DataNodeFromIbisResult(DataNodeResult):
    def __init__(
        self,
        platform_data_frame: "PlatformDataFrame",
        ibis_result: "AsyncIbisTable",
        full_sql_query_str: str,
        full_sql_query_logical_str: str,
    ):
        self._platform_data_frame = platform_data_frame
        self._ibis_result: AsyncIbisTable = ibis_result
        self._full_sql_query_str = full_sql_query_str
        self._full_sql_query_logical_str = full_sql_query_logical_str

    @property
    def full_sql_query_str(self) -> str:
        """
        The full SQL query string with the actual table names.
        """
        return self._full_sql_query_str

    @property
    def full_sql_query_logical_str(self) -> str:
        """
        The full SQL query string with the logical table names.
        """
        return self._full_sql_query_logical_str

    async def _to_arrow_safe(self, ibis_table: "AsyncIbisTable") -> "pyarrow.Table":
        """Convert ibis table to Arrow with necessary transformations."""
        from agent_platform.server.kernel.ibis_table_adapter import IbisTableAdapter

        adapter = IbisTableAdapter(ibis_table)
        return await adapter.to_pyarrow()

    async def list_sample_rows(self, num_samples: int) -> "list[Row]":
        if num_samples == 0:
            return []

        # Handle limit=-1 (fetch all rows) specially - allows unlimited rows for explicit requests
        if num_samples == -1:
            table = await self._to_arrow_safe(self._ibis_result)
        else:
            # Cap the num_samples to prevent memory exhaustion
            effective_limit = min(num_samples, MAX_SAMPLE_ROWS)
            table = await self._to_arrow_safe(self._ibis_result.limit(effective_limit))

        # table is pyarrow.Table from _to_arrow_safe
        pylist = table.to_pylist()
        return [list(row) for row in pylist]

    async def num_rows(self) -> int:
        return await self._ibis_result.execute_count()

    @property
    def num_columns(self) -> int:
        return len(self._ibis_result.columns)

    @property
    def column_headers(self) -> list[str]:
        return list(self._ibis_result.columns)

    @property
    def columns(self) -> dict[str, str]:
        return self._ibis_result.columns_with_types

    @property
    def platform_data_frame(self) -> "PlatformDataFrame":
        return self._platform_data_frame

    def to_ibis(self) -> Any:
        return self._ibis_result

    async def slice(
        self,
        offset: int = 0,
        limit: int | None = None,
        column_names: list[str] | None = None,
        *,
        output_format: SliceOutputFormat = "json",
        order_by: str | None = None,
    ) -> "bytes | Table":
        import time

        from sema4ai.actions import Table

        # Start with the ibis result
        logger.info(
            f"Slicing ibis result with offset: {offset}, limit: {limit}, "
            f"column_names: {column_names}, output_format: {output_format}, "
            f"order_by: {order_by}"
        )
        initial_time = time.monotonic()

        result = self._ibis_result
        ret = await _convert_ibis_slice_to_format(result, offset, limit, column_names, output_format, order_by)

        logger.info(f"Sliced ibis result in {time.monotonic() - initial_time:.2f} seconds")

        return typing.cast(bytes | Table, ret)
