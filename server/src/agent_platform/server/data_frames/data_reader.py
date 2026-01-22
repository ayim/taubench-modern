import typing
from abc import abstractmethod
from collections.abc import Iterator

from structlog.stdlib import get_logger

from agent_platform.core.files.mime_types import TABULAR_DATA_MIME_TYPES

if typing.TYPE_CHECKING:
    import fastexcel
    import pyarrow
    from sema4ai.actions import Row

    from agent_platform.core.files import UploadedFile
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)


class DataReaderSheet:
    @property
    @abstractmethod
    def name(self) -> str | None:
        """
        The name of the sheet (or None if not applicable -- a sheet name is only
        applicable to excel files, not csv files).
        """

    @property
    @abstractmethod
    def num_rows(self) -> int:
        """
        The number of rows in the sheet.
        """

    @property
    @abstractmethod
    def num_columns(self) -> int:
        """
        The number of columns in the sheet.
        """

    @property
    @abstractmethod
    def column_headers(self) -> list[str]:
        """
        The headers of the columns in the sheet.
        """

    @property
    @abstractmethod
    def columns(self) -> dict[str, str]:
        """
        Column name -> type mapping.
        """

    @abstractmethod
    def list_sample_rows(self, num_samples: int) -> "list[Row]":
        """
        A list of sample rows from the sheet.
        """

    @abstractmethod
    def to_ibis(self) -> "pyarrow.Table":
        """
        The full sheet as required by ibis.
        """


class FileDataReader:
    """
    A protocol for data readers.
    """

    @abstractmethod
    def has_multiple_sheets(self) -> bool:
        pass

    @abstractmethod
    def iter_sheets(self) -> Iterator[DataReaderSheet]:
        pass


class ExcelDataReader(FileDataReader):
    # Note: may have to fall back to read as csv if reading as excel fails.
    def __init__(self, file_bytes: bytes, sheet_name: str | None = None):
        self._file_bytes = file_bytes
        self._sheet_name = sheet_name
        self.__excel_reader: fastexcel.ExcelReader | None = None
        self._failed_reading_as_excel = False

    @property
    def _excel_reader(self) -> "fastexcel.ExcelReader":
        if self.__excel_reader is None:
            if self._failed_reading_as_excel:
                raise ValueError("Failed to read file as excel (in previous attempt)")

            import fastexcel

            try:
                self.__excel_reader = fastexcel.read_excel(self._file_bytes)
            except Exception as e:
                self._failed_reading_as_excel = True
                logger.error(
                    "Failed to read Excel file with fastexcel",
                    error=str(e),
                    error_type=type(e).__name__,
                    file_size=len(self._file_bytes),
                )
                raise
        return self.__excel_reader

    def has_multiple_sheets(self) -> bool:
        if self._sheet_name is not None:
            return False  # Sheet name specified (we only have 1 sheet)

        try:
            sheet_names = self._excel_reader.sheet_names
        except Exception:
            # If we haven't been able to read with excel, we'll assume it's a csv file
            # (in which case the csv reader will be used). We'll also set a flag so that
            # we don't try to read it as excel again.
            return False

        return len(sheet_names) > 1

    def iter_sheets(self) -> Iterator[DataReaderSheet]:
        try:
            excel_reader = self._excel_reader
        except Exception as e:
            logger.warning(
                "Failed to read file as Excel, falling back to CSV",
                error=str(e),
                error_type=type(e).__name__,
            )
            yield from CsvDataReader(self._file_bytes).iter_sheets()
            return

        sheet_names = excel_reader.sheet_names
        if self._sheet_name is not None:
            if self._sheet_name not in sheet_names:
                raise ValueError(f"Sheet {self._sheet_name} not found in file")
            sheet_names = [self._sheet_name]

        for sheet_name in sheet_names:
            yield ExcelDataReaderSheet(excel_reader, sheet_name)


