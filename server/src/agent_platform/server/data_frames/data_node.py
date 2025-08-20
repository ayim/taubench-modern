import typing
from abc import abstractmethod
from collections.abc import Sequence
from typing import Any, Literal, Protocol

if typing.TYPE_CHECKING:
    import pyarrow

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_reader import DataReaderSheet

SupportedIbisBackends = Literal["duckdb", "any"]


def _find_columns_case_insensitive(
    requested_columns: list[str], available_columns: list[str]
) -> list[str]:
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
            message=(
                f"Columns not found: {missing_columns}. Available columns: {available_columns}"
            ),
        )

    return selected_columns


def _convert_pyarrow_slice_to_format(  # noqa: PLR0913
    result: "pyarrow.Table",
    offset: int | None,
    limit: int | None,
    column_names: list[str] | None,
    output_format: Literal["json", "parquet"],
    order_by: str | None = None,
) -> bytes:
    available_columns = result.schema.names

    # Apply order by
    if order_by:
        order_by, desc = _parse_order_by(order_by, available_columns)
        result = result.sort_by([(order_by, "descending" if desc else "ascending")])

    # Apply column selection
    if column_names is not None:
        selected_columns = _find_columns_case_insensitive(column_names, available_columns)
        result = result.select(selected_columns)

    # Apply row slicing using ibis operations
    if offset is not None or limit is not None:
        if offset is None:
            offset = 0
        if limit is None:
            result = result[offset:]
        else:
            result = result[offset : offset + limit]

    return _convert_arrow_to_format(result, output_format)


def _convert_ibis_slice_to_format(  # noqa: PLR0913
    result: Any,
    offset: int,
    limit: int | None,
    column_names: list[str] | None,
    output_format: Literal["json", "parquet"],
    order_by: str | None = None,
) -> bytes:
    available_columns = list(result.columns)
    if order_by:
        order_by, desc = _parse_order_by(order_by, available_columns)

        op = result[order_by].desc() if desc else result[order_by].asc()
        result = result.order_by(op)

    # Apply column selection (case-insensitive)
    if column_names is not None:
        selected_columns = _find_columns_case_insensitive(column_names, available_columns)
        result = result.select(selected_columns)

    # Apply row slicing using ibis operations
    if offset is not None or limit is not None:
        if limit is None:
            result = result[offset:]
        else:
            result = result[offset : offset + limit]

    # Convert to pyarrow table
    table = result.to_pyarrow()
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
    output_format: Literal["json", "parquet"],
) -> bytes:
    import io
    import json

    import pyarrow.parquet

    # Convert to the requested format
    if output_format == "json":
        # Convert to list of dictionaries and then to JSON
        data = table.to_pylist()
        return json.dumps(data, default=str).encode("utf-8")
    elif output_format == "parquet":
        # Convert to parquet format
        buffer = io.BytesIO()
        pyarrow.parquet.write_table(table, buffer)
        return buffer.getvalue()
    else:
        raise ValueError(f"Unsupported format: {output_format}")


class DataNodeResult(Protocol):
    """
    A protocol for data node results.
    """

    required_backend: SupportedIbisBackends

    @abstractmethod
    def list_sample_rows(self, num_samples: int) -> list[Sequence[Any]]:
        pass

    @property
    @abstractmethod
    def num_rows(self) -> int:
        pass

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
    def platform_data_frame(self) -> "PlatformDataFrame":
        pass

    @abstractmethod
    def to_ibis(self) -> Any:
        """
        Returns something that can be bound to ibis (such
        as a pyarrow table or an ibis sql query).
        """

    @abstractmethod
    def slice(
        self,
        offset: int | None = None,
        limit: int | None = None,
        column_names: list[str] | None = None,
        output_format: Literal["json", "parquet"] = "json",
        order_by: str | None = None,
    ) -> bytes:
        """
        Returns a slice of the data frame as bytes in the specified format.

        Args:
            offset: From which offset to start the slice (inclusive). If None, starts from 0.
            limit: The number of rows to slice. If None, goes to the end.
            column_names: List of column names to include. If None, includes all columns.
            output_format: Output format - either "json" or "parquet".
            order_by: The column name to order by (use '-' prefix to order by descending order).
        Returns:
            The sliced data as bytes in the specified format.
        """


