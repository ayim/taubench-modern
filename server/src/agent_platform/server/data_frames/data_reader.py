import typing
from abc import abstractmethod
from collections.abc import Iterator, Sequence
from typing import Any

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    import fastexcel

    from agent_platform.core.files import UploadedFile
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)
_excel_mime_types = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
]

_all_mime_types = [  # noqa: RUF005
    "text/csv",
    "text/tab-separated-values",
] + _excel_mime_types


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

    @abstractmethod
    def list_sample_rows(self, num_samples: int) -> list[Sequence[Any]]:
        """
        A list of sample rows from the sheet.
        """

    @abstractmethod
    def to_ibis(self) -> Any:
        """
        The full sheet as required by ibis.
        """


class FileDataReader:
    """
    A protocol for data readers.
    """

    @property
    @abstractmethod
    def file_metadata(self) -> "UploadedFile":
        """
        The metadata of the file.
        """

    @abstractmethod
    def has_multiple_sheets(self) -> bool:
        pass

    @abstractmethod
    def iter_sheets(self) -> Iterator[DataReaderSheet]:
        pass


class ExcelDataReader(FileDataReader):
    # Note: may have to fall back to read as csv if reading as excel fails.
    def __init__(
        self, file_metadata: "UploadedFile", file_bytes: bytes, sheet_name: str | None = None
    ):
        self._file_metadata = file_metadata
        self._file_bytes = file_bytes
        self._sheet_name = sheet_name
        self.__excel_reader: fastexcel.ExcelReader | None = None
        self._failed_reading_as_excel = False

    @property
    def file_metadata(self) -> "UploadedFile":
        return self._file_metadata

    @property
    def _excel_reader(self) -> "fastexcel.ExcelReader":
        if self.__excel_reader is None:
            if self._failed_reading_as_excel:
                raise ValueError("Failed to read file as excel (in previous attempt)")

            import fastexcel

            try:
                self.__excel_reader = fastexcel.read_excel(self._file_bytes)
            except Exception:
                self._failed_reading_as_excel = True
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
        except Exception:
            yield from CsvDataReader(self._file_metadata, self._file_bytes).iter_sheets()
            return

        sheet_names = excel_reader.sheet_names
        if self._sheet_name is not None:
            if self._sheet_name not in sheet_names:
                raise ValueError(f"Sheet {self._sheet_name} not found in file")
            sheet_names = [self._sheet_name]

        for sheet_name in sheet_names:
            yield ExcelDataReaderSheet(self._file_metadata, excel_reader, sheet_name)


class ExcelDataReaderSheet(DataReaderSheet):
    def __init__(
        self, file_metadata: "UploadedFile", excel_reader: "fastexcel.ExcelReader", sheet_name: str
    ):
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
            return [
                c.name
                for c in self._excel_reader.load_sheet(
                    self._sheet_name, n_rows=0
                ).available_columns()
            ]
        return [c.name for c in self._loaded_sheet().available_columns()]

    def list_sample_rows(self, num_samples: int) -> list[Sequence[Any]]:
        if self.__loaded_sheet is None:
            loaded_sheet = self._excel_reader.load_sheet(self._sheet_name, n_rows=num_samples)
            return self._load_samples(loaded_sheet.to_arrow())

        loaded_sheet = self._loaded_sheet()
        return self._load_samples(loaded_sheet.to_arrow()[:num_samples])

    def _load_samples(self, batch) -> list[Sequence[Any]]:
        return list(zip(*[col.to_pylist() for col in batch.columns], strict=True))

    def to_ibis(self) -> Any:
        return self._loaded_sheet().to_arrow()


class CsvDataReaderSheet(DataReaderSheet):
    def __init__(self, file_metadata: "UploadedFile", file_bytes: bytes):
        self._file_metadata = file_metadata
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

    def list_sample_rows(self, num_samples: int) -> list[Sequence[Any]]:
        import io

        import pyarrow.csv

        table = pyarrow.csv.read_csv(
            io.BytesIO(self._file_bytes),
            pyarrow.csv.ReadOptions(),
        )[:num_samples]
        return list(zip(*[col.to_pylist() for col in table.columns], strict=True))

    def to_ibis(self) -> Any:
        import io

        import pyarrow.csv

        return pyarrow.csv.read_csv(
            io.BytesIO(self._file_bytes),
        )


class CsvDataReader(FileDataReader):
    def __init__(self, file_metadata: "UploadedFile", file_bytes: bytes):
        self._file_metadata = file_metadata
        self._file_bytes = file_bytes

    @property
    def file_metadata(self) -> "UploadedFile":
        return self._file_metadata

    def has_multiple_sheets(self) -> bool:
        return False

    def iter_sheets(self) -> Iterator[DataReaderSheet]:
        yield CsvDataReaderSheet(self._file_metadata, self._file_bytes)


async def _get_file(
    user_id: str,
    thread_id: str,
    storage: "BaseStorage",
    *,
    file_id: str | None = None,
    file_ref: str | None = None,
) -> "tuple[UploadedFile, bytes]":
    """Get a file from the storage."""
    from agent_platform.server.file_manager.base import BaseFileManager
    from agent_platform.server.file_manager.option import FileManagerService

    file_manager: BaseFileManager = FileManagerService.get_instance(storage)

    from agent_platform.core.errors.base import PlatformError

    # Get the file metadata
    file_metadata: UploadedFile | None = None
    if file_id:
        file_metadata = await storage.get_file_by_id(file_id, user_id)
    elif file_ref:
        # To get by ref we need the actual thread object...
        thread = await storage.get_thread(user_id, thread_id)
        file_metadata = await storage.get_file_by_ref(thread, file_ref, user_id)
    else:
        raise PlatformError(
            message="Either file_id or file_ref must be provided",
        )

    # If we have no metadata, raise
    if file_metadata is None:
        raise PlatformError(
            message=f"File with id {file_id} not found",
        )

    # Check if the file is in the thread
    if file_metadata.thread_id != thread_id:
        raise PlatformError(
            message=f"File with id {file_id} is not in thread {thread_id}",
        )

    # Get the file from the storage
    file_contents = await file_manager.read_file_contents(file_metadata.file_id, user_id)

    # Return the file contents
    return file_metadata, file_contents


async def create_file_data_reader(  # noqa: PLR0913
    user: "AuthedUser",
    tid: str,
    storage: "BaseStorage",
    sheet_name: str | None = None,
    *,
    file_id: str | None = None,
    file_ref: str | None = None,
) -> "FileDataReader":
    from agent_platform.core.errors.base import PlatformError
    from agent_platform.server.storage.base import BaseStorage

    # Get the file from the storage
    file_metadata, file_bytes = await _get_file(
        user.user_id, tid, typing.cast(BaseStorage, storage), file_id=file_id, file_ref=file_ref
    )

    # Make sure it's an appropriate file type (excel or csv)
    data_reader: FileDataReader
    try:
        if file_metadata.mime_type in ("text/csv", "text/tab-separated-values"):
            data_reader = CsvDataReader(file_metadata, file_bytes)
        else:
            data_reader = ExcelDataReader(file_metadata, file_bytes, sheet_name=sheet_name)
    except Exception as e:
        if file_metadata.mime_type not in _all_mime_types:
            message = (
                f"File {file_id} is not a valid table file (unexpected mime type: "
                f"{file_metadata.mime_type!r})"
            )
        else:
            message = (
                f"Unable to read file {file_id} as a data frame "
                f"(found mime type {file_metadata.mime_type!r})"
            )

        logger.error(message, error=e)
        raise PlatformError(message=message) from e

    return data_reader
