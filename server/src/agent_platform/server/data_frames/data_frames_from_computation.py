# ruff: noqa: E501
import datetime
import typing
import uuid

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from sema4ai.actions import Table

    from agent_platform.core.data_frames.data_frames import (
        DataFrameSource,
    )
    from agent_platform.core.data_frames.semantic_data_model_types import (
        LogicalTable,
    )
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


async def _get_tables_from_specific_sdm(
    data_frames_kernel: "DataFramesKernel",
    semantic_data_model_name: str,
) -> "dict[str, LogicalTable]":
    """Get table info when a specific semantic_data_model_name is provided.

    Args:
        data_frames_kernel: The data frames kernel instance
        semantic_data_model_name: The name of the semantic data model to use

    Returns:
        A dict mapping table names to their LogicalTable info

    Raises:
        PlatformError: If the semantic data model is not found
    """
    from agent_platform.core.errors.base import PlatformError

    table_name_to_table_info: dict[str, LogicalTable] = {}

    semantic_data_models_infos = await data_frames_kernel.get_semantic_data_models()

    # Find the specified semantic data model
    target_sdm_info = None
    for semantic_data_model_and_refs in semantic_data_models_infos:
        semantic_data_model_info = semantic_data_model_and_refs.semantic_data_model_info
        semantic_data_model = semantic_data_model_info["semantic_data_model"]
        if semantic_data_model.name == semantic_data_model_name:
            target_sdm_info = semantic_data_model_info
            break

    if target_sdm_info is None:
        available_names = [
            sdm.semantic_data_model_info["semantic_data_model"].name
            for sdm in semantic_data_models_infos
            if sdm.semantic_data_model_info["semantic_data_model"].name
        ]
        raise PlatformError(
            message=(
                f"Semantic data model with name "
                f"{semantic_data_model_name!r} not found. "
                f"Available semantic data models: {available_names}"
            )
        )

    semantic_data_model = target_sdm_info["semantic_data_model"]
    tables: list[LogicalTable] = semantic_data_model.tables or []
    for table in tables:
        name = table.get("name")
        if not name:
            continue
        table_name_to_table_info[name] = table

    return table_name_to_table_info


async def _get_tables_from_data_frames_and_sdms(
    data_frames_kernel: "DataFramesKernel",
    all_data_frames: list,
    required_table_names: set[str],
) -> tuple[
    dict[str, "LogicalTable"],
    dict[str, str],
    dict[str, "DataFrameSource"],
    set[str | None],
]:
    """Get table info when semantic_data_model_name is None.

    First checks data frames in the thread, then falls back to semantic
    data models.

    Args:
        data_frames_kernel: The data frames kernel instance
        all_data_frames: List of all data frames in the thread
        required_table_names: Set of table names required by the SQL
            query (modified in place)

    Returns:
        A tuple of:
        - table_name_to_table_info: Dict mapping table names to
          LogicalTable info
        - table_name_to_sdm_name: Dict mapping table names to their
          semantic data model names
        - computation_input_sources: Dict mapping table names to
          DataFrameSource
        - dialects_found: Set of dialects found in the data frames
    """
    from agent_platform.core.data_frames.data_frames import (
        DataFrameSource,
    )

    table_name_to_table_info: dict[str, LogicalTable] = {}
    table_name_to_sdm_name: dict[str, str] = {}
    computation_input_sources: dict[str, DataFrameSource] = {}
    dialects_found: set[str | None] = set()

    # First, check for data frames in the thread
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

    # If tables are still required, look in semantic data models
    if required_table_names:
        semantic_data_models_infos = await data_frames_kernel.get_semantic_data_models()
        for semantic_data_model_and_refs in semantic_data_models_infos:
            semantic_data_model_info = semantic_data_model_and_refs.semantic_data_model_info
            semantic_data_model = semantic_data_model_info["semantic_data_model"]
            sdm_name = semantic_data_model.name
            tables: list[LogicalTable] = semantic_data_model.tables or []
            if not tables:
                continue
            for table in tables:
                name = table.get("name")
                if not name:
                    continue
                table_name_to_table_info[name] = table
                if sdm_name:
                    table_name_to_sdm_name[name] = sdm_name

    return (
        table_name_to_table_info,
        table_name_to_sdm_name,
        computation_input_sources,
        dialects_found,
    )


