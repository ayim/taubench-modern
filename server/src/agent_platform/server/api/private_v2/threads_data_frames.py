import dataclasses
import datetime
import typing
from collections.abc import Sequence
from typing import Annotated, Any, Literal

from fastapi import HTTPException, Response
from fastapi.routing import APIRouter
from pydantic.main import BaseModel
from structlog.stdlib import get_logger

from agent_platform.server.api.dependencies import (
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


@dataclasses.dataclass
class _DataFrameInspectionAPI:
    thread_id: Annotated[str, "The ID of the thread that the data frame is in."]
    name: Annotated[str, "The name of the data frame."]
    sheet_name: Annotated[
        str | None,
        "The name of the sheet that the data frame is in (None if not applicable, i.e.: "
        "if the data frame is a .csv, not excel).",
    ]
    num_rows: Annotated[int, "The number of rows in the data frame."]
    num_columns: Annotated[int, "The number of columns in the data frame."]
    created_at: Annotated[datetime.datetime, "The date and time the data frame was created."]
    column_headers: Annotated[list[str], "The headers of the columns in the data frame."]
    sample_rows: Annotated[list[Sequence[Any]], "The sample rows of the data frame."]


@router.get("/{tid}/inspect-file-as-data-frame")
async def inspect_file_as_data_frame(  # noqa: PLR0913
    user: AuthedUser,
    tid: str,
    file_id: str,
    storage: StorageDependency,
    num_samples: Annotated[
        int,
        """The number of samples to return for each data frame.

        If 0, no samples are returned.
        If -1, all samples are returned.
        If a positive number, return up to that number of samples.
        """,
    ] = 0,
    sheet_name: Annotated[
        str | None,
        """The name of the sheet to inspect. If not given and a multi-sheet
        file is given, all sheets are inspected.""",
    ] = None,
) -> list[_DataFrameInspectionAPI]:
    """Inspect a file as a data frame.

    Note: may return multiple data frames if the file is a multi-sheet excel file."""

    from agent_platform.server.data_frames.data_reader import (
        create_file_data_reader,
    )

    ret: list[_DataFrameInspectionAPI] = []

    data_reader = await create_file_data_reader(user, file_id, tid, storage, sheet_name)
    file_metadata = data_reader.file_metadata

    for sheet in data_reader.iter_sheets():
        ret.append(
            _DataFrameInspectionAPI(
                thread_id=tid,
                name=file_metadata.file_ref,
                sheet_name=sheet.name,
                num_rows=sheet.num_rows,
                num_columns=sheet.num_columns,
                created_at=datetime.datetime.now(),
                column_headers=sheet.column_headers,
                sample_rows=sheet.list_sample_rows(num_samples),
            )
        )

    return ret


@dataclasses.dataclass
class _DataFrameCreationAPI:
    data_frame_id: str
    thread_id: str
    name: str
    sheet_name: str | None
    description: str | None
    num_rows: int
    num_columns: int
    created_at: datetime.datetime
    column_headers: list[str]
    sample_rows: list[Sequence[Any]]


@router.post("/{tid}/data-frames/from-file")
async def create_data_frame_from_file(  # noqa: PLR0913
    user: AuthedUser,
    tid: str,
    file_id: str,
    storage: StorageDependency,
    num_samples: Annotated[
        int,
        """The number of samples to return for each data frame.

        If 0, no samples are returned.
        If -1, all samples are returned.
        If a positive number, return up to that number of samples.
        """,
    ] = 0,
    sheet_name: Annotated[
        str | None,
        """The name of the sheet to inspect. If not given and a multi-sheet
        file is given, an error is raised.""",
    ] = None,
    description: Annotated[str | None, "The description for the data frame."] = None,
    name: Annotated[str | None, "The name for the data frame."] = None,
) -> _DataFrameCreationAPI:
    """Create a data frame from a file.

    Note: if the file is a multi-sheet excel file, this needs to be called for each sheet
    by specifying the sheet_name.
    """
    import keyword
    import os.path
    import uuid

    from agent_platform.core.errors.base import PlatformError
    from sema4ai.common.text import slugify

    inspected_data_frames = await inspect_file_as_data_frame(
        user, tid, file_id, storage, num_samples, sheet_name
    )
    if len(inspected_data_frames) == 0:
        raise HTTPException(status_code=400, detail="No data frames found in file")

    if len(inspected_data_frames) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple data frames found in file. Please specify sheet_name.",
        )

    inspected_data_frame = inspected_data_frames[0]

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)

    # Get the thread to find the agent_id
    thread = await base_storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    use_name = name
    if not use_name:
        # Try to generate a name from the file name / sheet name.
        ref = os.path.basename(inspected_data_frame.name)
        ref = os.path.splitext(ref)[0]

        use_name = slugify(ref).replace("-", "_")
        if sheet_name:
            sheet_name_as_slug = slugify(sheet_name).replace("-", "_")
            use_name = f"{use_name}_{sheet_name_as_slug}"

        if not use_name.isidentifier() or keyword.iskeyword(use_name):
            use_name = f"data_{use_name}"  # first char may be digit or it's a keyword.

        if not use_name.isidentifier() or keyword.iskeyword(use_name):
            # Still not valid, let's raise an error.
            raise PlatformError(
                message=(
                    "It was not possible to generate a valid name for the data frame. "
                    f"Please provide one as a parameter to the request (auto-generated name: "
                    f"{use_name!r})."
                )
            )

    data_frame = PlatformDataFrame(
        data_frame_id=str(uuid.uuid4()),
        user_id=user.user_id,
        agent_id=thread.agent_id,
        thread_id=tid,
        sheet_name=inspected_data_frame.sheet_name,
        num_rows=inspected_data_frame.num_rows,
        num_columns=inspected_data_frame.num_columns,
        column_headers=inspected_data_frame.column_headers,
        name=use_name,
        input_id_type="file",
        created_at=datetime.datetime.now(datetime.UTC),
        computation_input_sources={},
        file_id=file_id,
        description=description,
        computation=None,
        # we could save the data as parquet, but for now, let's experiment in always
        # rebuilding the full data whenever asked.
        parquet_contents=None,
    )

    await base_storage.save_data_frame(data_frame)

    return _DataFrameCreationAPI(
        data_frame_id=data_frame.data_frame_id,
        thread_id=data_frame.thread_id,
        name=data_frame.name,
        sheet_name=sheet_name,
        description=data_frame.description,
        num_rows=data_frame.num_rows,
        num_columns=data_frame.num_columns,
        created_at=data_frame.created_at,
        column_headers=data_frame.column_headers,
        sample_rows=inspected_data_frame.sample_rows,
    )


