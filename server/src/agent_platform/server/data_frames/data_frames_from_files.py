import dataclasses
import typing

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    import polars

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


async def _get_file(
    user_id: str, file_id: str, thread_id: str, storage: "BaseStorage"
) -> "tuple[UploadedFile, bytes]":
    """Get a file from the storage."""
    from agent_platform.server.file_manager.base import BaseFileManager
    from agent_platform.server.file_manager.option import FileManagerService

    file_manager: BaseFileManager = FileManagerService.get_instance(storage)

    from agent_platform.core.errors.base import PlatformError

    # Get the file metadata
    file_metadata = await storage.get_file_by_id(file_id, user_id)

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
    file_contents = await file_manager.read_file_contents(file_id, user_id)

    # Return the file contents
    return file_metadata, file_contents


@dataclasses.dataclass
class DataFrameLoadResult:
    df: "polars.DataFrame | dict[str, polars.DataFrame]"
    file_metadata: "UploadedFile"


async def load_data_frame_from_file(  # noqa: PLR0913
    user: "AuthedUser",
    file_id: str,
    tid: str,
    storage: "BaseStorage",
    sheet_name: str | None = None,
    sheet_id: int | None = None,
) -> "DataFrameLoadResult":
    import polars

    from agent_platform.core.errors.base import PlatformError
    from agent_platform.server.storage.base import BaseStorage

    # Get the file from the storage
    file_metadata, file_bytes = await _get_file(
        user.user_id, file_id, tid, typing.cast(BaseStorage, storage)
    )

    # Make sure it's an appropriate file type (excel or csv)

    # DataFrame
    #     If reading a single sheet.
    # dict
    #     If reading multiple sheets, a "{sheetname: DataFrame, ...}" dict is returned.
    df: polars.DataFrame | dict[str, polars.DataFrame]

    # Make sure it's an appropriate file type (excel or csv)
    try:
        if file_metadata.mime_type == "text/csv":
            df = polars.read_csv(file_bytes, infer_schema_length=2000)
        elif file_metadata.mime_type == "text/tab-separated-values":
            df = polars.read_csv(file_bytes, separator="\t")
        else:
            if False:
                # This import is here just for pyinstaller to include it in the binary.
                import fastexcel  # noqa: F401

            # Either excel type or something else (try to parse with excel first, then csv)
            try:
                sheet_filters = {}
                if sheet_name is not None:
                    sheet_filters["sheet_name"] = sheet_name
                elif sheet_id is not None:
                    sheet_filters["sheet_id"] = sheet_id
                else:
                    # i.e.: all sheets
                    sheet_filters["sheet_id"] = 0

                df = polars.read_excel(file_bytes, **sheet_filters)
            except Exception:
                # In Windows it's possible that a file is detected as excel when it's
                # actually a csv, so, always fall back to reading it as a csv (as
                # polars.read_excel will fail).
                df = polars.read_csv(file_bytes, infer_schema_length=2000)
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

    return DataFrameLoadResult(df, file_metadata)