class ExcelDataReaderSheet(DataReaderSheet):
    def __init__(self, excel_reader: "fastexcel.ExcelReader", sheet_name: str):
        self._excel_reader = excel_reader
        self._sheet_name = sheet_name
        self.__loaded_sheet: fastexcel.ExcelSheet | None = None

    @property
    def name(self) -> str:
        return self._sheet_name

    def _loaded_sheet(self) -> "fastexcel.ExcelSheet":
        if self.__loaded_sheet is None:
            self.__loaded_sheet = self._excel_reader.load_sheet(self._sheet_name)
        return self.__loaded_sheet

    @property
    def num_rows(self) -> int:
        return self._loaded_sheet().height

    @property
    def num_columns(self) -> int:
        return len(self.column_headers)

    @property
    def column_headers(self) -> list[str]:
        if self.__loaded_sheet is None:
            return [c.name for c in self._excel_reader.load_sheet(self._sheet_name, n_rows=0).available_columns()]
        return [c.name for c in self._loaded_sheet().available_columns()]

    @property
    def columns(self) -> dict[str, str]:
        table = self.to_ibis()
        return {field.name: str(field.type) for field in table.schema}

    def list_sample_rows(self, num_samples: int) -> "list[Row]":
        from agent_platform.server.data_frames.data_node import MAX_SAMPLE_ROWS

        # Cap num_samples to prevent memory exhaustion (except for -1 which means all rows)
        if num_samples != -1 and num_samples > MAX_SAMPLE_ROWS:
            logger.info(
                "sample rows capped to maximum",
                requested_num_samples=num_samples,
                max_sample_rows=MAX_SAMPLE_ROWS,
            )
            effective_limit = MAX_SAMPLE_ROWS
        else:
            effective_limit = num_samples

        if self.__loaded_sheet is None:
            loaded_sheet = self._excel_reader.load_sheet(self._sheet_name, n_rows=effective_limit)
            return self._load_samples(loaded_sheet.to_arrow())

        loaded_sheet = self._loaded_sheet()
        table = loaded_sheet.to_arrow()
        if effective_limit != -1 and effective_limit < table.num_rows:
            table = table[:effective_limit]
        return self._load_samples(table)

    def _load_samples(self, batch) -> "list[Row]":
        from agent_platform.server.data_frames.data_node import convert_to_valid_json_types

        return typing.cast(
            "list[Row]",
            [
                convert_to_valid_json_types(list(row))
                for row in zip(*[col.to_pylist() for col in batch.columns], strict=True)
            ],
        )

    def to_ibis(self) -> "pyarrow.Table":
        arrow_table = self._loaded_sheet().to_arrow()
        return _convert_null_data_types_to_string(arrow_table)


class CsvDataReaderSheet(DataReaderSheet):
    def __init__(self, file_bytes: bytes):
        self._file_bytes = file_bytes

    @property
    def name(self) -> str | None:
        return None  # a csv sheet never has a name.

    @property
    def num_rows(self) -> int:
        import io

        import pyarrow.csv

        row_count = 0
        for batch in pyarrow.csv.open_csv(
            io.BytesIO(self._file_bytes),
            pyarrow.csv.ReadOptions(),
        ):
            row_count += batch.num_rows
        return row_count

    @property
    def num_columns(self) -> int:
        return len(self.column_headers)

    @property
    def column_headers(self) -> list[str]:
        import io

        import pyarrow.csv

        reader = pyarrow.csv.open_csv(
            io.BytesIO(self._file_bytes),
            pyarrow.csv.ReadOptions(),
        )
        return list(reader.schema.names)

    @property
    def columns(self) -> dict[str, str]:
        table = self.to_ibis()
        return {field.name: str(field.type) for field in table.schema}

    def list_sample_rows(self, num_samples: int) -> "list[Row]":
        import io

        import pyarrow.csv

        from agent_platform.server.data_frames.data_node import MAX_SAMPLE_ROWS, convert_to_valid_json_types

        if num_samples == 0:
            return []

        # Cap num_samples to prevent memory exhaustion (except for -1 which means all rows)
        if num_samples != -1 and num_samples > MAX_SAMPLE_ROWS:
            logger.info(
                "sample rows capped to maximum",
                requested_num_samples=num_samples,
                max_sample_rows=MAX_SAMPLE_ROWS,
            )
            effective_limit = MAX_SAMPLE_ROWS
        else:
            effective_limit = num_samples

        table = pyarrow.csv.read_csv(
            io.BytesIO(self._file_bytes),
            pyarrow.csv.ReadOptions(),
        )
        if effective_limit != -1 and effective_limit < table.num_rows:
            table = table[:effective_limit]

        return typing.cast(
            "list[Row]",
            [
                convert_to_valid_json_types(list(row))
                for row in zip(*[col.to_pylist() for col in table.columns], strict=True)
            ],
        )

    def to_ibis(self) -> "pyarrow.Table":
        import io

        import pyarrow.csv

        csv_table = pyarrow.csv.read_csv(
            io.BytesIO(self._file_bytes),
        )

        csv_table = _convert_null_data_types_to_string(csv_table)

        return csv_table