@router.get("/{tid}/data-frames")
async def get_thread_data_frames(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    num_samples: int = 0,
) -> list[_DataFrameCreationAPI]:
    """Get a list of data frames for a thread.

    Args:
        user: The user making the request.
        tid: The ID of the thread to get data frames for.
        storage: The storage to use to get the data frames.
        num_samples: The number of samples to return for each data frame.
            If 0, no samples are returned.
            If -1, all samples are returned.
            If a positive number, return up to that number of samples.

    Returns:
        A list of data frames created in the thread.
    """
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)

    data_frames: list[PlatformDataFrame] = await base_storage.list_data_frames(tid)
    ret: list[_DataFrameCreationAPI] = []
    for data_frame in data_frames:
        data_frame_api = _DataFrameCreationAPI(
            data_frame_id=data_frame.data_frame_id,
            thread_id=data_frame.thread_id,
            name=data_frame.name,
            sheet_name=data_frame.sheet_name,
            description=data_frame.description,
            num_rows=data_frame.num_rows,
            num_columns=data_frame.num_columns,
            created_at=data_frame.created_at,
            column_headers=data_frame.column_headers,
            sample_rows=[],  # It'll be loaded later if needed
        )

        if num_samples != 0:
            data_frames_kernel = DataFramesKernel(base_storage, user, tid)
            resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)
            data_frame_api.sample_rows = resolved_df.list_sample_rows(num_samples)
        ret.append(data_frame_api)
    return ret


@dataclasses.dataclass
class _DataFrameComputationPayload:
    new_data_frame_name: Annotated[str, "The name for the new data frame."]
    sql_query: Annotated[str, "The SQL query to execute."]
    description: Annotated[str | None, "Optional description for the new data frame."] = None
    sql_dialect: Annotated[str, "The dialect of the SQL query to use (default is 'duckdb')."] = (
        "duckdb"
    )