class DataNodeFromDataReaderSheet(DataNodeResult):
    required_backend: SupportedIbisBackends = "duckdb"

    def __init__(self, platform_data_frame: "PlatformDataFrame", reader_sheet: "DataReaderSheet"):
        self._platform_data_frame = platform_data_frame
        self._reader_sheet = reader_sheet

    def list_sample_rows(self, num_samples: int) -> list[Sequence[Any]]:
        return self._reader_sheet.list_sample_rows(num_samples)

    @property
    def num_rows(self) -> int:
        return self._reader_sheet.num_rows

    @property
    def num_columns(self) -> int:
        return self._reader_sheet.num_columns

    @property
    def column_headers(self) -> list[str]:
        return self._reader_sheet.column_headers

    @property
    def platform_data_frame(self) -> "PlatformDataFrame":
        return self._platform_data_frame

    def to_ibis(self) -> Any:
        return self._reader_sheet.to_ibis()

    def slice(
        self,
        offset: int | None = None,
        limit: int | None = None,
        column_names: list[str] | None = None,
        output_format: Literal["json", "parquet"] = "json",
        order_by: str | None = None,
    ) -> bytes:
        table: pyarrow.Table = self._reader_sheet.to_ibis()

        return _convert_pyarrow_slice_to_format(
            table, offset, limit, column_names, output_format, order_by
        )


class DataNodeFromInMemoryDataFrame(DataNodeResult):
    required_backend: SupportedIbisBackends = "duckdb"

    def __init__(self, platform_data_frame: "PlatformDataFrame"):
        self._platform_data_frame = platform_data_frame
        self.__loaded_table: "Any | None" = None  # noqa: UP037
        if self._platform_data_frame.parquet_contents is None:
            raise ValueError("Parquet contents are required for in-memory data frames")
        self._parquet_contents: bytes = self._platform_data_frame.parquet_contents

    def _loaded_table(self) -> "Any":
        if self.__loaded_table is None:
            import io

            import pyarrow.parquet

            stream = io.BytesIO(self._parquet_contents)
            self.__loaded_table = pyarrow.parquet.read_table(stream)
        return self.__loaded_table

    def list_sample_rows(self, num_samples: int) -> list[Sequence[Any]]:
        table = self._loaded_table()
        # Get sample rows using pyarrow
        if num_samples >= table.num_rows:
            # Return all rows
            return [tuple(row) for row in table.to_pylist()]
        else:
            return [tuple(row) for row in table.slice(0, num_samples).to_pylist()]

    @property
    def num_rows(self) -> int:
        return self._loaded_table().num_rows

    @property
    def num_columns(self) -> int:
        return self._loaded_table().num_columns

    @property
    def column_headers(self) -> list[str]:
        return list(self._loaded_table().column_names)

    @property
    def platform_data_frame(self) -> "PlatformDataFrame":
        return self._platform_data_frame

    def to_ibis(self) -> Any:
        return self._loaded_table()

    def slice(
        self,
        offset: int | None = None,
        limit: int | None = None,
        column_names: list[str] | None = None,
        output_format: Literal["json", "parquet"] = "json",
    ) -> bytes:
        table = self._loaded_table()

        return _convert_pyarrow_slice_to_format(table, offset, limit, column_names, output_format)


class DataNodeFromIbisResult(DataNodeResult):
    required_backend: SupportedIbisBackends = "any"

    def __init__(self, platform_data_frame: "PlatformDataFrame", ibis_result: Any):
        self._platform_data_frame = platform_data_frame
        self._ibis_result = ibis_result

    def list_sample_rows(self, num_samples: int) -> list[Sequence[Any]]:
        table = self._ibis_result.sample(num_samples).to_pyarrow()
        return [tuple(row) for row in table.to_pylist()]

    @property
    def num_rows(self) -> int:
        return self._ibis_result.count().to_pyarrow().as_py()

    @property
    def num_columns(self) -> int:
        return len(self._ibis_result.columns)

    @property
    def column_headers(self) -> list[str]:
        return list(self._ibis_result.columns)

    @property
    def platform_data_frame(self) -> "PlatformDataFrame":
        return self._platform_data_frame

    def to_ibis(self) -> Any:
        return self._ibis_result

    def slice(
        self,
        offset: int = 0,
        limit: int | None = None,
        column_names: list[str] | None = None,
        *,
        order_by: str | None = None,
        output_format: Literal["json", "parquet"] = "json",
    ) -> bytes:
        # Start with the ibis result
        result = self._ibis_result
        return _convert_ibis_slice_to_format(
            result, offset, limit, column_names, output_format, order_by
        )
