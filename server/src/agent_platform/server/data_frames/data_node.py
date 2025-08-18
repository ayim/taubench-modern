import typing
from abc import abstractmethod
from collections.abc import Sequence
from typing import Any, Literal, Protocol

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_reader import DataReaderSheet

SupportedIbisBackends = Literal["duckdb", "any"]


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