@router.post("/{tid}/data-frames/from-computation")
async def create_data_frame_from_sql_computation(
    payload: _DataFrameComputationPayload,
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    num_samples: Annotated[
        int,
        """The number of samples to return for each data frame.

        If 0, no samples are returned.
        If -1, all samples are returned.
        If a positive number, return up to that number of samples.
        """,
    ] = 0,
) -> _DataFrameCreationAPI:
    """Create a new data frame from existing data frames using a SQL computation.

    Args:
        payload: The computation payload containing name, SQL query, and input data frames
        user: The user making the request
        tid: The ID of the thread
        storage: The storage to use

    Returns:
        The created data frame information
    """
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    base_storage = typing.cast(BaseStorage, storage)

    data_frames_kernel = DataFramesKernel(base_storage, user, tid)

    resolved_df = await create_data_frame_from_sql_computation(
        data_frames_kernel=data_frames_kernel,
        storage=base_storage,
        new_data_frame_name=payload.new_data_frame_name,
        sql_query=payload.sql_query,
        dialect=payload.sql_dialect,
        description=payload.description,
    )

    platform_data_frame = resolved_df.platform_data_frame

    return _DataFrameCreationAPI(
        data_frame_id=platform_data_frame.data_frame_id,
        thread_id=platform_data_frame.thread_id,
        name=platform_data_frame.name,
        sheet_name=platform_data_frame.sheet_name,
        description=platform_data_frame.description,
        num_rows=platform_data_frame.num_rows,
        num_columns=platform_data_frame.num_columns,
        created_at=platform_data_frame.created_at,
        column_headers=platform_data_frame.column_headers,
        sample_rows=resolved_df.list_sample_rows(num_samples),
    )


class _SliceDataInput(BaseModel):
    data_frame_id: Annotated[str, "The ID of the data frame to slice."]
    data_frame_name: Annotated[str | None, "The name of the data frame to slice."] = None
    offset: Annotated[int, "From which offset to start the slice (starts at 0)."] = 0
    limit: Annotated[int | None, "The maximum number of rows to return in the slice."] = None
    column_names: Annotated[list[str] | None, "The column names to include."] = None
    output_format: Annotated[Literal["json", "parquet"], "The output format."] = "json"
    order_by: Annotated[
        str | None,
        "The column name to order by (use '-' prefix to order by descending order).",
    ] = None


@router.get("/{tid}/data-frames/slice")
async def slice_data_frame(  # noqa: PLR0912,C901
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    payload: _SliceDataInput,
) -> Response:
    """Get a slice of a data frame's contents.

    Args:
        user: The user making the request
        tid: The ID of the thread
        storage: The storage to use
        data_frame_id: The ID of the data frame to slice (mutually exclusive with data_frame_name)
        data_frame_name: The name of the data frame to slice (mutually exclusive with data_frame_id)
        offset: From which offset to start the slice. If not provided, starts with 0
        limit: The number of rows to slice. If not provided, slices to the end.
        column_names: List of column names to include. If not provided, returns all columns
        output_format: Output format - either "json" or "parquet"
        order_by: The column name to order by (use '-' prefix to order by descending order).

    Returns:
        A streaming response with the sliced data in the specified format
    """
    from agent_platform.core.errors.base import PlatformError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    # Validate that exactly one of data_frame_id or data_frame_name is provided
    if payload.data_frame_id is None and payload.data_frame_name is None:
        raise PlatformError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Either data_frame_id or data_frame_name must be provided",
        )

    if payload.data_frame_id is not None and payload.data_frame_name is not None:
        raise PlatformError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Only one of data_frame_id or data_frame_name can be provided",
        )

    base_storage = typing.cast(BaseStorage, storage)
    data_frames_kernel = DataFramesKernel(base_storage, user, tid)

    # Find the data frame
    data_frame = None
    if payload.data_frame_id is not None:
        # Get by ID
        data_frames = await base_storage.list_data_frames(tid)
        for df in data_frames:
            if df.data_frame_id == payload.data_frame_id:
                data_frame = df
                break
        else:
            raise PlatformError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Data frame with id {payload.data_frame_id} not found in thread: {tid}",
            )
    else:
        # Get by name
        data_frames = await base_storage.list_data_frames(tid)
        for df in data_frames:
            if df.name == payload.data_frame_name:
                data_frame = df
                break
        else:
            raise PlatformError(
                error_code=ErrorCode.NOT_FOUND,
                message=(
                    f"Data frame with name {payload.data_frame_name} not found in thread: {tid}"
                ),
            )

    try:
        # Resolve the data frame
        resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)

        # Get the sliced data
        sliced_data = resolved_df.slice(
            offset=payload.offset,
            limit=payload.limit,
            column_names=payload.column_names,
            output_format=payload.output_format,
            order_by=payload.order_by,
        )

        # Return as streaming response
        if payload.output_format == "json":
            return Response(content=sliced_data, media_type="application/json")
        elif payload.output_format == "parquet":
            return Response(
                content=sliced_data,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={data_frame.name}.parquet"},
            )
        else:
            raise PlatformError(
                message=f"Unsupported format: {payload.output_format}",
            )

    except PlatformError:
        raise
    except Exception as e:
        logger.error("Error slicing data frame", error=e, data_frame_id=data_frame.data_frame_id)
        raise PlatformError(message="Internal server error while slicing data frame") from e