def _convert_null_data_types_to_string(table: "pyarrow.Table") -> "pyarrow.Table":
    """
    Convert null column data types to string.

    This is needed because duckdb doesn't support null column types (it does accept
    having null values in the column if the column is of a different type though).
    """
    import pyarrow

    null_data_type: pyarrow.DataType = pyarrow.null()

    new_schema_values = []
    has_null_data_type = False
    for f in table.schema:
        if null_data_type == f.type:
            has_null_data_type = True
            f = f.with_type(pyarrow.string())  # noqa: PLW2901
        new_schema_values.append(f)

    if has_null_data_type:
        table = table.cast(pyarrow.schema(new_schema_values))
    return table


class CsvDataReader(FileDataReader):
    def __init__(self, file_bytes: bytes):
        self._file_bytes = file_bytes

    def has_multiple_sheets(self) -> bool:
        return False

    def iter_sheets(self) -> Iterator[DataReaderSheet]:
        yield CsvDataReaderSheet(self._file_bytes)


async def get_file_metadata(
    user_id: str,
    thread_id: str,
    storage: "BaseStorage",
    *,
    file_id: str | None = None,
    file_ref: str | None = None,
) -> "UploadedFile":
    """Get a file metadata from the storage."""
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    ret: UploadedFile | None = None
    if file_id:
        ret = await storage.get_file_by_id(file_id, user_id)
        if ret is None:
            raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message=f"File with id {file_id} not found")
        return ret
    elif file_ref:
        thread = await storage.get_thread(user_id, thread_id)
        ret = await storage.get_file_by_ref(thread, file_ref, user_id)
        if ret is None:
            raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message=f"File with ref {file_ref} not found")
        return ret
    else:
        raise PlatformHTTPError(
            error_code=ErrorCode.PRECONDITION_FAILED,
            message="Either file_id or file_ref must be provided",
        )


async def _get_file_contents(
    user_id: str, thread_id: str, storage: "BaseStorage", file_metadata: "UploadedFile"
) -> bytes:
    """Get a file from the storage."""
    from agent_platform.server.file_manager.base import BaseFileManager
    from agent_platform.server.file_manager.option import FileManagerService

    file_manager: BaseFileManager = FileManagerService.get_instance(storage)

    # Note: we previously checked if `file_metadata.thread_id != thread_id`
    # and raised an error, but stopped doing that because for work items
    # the owner is not the thread but the work item (thus this check would
    # have been wrong in this case).

    # Get the file from the storage
    file_contents = await file_manager.read_file_contents(file_metadata.file_id, user_id)

    # Return the file contents
    return file_contents


def create_file_data_reader_from_contents(
    file_contents: bytes,
    file_name: str,
    mime_type: str,
    sheet_name: str | None = None,
) -> "FileDataReader":
    """Create a FileDataReader from file contents directly.

    Args:
        file_contents: The raw file contents as bytes
        file_name: The name of the file
        mime_type: The MIME type of the file
        sheet_name: Optional sheet name for Excel files

    Returns:
        A FileDataReader instance
    """
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    # Make sure it's an appropriate file type (excel or csv)
    data_reader: FileDataReader
    try:
        if mime_type in ("text/csv", "text/tab-separated-values"):
            data_reader = CsvDataReader(file_contents)
        else:
            data_reader = ExcelDataReader(file_contents, sheet_name=sheet_name)
    except Exception as e:
        if mime_type not in TABULAR_DATA_MIME_TYPES:
            message = f"File {file_name} is not a valid table file (unexpected mime type: {mime_type!r})"
        else:
            message = f"Unable to read file {file_name} as a data frame (found mime type {mime_type!r})"

            logger.exception(message)
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=message,
        ) from e

    return data_reader


async def create_file_data_reader(
    user: "AuthedUser",
    tid: str,
    storage: "BaseStorage",
    sheet_name: str | None = None,
    *,
    file_metadata: "UploadedFile",
) -> "FileDataReader":
    from agent_platform.server.storage.base import BaseStorage

    # Get the file from the storage
    file_bytes = await _get_file_contents(
        user.user_id, tid, typing.cast(BaseStorage, storage), file_metadata=file_metadata
    )

    # Use the new function to create the data reader
    return create_file_data_reader_from_contents(
        file_bytes,
        file_metadata.file_ref,
        file_metadata.mime_type,
        sheet_name=sheet_name,
    )
