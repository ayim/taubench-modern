# ruff: noqa: E501
import datetime
import typing
import uuid

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from sema4ai.actions import Table

    from agent_platform.core.data_frames.semantic_data_model_types import LogicalTable
    from agent_platform.server.storage.base import BaseStorage

    from .data_frames_kernel import DataFramesKernel
    from .data_node import DataNodeResult

logger = get_logger(__name__)


def extract_column_name_to_expr(table: "LogicalTable") -> dict[str, str]:
    """Extract a mapping of logical column names to their physical SQL expressions from a
    logical table in a semantic data model.

    Args:
        table: A LogicalTable dict containing dimensions, facts, time_dimensions, and metrics.

    Returns:
        A dict mapping logical column names to their physical SQL expressions.
        Example: {"customer_name": "first_name || ' ' || last_name", "revenue": "amount"}
    """
    from agent_platform.core.data_frames.semantic_data_model_types import CATEGORIES

    logical_column_name_to_expr: dict[str, str] = {}

    # Iterate through all column types (dimensions, facts, time_dimensions, metrics)
    for category in CATEGORIES:
        columns = table.get(category) or []
        for column_def in columns:
            if isinstance(column_def, dict):
                name = column_def.get("name")
                expr = column_def.get("expr")
                if name and expr:
                    logical_column_name_to_expr[name] = expr

    return logical_column_name_to_expr


async def create_data_frame_from_sql_computation_api(  # noqa
    data_frames_kernel: "DataFramesKernel",
    storage: "BaseStorage",
    new_data_frame_name: str,
    sql_query: str,
    dialect: str | None,
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
            If None, the dialect is inferred from the semantic data model(s) or data frame(s) being
            queried.
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
    from sema4ai.actions import Table

    from agent_platform.core.data_frames.data_frames import (
        DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT,
        DataFrameSource,
        PlatformDataFrame,
    )
    from agent_platform.core.data_frames.semantic_data_model_types import BaseTable, LogicalTable
    from agent_platform.core.errors.base import PlatformError
    from agent_platform.server.data_frames.data_node import DataNodeResult
    from agent_platform.server.data_frames.sql_manipulation import (
        extract_variable_names_required_from_sql_computation,
        validate_sql_query,
    )

    sql_ast = validate_sql_query(sql_query, dialect)

    required_table_names: set[str] = extract_variable_names_required_from_sql_computation(sql_ast)

    computation_input_sources: dict[str, DataFrameSource] = {}

    thread = await data_frames_kernel.get_thread()

    all_data_frames = await data_frames_kernel.list_data_frames()
    table_name_to_table_info: dict[str, LogicalTable] = {}

    dialects_found: set[str | None] = set()

    # Get the data frame from storage
    for df in all_data_frames:
        if df.name in required_table_names:
            required_table_names.remove(df.name)
            computation_input_sources[df.name] = DataFrameSource(
                source_type="data_frame",
                source_id=df.data_frame_id,
            )
            dialects_found.add(df.sql_dialect)
            if not required_table_names:
                break

    if required_table_names:
        # If we don't find the data frames in the thread, we look for them in the semantic data
        # models (which would allow us to get data directly from a file or database).
        semantic_data_models_infos = await data_frames_kernel.get_semantic_data_models()
        for semantic_data_model_and_refs in semantic_data_models_infos:
            semantic_data_model = semantic_data_model_and_refs.semantic_data_model_info[
                "semantic_data_model"
            ]
            tables: list[LogicalTable] = semantic_data_model.get("tables") or []
            if not tables:
                continue
            for table in tables:
                name = table.get("name")
                if not name:
                    continue
                table_name_to_table_info[name] = table

        data_connection_ids: set[str] = set()
        for name in tuple(required_table_names):
            table_info = table_name_to_table_info.get(name)
            if table_info:
                base_table: BaseTable | None = table_info.get("base_table")
                if base_table is not None:
                    data_connection_id = base_table.get("data_connection_id")
                    if data_connection_id is not None:
                        data_connection_ids.add(data_connection_id)
                    elif base_table.get("file_reference") is not None:
                        dialects_found.add("duckdb")

                # Ok, name found in a semantic data model
                # Extract column mappings from the logical table
                logical_column_names_to_expr = extract_column_name_to_expr(table_info)

                computation_input_sources[name] = DataFrameSource(
                    source_type="semantic_data_model",
                    base_table=base_table,
                    logical_table_name=table_info.get("name"),
                    logical_column_names_to_expr=logical_column_names_to_expr
                    if logical_column_names_to_expr
                    else None,
                )
                required_table_names.remove(name)

        if not dialect:
            # We need to compute it based on the found dialects (update it with the data
            # connections found and set it accordingly)
            if data_connection_ids:
                data_connections = await data_frames_kernel.get_data_connections(
                    data_connection_ids
                )
                dialects_found.update(
                    data_connection.engine for data_connection in data_connections
                )

            dialects_found.discard(None)
            if len(dialects_found) == 1:
                dialect = dialects_found.pop()
            else:
                dialect = "duckdb"  # Multiple dialects found, use duckdb for federation.

    if required_table_names:
        raise PlatformError(
            message=(
                f"Data frame(s) or Semantic Data Model table(s) with name(s) {required_table_names!r} not found.\n"
                f"Available data frames in thread: {[df.name for df in all_data_frames]}\n"
                f"Available Semantic Data Model tables: {list(table_name_to_table_info.keys())}\n"
                f"Expected SQL to be compatible with: {dialect}"
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
