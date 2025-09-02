import datetime
import typing
import uuid

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from sema4ai.actions import Table

    from agent_platform.server.storage.base import BaseStorage

    from .data_frames_kernel import DataFramesKernel
    from .data_node import DataNodeResult

logger = get_logger(__name__)


async def create_data_frame_from_sql_computation_api(  # noqa: PLR0913
    data_frames_kernel: "DataFramesKernel",
    storage: "BaseStorage",
    new_data_frame_name: str,
    sql_query: str,
    dialect: str,
    description: str | None = None,
    num_samples: int = 0,
) -> "tuple[DataNodeResult, Table]":
    """Create a new data frame from existing data frames using a SQL query.

    Args:
        storage: The storage instance
        new_data_frame_name: The name for the new data frame
        sql_query: The SQL query to execute
        description: Optional description for the new data frame
        dialect: The dialect of the SQL query to use ("postgres", "mysql", "sqlite", etc).
        num_samples: The number of rows to return from the data frame.
            Note: Internally we always have to preload some samples to save in the
            data frame, but if the caller will require more, we'll actually load that many
            samples (but then just save the internally required number of samples in the data
            frame).
    Returns:
        A node which can later be queried for the data (the platform data frame is
        available in it) and a table with the number of samples required.

    Raises:
        PlatformError: If the computation fails or data frames are not found.
    """
    import sqlglot
    from sema4ai.actions import Table

    from agent_platform.core.data_frames.data_frames import (
        DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT,
        DataFrameSource,
        PlatformDataFrame,
    )
    from agent_platform.core.errors.base import PlatformError
    from agent_platform.server.data_frames.data_frames_kernel import (
        extract_variable_names_required_from_sql_computation,
    )
    from agent_platform.server.data_frames.data_node import DataNodeResult
    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    expressions = sqlglot.parse(sql_query, dialect=dialect)
    if len(expressions) != 1:
        raise PlatformError(
            message=f"SQL query must be a single expression. Found: {len(expressions)} "
            f"SQL query: {sql_query!r}"
        )

    expr = expressions[0]
    if expr is None or not hasattr(expr, "key"):
        raise PlatformError(message=f"SQL query is not a valid expression: {sql_query!r}")

    reasons = get_destructive_reasons(expr)
    if reasons:
        raise PlatformError(
            message=f"Unable to create data frame from SQL query: {sql_query} (Errors: {reasons})"
        )

    required_table_names = extract_variable_names_required_from_sql_computation(sql_query, dialect)

    computation_input_sources: dict[str, DataFrameSource] = {}

    # Get the thread to find the agent_id
    thread = await data_frames_kernel.get_thread()
    if not thread:
        raise PlatformError(message="Thread not found")

    all_data_frames = await data_frames_kernel.list_data_frames()

    # Get the data frame from storage
    for df in all_data_frames:
        if df.name in required_table_names:
            required_table_names.remove(df.name)
            computation_input_sources[df.name] = DataFrameSource(
                source_type="data_frame",
                source_id=df.data_frame_id,
            )
            if not required_table_names:
                break

    if required_table_names:
        raise PlatformError(
            message=(
                f"Data frame(s) with name(s) {required_table_names!r} not found. "
                f"Available data frames in thread: {[df.name for df in all_data_frames]}"
            )
        )

    # Create the new data frame
    data_frame = PlatformDataFrame(
        data_frame_id=str(uuid.uuid4()),
        user_id=data_frames_kernel.user_id,
        agent_id=thread.agent_id,
        thread_id=data_frames_kernel.tid,
        num_rows=0,  # We don't know the number of rows yet
        num_columns=0,  # We don't know the number of columns yet
        column_headers=[],  # We don't know the column headers yet
        name=new_data_frame_name,
        input_id_type="sql_computation",
        created_at=datetime.datetime.now(datetime.UTC),
        computation_input_sources=computation_input_sources,
        description=description,
        computation=sql_query,
        extra_data=PlatformDataFrame.build_extra_data(sql_dialect=dialect),
    )

    resolved_df: DataNodeResult = await data_frames_kernel.resolve_data_frame(data_frame)

    if num_samples > 0:
        use_num_samples = max(num_samples, DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT)
    else:
        use_num_samples = DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT

    # We always have to compute the data frame and cache a few samples which will
    # always be provided to the LLM.
    sliced_data = typing.cast(
        Table,
        resolved_df.slice(
            offset=0,
            limit=use_num_samples,
            column_names=None,
            output_format="table",
        ),
    )

    # Update the data frame with the computed data frame now that it's materialized
    data_frame.num_rows = resolved_df.num_rows
    data_frame.num_columns = resolved_df.num_columns
    data_frame.column_headers = resolved_df.column_headers
    data_frame.patch_extra_data(sample_rows=sliced_data.rows[:DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT])

    # Save the data frame to storage
    await storage.save_data_frame(data_frame)

    new_rows = sliced_data.rows[:num_samples]
    return resolved_df, Table(columns=sliced_data.columns, rows=new_rows)