async def _process_tables_and_get_dialect(
    data_frames_kernel: "DataFramesKernel",
    required_table_names: set[str],
    table_name_to_table_info: "dict[str, LogicalTable]",
    table_name_to_sdm_name: dict[str, str],
    computation_input_sources: dict,
    dialects_found: set[str | None],
    dialect: str | None,
    semantic_data_model_name: str | None,
) -> str | None:
    """Process tables from semantic data models and determine the SQL
    dialect.

    Note: Dialect is only set when processing semantic data model tables,
    not when all sources are existing data frames.

    Args:
        data_frames_kernel: The data frames kernel instance
        required_table_names: Set of table names required (modified in
            place)
        table_name_to_table_info: Dict mapping table names to
            LogicalTable info
        table_name_to_sdm_name: Dict mapping table names to their SDM
            names
        computation_input_sources: Dict to populate with DataFrameSource
            objects (modified in place)
        dialects_found: Set of dialects found (modified in place)
        dialect: The SQL dialect (if already specified)
        semantic_data_model_name: The semantic data model name (if
            specified)

    Returns:
        The determined SQL dialect (or None if no semantic data model
        tables were processed)

    Raises:
        PlatformError: If required tables are not found
    """
    from agent_platform.core.data_frames.data_frames import (
        DataFrameSource,
    )
    from agent_platform.core.data_frames.semantic_data_model_types import (
        BaseTable,
    )

    data_connection_ids: set[str] = set()
    processed_sdm_tables = False

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

            # Extract column mappings from the logical table
            logical_column_names_to_expr = extract_column_name_to_expr(table_info)

            # Use provided semantic_data_model_name if set, otherwise
            # use the mapped name
            sdm_name_for_source = (
                semantic_data_model_name if semantic_data_model_name is not None else table_name_to_sdm_name.get(name)
            )

            computation_input_sources[name] = DataFrameSource(
                source_type="semantic_data_model",
                semantic_data_model_name=sdm_name_for_source,
                base_table=base_table,
                logical_table_name=table_info.get("name"),
                logical_column_names_to_expr=(logical_column_names_to_expr if logical_column_names_to_expr else None),
            )
            required_table_names.remove(name)
            processed_sdm_tables = True

    # Determine the dialect if not already specified
    # Only set dialect when processing semantic data model tables
    if not dialect and processed_sdm_tables:
        if data_connection_ids:
            data_connections = await data_frames_kernel.get_data_connections(data_connection_ids)
            dialects_found.update(data_connection.engine for data_connection in data_connections)

        dialects_found.discard(None)
        if len(dialects_found) == 1:
            dialect = dialects_found.pop()
        else:
            # Multiple dialects found, use duckdb for federation.
            dialect = "duckdb"

    return dialect


async def create_data_frame_from_sql_computation_api(
    data_frames_kernel: "DataFramesKernel",
    storage: "BaseStorage",
    new_data_frame_name: str,
    sql_query: str,
    dialect: str | None,
    description: str | None = None,
    num_samples: int = 0,
    semantic_data_model_name: str | None = None,
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
        semantic_data_model_name: If provided, only use tables from this semantic data model.
            When set, source resolution will skip data frames and other semantic data models.
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
    from agent_platform.core.errors.base import PlatformError
    from agent_platform.server.data_frames.data_node import DataNodeResult
    from agent_platform.server.data_frames.sql_manipulation import (
        extract_variable_names_required_from_sql_computation,
        validate_sql_query,
    )

    sql_ast = validate_sql_query(sql_query, dialect)

    required_table_names: set[str] = extract_variable_names_required_from_sql_computation(sql_ast)

    thread = await data_frames_kernel.get_thread()
    all_data_frames = await data_frames_kernel.list_data_frames()

    # Step 1 & 2: Get table info based on whether semantic_data_model_name is provided
    if semantic_data_model_name is not None:
        table_name_to_table_info = await _get_tables_from_specific_sdm(
            data_frames_kernel,
            semantic_data_model_name,
        )
        table_name_to_sdm_name: dict[str, str] = {}
        computation_input_sources: dict[str, DataFrameSource] = {}
        dialects_found: set[str | None] = set()
    else:
        (
            table_name_to_table_info,
            table_name_to_sdm_name,
            computation_input_sources,
            dialects_found,
        ) = await _get_tables_from_data_frames_and_sdms(
            data_frames_kernel,
            all_data_frames,
            required_table_names,
        )

    # Step 3: Process tables and determine dialect
    dialect = await _process_tables_and_get_dialect(
        data_frames_kernel,
        required_table_names,
        table_name_to_table_info,
        table_name_to_sdm_name,
        computation_input_sources,
        dialects_found,
        dialect,
        semantic_data_model_name,
    )

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
        columns={},  # We don't know the columns yet
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
        await resolved_df.slice(
            offset=0,
            limit=use_num_samples,
            column_names=None,
            output_format="table",
        ),
    )

    # Update the data frame with the computed data frame now that it's materialized
    # Note: We use sliced_data.columns for column info because resolved_df properties
    # may not be populated correctly for all backend types (e.g., Redshift where ibis
    # cannot infer schema from lazy SQL expressions until the query is executed)
    data_frame.num_rows = await resolved_df.num_rows()
    data_frame.num_columns = len(sliced_data.columns)
    data_frame.column_headers = list(sliced_data.columns)
    data_frame.columns = resolved_df.columns
    data_frame.patch_extra_data(sample_rows=sliced_data.rows[:DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT])

    # Save the data frame to storage
    await storage.save_data_frame(data_frame)

    new_rows = sliced_data.rows[:num_samples]
    return resolved_df, Table(columns=sliced_data.columns, rows=new_rows)
