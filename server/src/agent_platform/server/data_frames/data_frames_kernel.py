# ruff: noqa: PLR0912, PLR0915, C901, E501
import json
import typing

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames.data_frames import DataFrameSource, PlatformDataFrame
    from agent_platform.core.thread.thread import Thread
    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelAndReferences,
    )
    from agent_platform.server.kernel.ibis import AsyncIbisConnection
    from agent_platform.server.storage.base import BaseStorage

    from .data_frames_assembly_info import AssemblyInfo
    from .data_node import DataNodeResult, SupportedIbisBackends


logger = get_logger(__name__)


def recursion_guard(func: typing.Callable) -> typing.Callable:
    """
    A decorator to prevent recursion.
    """

    def wrapper(self, data_frame: "PlatformDataFrame", *args, **kwargs):
        if data_frame.data_frame_id in self._computing_data_frames:
            from agent_platform.core.errors.base import PlatformError

            raise PlatformError(message=f"Recursion detected when computing data frame: {data_frame.data_frame_id}")
        self._computing_data_frames.add(data_frame.data_frame_id)
        try:
            return func(self, data_frame, *args, **kwargs)
        finally:
            self._computing_data_frames.remove(data_frame.data_frame_id)

    return wrapper


class Dependencies:
    """
    A class to represent the dependencies of a data frame.
    """

    def __init__(self, data_frame: "PlatformDataFrame"):
        self._data_frame = data_frame  # the base data frame that is being computed

        # The dependencies of the data frame
        self._data_frames: dict[str, PlatformDataFrame] = {}
        self._sub_dependencies: dict[str, Dependencies] = {}
        self._data_frames_sources: dict[str, DataFrameSource] = {}

    def __repr__(self) -> str:
        lst = []
        lst.append(f"Dependencies for data frame: {self._data_frame.name}")
        lst.append("Data frames:")
        for name in self._data_frames.keys():
            lst.append(f"{name}")
        lst.append("Data frames sources:")
        for name, df_source in self._data_frames_sources.items():
            lst.append(f"{name}:{json.dumps(df_source.model_dump(), default=str, indent=2)}")
        lst.append("Sub dependencies:")
        for name, sub_dependency in self._sub_dependencies.items():
            as_str = repr(sub_dependency)
            as_str = f"{name}: \n{as_str}"
            as_str = as_str.replace("\n", "\n  ")
            lst.append(as_str)
        return "\n".join(lst)

    def add_leaf_data_frame_dependency(self, name: str, data_frame: "PlatformDataFrame"):
        """
        Adds a "leaf" data frame dependency (i.e.: one which will load directly
        from a file or in-memory).
        """
        self._data_frames[name] = data_frame

    def add_leaf_data_frame_source_dependency(self, name: str, data_frame_source: "DataFrameSource"):
        """
        Adds a data frame source dependency (i.e.: one which will load from a
        semantic data model).
        """
        self._data_frames_sources[name] = data_frame_source

    def add_sub_dependencies(self, name: str, sub_dependencies: "Dependencies"):
        """
        Add a full new dependency which has its own dependencies (this is
        expected to happen when a SQL references another SQL dataframe).
        """
        self._sub_dependencies[name] = sub_dependencies

    def _get_backend_from_df(self, df: "PlatformDataFrame") -> "SupportedIbisBackends | None":
        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.data_frames.data_node import DUCK_DB_BACKEND

        if df.input_id_type == "sql_computation":
            return None
        elif df.input_id_type in ("in_memory", "file"):
            return DUCK_DB_BACKEND
        else:
            raise PlatformError(message=f"Unsupported input_id_type: {df.input_id_type}")

    def _get_backend_from_df_source(self, df_source: "DataFrameSource") -> "SupportedIbisBackends|None":
        from agent_platform.core.semantic_data_model.types import BaseTable
        from agent_platform.server.data_frames.data_node import (
            DUCK_DB_BACKEND,
            make_data_connection_backend,
        )

        if df_source.source_type == "semantic_data_model":
            base_table: BaseTable | None = typing.cast(BaseTable | None, df_source.base_table)
            if base_table is None:
                logger.error(
                    f"Semantic data model base table is None in DataFrameSource. df_source: {df_source!r}",
                )
                return None
            # Ok, we have a base table, let's see if it's a database or a file
            base_table_data_connection_id = base_table.get("data_connection_id")
            # Note that the database is actually usually part of the data connection
            if base_table_data_connection_id is not None:
                return make_data_connection_backend(base_table_data_connection_id)
            else:
                # Either file reference or data frame reference, both are materialized in duckdb
                return DUCK_DB_BACKEND

        return None

    def get_required_backends_recursive(self) -> "set[SupportedIbisBackends]":
        from agent_platform.server.data_frames.data_node import DUCK_DB_BACKEND

        backends: set[SupportedIbisBackends] = set()
        for df in self._data_frames.values():
            backend = self._get_backend_from_df(df)
            if backend is not None:
                backends.add(backend)

        for df_source in self._data_frames_sources.values():
            backend = self._get_backend_from_df_source(df_source)
            if backend is not None:
                backends.add(backend)

        for sub_dependencies in self._sub_dependencies.values():
            backends.update(sub_dependencies.get_required_backends_recursive())

        if not backends:
            # Default to duckdb if no backends are found (i.e.: "select 1" should work).
            backends.add(DUCK_DB_BACKEND)

        return backends

    async def resolve_graph(self, kernel: "DataFramesKernel", data_frame: "PlatformDataFrame") -> "DataNodeResult":
        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.data_frames.data_node import (
            SupportedIbisBackends,
        )

        required_backends: set[SupportedIbisBackends] = self.get_required_backends_recursive()
        if len(required_backends) != 1:
            raise PlatformError(
                message=f"Unable to compute data frame: multiple required backends: "
                f"{required_backends} "
                f"(federation not supported yet)"
            )
        else:
            use_backend = required_backends.pop()
            if use_backend.backend == "duckdb":
                import time

                import ibis

                from agent_platform.server.kernel.ibis import create_async_connection

                initial_time = time.monotonic()
                raw_con = ibis.duckdb.connect()
                con = create_async_connection(raw_con, engine="duckdb")
                logger.info(f"Created ibis.duckdb connection in {time.monotonic() - initial_time:.2f} seconds")
                return await self._resolve_sql_with_connection(kernel, data_frame, con)

            elif use_backend.backend == "data-connection":
                return await self._resolve_sql_with_data_connection_backend(kernel, data_frame, use_backend)

            else:
                raise PlatformError(message=f"Unsupported required_backend: {use_backend}")

    def _iter_recursive_data_frames(self) -> "Iterator[PlatformDataFrame]":
        yield from self._data_frames.values()
        for sub_dependencies in self._sub_dependencies.values():
            yield from sub_dependencies._iter_recursive_data_frames()

    def _iter_recursive_data_frame_sources_with_names(self) -> "Iterator[tuple[str, DataFrameSource]]":
        """Iterate over data frame sources with their table names (dict keys)."""
        yield from self._data_frames_sources.items()
        for sub_dependencies in self._sub_dependencies.values():
            yield from sub_dependencies._iter_recursive_data_frame_sources_with_names()

    def get_all_data_frame_sources_with_names_recursive(self) -> "list[tuple[str, DataFrameSource]]":
        """Get all data frame sources with their table names (dict keys).

        This method collects:
        1. Semantic data model sources (database tables or file references) with their table names
        2. In-memory/file data frames as pseudo-sources (without table names, using empty string as key)

        Data frame references in computation_input_sources that point to SQL computations are NOT
        included because they represent intermediate computations handled as CTEs.

        Returns:
            List of tuples (table_name, DataFrameSource). For in-memory/file data frames,
            table_name will be an empty string since they don't have logical table names.
        """
        from agent_platform.core.data_frames.data_frames import DataFrameSource

        sources_with_names: list[tuple[str, DataFrameSource]] = []

        # Add sources from the root data frame's computation_input_sources with their keys
        if self._data_frame.computation_input_sources:
            for table_name, source in self._data_frame.computation_input_sources.items():
                if source.source_type == "semantic_data_model":
                    sources_with_names.append((table_name, source))

        # Add sources from recursive dependencies with their keys
        sources_with_names.extend(self._iter_recursive_data_frame_sources_with_names())

        # Add pseudo-sources for leaf data frames (in-memory/file), NOT for sql_computation
        # SQL computation dataframes are handled as CTEs, not as materialized sources
        # These don't have table names, so use empty string as the key
        for df in self._iter_recursive_data_frames():
            if df.input_id_type in ("in_memory", "file"):
                # Create a pseudo DataFrameSource to represent in-memory/file data frames
                sources_with_names.append(
                    (
                        "",  # No table name for in-memory/file data frames
                        DataFrameSource(
                            source_type="data_frame",
                            source_id=df.data_frame_id,
                        ),
                    )
                )

        return sources_with_names

    def _iter_recursive_sql_computation_data_frames(self) -> "Iterator[PlatformDataFrame]":
        """Yield SQL computation data frames in dependency-first order (topological sort).

        This ensures that when generating CTEs, dependencies are defined before they are
        referenced, preventing "forward reference" errors in databases like Postgres.

        Uses depth-first post-order traversal: children are yielded before their parents.
        """
        for sub_dependencies in self._sub_dependencies.values():
            # First, recursively yield all dependencies of this sub-dependency
            yield from sub_dependencies._iter_recursive_sql_computation_data_frames()
            # Then yield this sub-dependency itself (after its dependencies)
            yield sub_dependencies._data_frame

    async def _resolve_sql_with_data_connection_backend(
        self,
        kernel: "DataFramesKernel",
        data_frame: "PlatformDataFrame",
        use_backend: "SupportedIbisBackends",
    ) -> "DataNodeResult":
        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.kernel.data_connection_inspector import DataConnectionInspector

        data_connection_id = use_backend.data_connection_id
        if data_connection_id is None:
            raise PlatformError(message=f"Data connection id or database is None for backend: {use_backend}")
        data_connection = await kernel._storage.get_data_connection(data_connection_id)
        con = await DataConnectionInspector.create_ibis_connection(data_connection)
        return await self._resolve_sql_with_connection(kernel, data_frame, con)

    async def _resolve_sql_with_connection(
        self,
        kernel: "DataFramesKernel",
        data_frame: "PlatformDataFrame",
        con: "AsyncIbisConnection",
    ) -> "DataNodeResult":
        """Execute SQL query using appropriate strategy based on data source type.

        Routes to either:
        - DatabaseQueryExecutor: For queries against database tables (Postgres/Snowflake/etc.)
        - FileBasedQueryExecutor: For queries against CSV/Excel files (DuckDB dialect) - FALLBACK

        FileBasedQueryExecutor is used as fallback for edge cases where dialect is None
        or not explicitly handled by other strategies.
        """
        from agent_platform.server.data_frames.database_query_executor import DatabaseQueryExecutor
        from agent_platform.server.data_frames.file_based_query_executor import FileBasedQueryExecutor

        # Try DatabaseQueryExecutor first for explicit database dialects
        db_strategy = DatabaseQueryExecutor()
        if db_strategy.can_handle(data_frame, self):
            return await db_strategy.execute(kernel, data_frame, con, self)

        # Fallback to FileBasedQueryExecutor (handles DuckDB and edge cases)
        file_strategy = FileBasedQueryExecutor()
        return await file_strategy.execute(kernel, data_frame, con, self)


class DataFramesKernel:
    """
    A kernel for data frames.

    This kernel is responsible for materializing data frames (getting its pre-conditions,
    executing SQL queries, etc).

    It may save state in the class itself while doing it, so, each time a computation
    is needed, it should be re-created.

    It may load the data frames from storage, but it should not store anything in this class.
    """

    def __init__(self, storage: "BaseStorage", user: "AuthedUser", tid: str):
        self._storage = storage
        self._user = user
        self._tid = tid
        self._agent_id: str | None = None
        self._thread: Thread | None = None

        # Dict of data frame id to resolved data frame.
        # This is used to avoid resolving the same data frame multiple times.
        self._resolved_data_frames: dict[str, DataNodeResult] = {}
        self._computing_data_frames: set[str] = set()

        self._data_frames: list[PlatformDataFrame] | None = None
        self._semantic_data_models: list[SemanticDataModelAndReferences] | None = None
        self._name_to_data_frame: dict[str, PlatformDataFrame] | None = None
        self._data_connection_id_to_data_connection: dict[str, DataConnection] = {}

    async def get_thread(self) -> "Thread":
        if self._thread is None:
            self._thread = await self._storage.get_thread(self._user.user_id, self._tid)
        return self._thread

    async def get_agent_id(self) -> str:
        if self._agent_id is None:
            thread = await self.get_thread()
            self._agent_id = thread.agent_id
        return self._agent_id

    async def list_data_frames(self) -> list["PlatformDataFrame"]:
        if self._data_frames is None:
            self._data_frames = await self._storage.list_data_frames(self._tid)
        return self._data_frames

    async def _get_name_to_data_frame(self) -> "dict[str, PlatformDataFrame]":
        if self._name_to_data_frame is not None:
            return self._name_to_data_frame

        data_frames = await self.list_data_frames()
        self._name_to_data_frame = {df.name: df for df in data_frames}
        return self._name_to_data_frame

    async def get_semantic_data_models(self) -> list["SemanticDataModelAndReferences"]:
        if self._semantic_data_models is None:
            from agent_platform.server.data_frames.semantic_data_model_collector import (
                SemanticDataModelCollector,
            )

            collector = SemanticDataModelCollector(
                agent_id=await self.get_agent_id(),
                thread_id=self._tid,
                user=self._user,
                state=None,  # No state available in this context
            )
            self._semantic_data_models = await collector.collect_semantic_data_models(self._storage)
        assert self._semantic_data_models is not None
        return self._semantic_data_models

    async def get_data_connections(self, data_connection_ids: set[str]) -> list["DataConnection"]:
        missing: set[str] = set()
        data_connections: list[DataConnection] = []

        for data_connection_id in data_connection_ids:
            data_connection = self._data_connection_id_to_data_connection.get(data_connection_id)
            if data_connection is None:
                missing.add(data_connection_id)
            else:
                data_connections.append(data_connection)

        if missing:
            queried_data_connections = await self._storage.get_data_connections(list(missing))
            for data_connection in queried_data_connections:
                self._data_connection_id_to_data_connection[data_connection.id] = data_connection
                data_connections.append(data_connection)

        return data_connections

    @property
    def tid(self) -> str:
        return self._tid

    @property
    def user_id(self) -> str:
        return self._user.user_id

    async def _compute_data_frame_graph(
        self,
        data_frame: "PlatformDataFrame",
        name_to_data_frame: "dict[str, PlatformDataFrame]",
    ) -> "Dependencies":
        """
        Compute the dependencies of a data frame.

        Recursively computes the dependencies of a data frame
        (each data frame may depend on other data frames, and we need to compute them in order
        -- in practice we have a graph of data frames so that the current one depends on
        a previous one being available).

        Args:
            data_frame: The data frame to compute the dependencies of.
            name_to_data_frame: All the data frames in the thread.
            dependencies: The dependencies to result.

        Returns:
            The dependencies of the data frame.
        """
        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.data_frames.sql_manipulation import (
            extract_variable_names_required_from_sql_computation,
            validate_sql_query,
        )

        dependencies = Dependencies(data_frame)

        if data_frame.input_id_type == "sql_computation":
            # ok, for a sql computation, we need to find the data frames that are referenced
            # in the computation.
            sql_query = data_frame.computation
            if sql_query is None:
                raise PlatformError(
                    message="Data frame marked as a sql computation has no computation SQL query "
                    f"defined, which is needed to materialize it. Data frame name: "
                    f"{data_frame.name}, id: {data_frame.data_frame_id}"
                )
            sql_ast = validate_sql_query(sql_query, data_frame.sql_dialect, allow_mutate=data_frame.allow_mutate)
            required_variable_names = extract_variable_names_required_from_sql_computation(sql_ast)

            for name in required_variable_names:
                df = name_to_data_frame.get(name)
                if df is None:
                    # Ok, not a data frame, let's see if it's declared in the input sources
                    # (i.e.: using semantic data models information to resolve the data frame).
                    input_sources = data_frame.computation_input_sources
                    df_source = input_sources.get(name)
                    if df_source is None:
                        raise PlatformError(message=f"Data frame with name {name} not found")

                    dependencies.add_leaf_data_frame_source_dependency(name, df_source)

                elif df.input_id_type in ("sql_computation",):
                    sub_dependencies = await self._compute_data_frame_graph(df, name_to_data_frame)
                    # The order is important, first add dependencies and only to finish add the
                    # one that depends on them.
                    dependencies.add_sub_dependencies(name, sub_dependencies)

                else:
                    if df.input_id_type not in ("in_memory", "file"):
                        raise PlatformError(
                            message=f"Unsupported input_id_type: {df.input_id_type} for "
                            f"data frame: {df.name}, id: {df.data_frame_id}"
                        )

                    dependencies.add_leaf_data_frame_dependency(name, df)

        elif data_frame.input_id_type in ("in_memory", "file"):
            pass  # no deps
        else:
            raise PlatformError(
                message=f"Unsupported input_id_type: {data_frame.input_id_type} for data frame: "
                f"{data_frame.name}, id: {data_frame.data_frame_id}"
            )

        return dependencies

    async def _resolve_file_data_source(self, data_source: "DataFrameSource", table_name: str) -> "DataNodeResult":
        """
        A data frame source must be used to resolve contents from the semantic data model.

        Args:
            data_source: The DataFrameSource with base_table info
            table_name: The table name from the SDM (used as the data frame name)
        """
        import datetime
        import uuid

        from agent_platform.core.data_frames.data_frames import PlatformDataFrame
        from agent_platform.core.errors.base import PlatformError
        from agent_platform.core.semantic_data_model.types import BaseTable

        if data_source.source_type == "data_frame":
            raise RuntimeError("Must resolve as a data frame, not a data source")

        elif data_source.source_type == "semantic_data_model":
            base_table_info: BaseTable | None = typing.cast(BaseTable | None, data_source.base_table)
            if base_table_info is None:
                raise PlatformError(message=f"Data source info is None for data source: {data_source}")

            file_reference = base_table_info.get("file_reference")
            if file_reference is not None:
                temp_data_frame = PlatformDataFrame(
                    data_frame_id=str(uuid.uuid4()),
                    user_id=self._user.user_id,
                    agent_id=await self.get_agent_id(),
                    thread_id=self._tid,
                    num_rows=0,
                    num_columns=0,
                    column_headers=[],
                    columns={},
                    name=table_name,
                    input_id_type="file",
                    file_id=file_reference.get("file_id"),
                    file_ref=file_reference.get("file_ref"),
                    sheet_name=file_reference.get("sheet_name"),
                    computation_input_sources={},
                    description="",
                    computation=None,
                    parquet_contents=None,
                    extra_data=None,
                    created_at=datetime.datetime.now(datetime.UTC),
                )
                return await self.resolve_data_frame(temp_data_frame)
            else:
                raise PlatformError(message=f"file_reference is None for data source: {data_source}")

        raise PlatformError(message=f"Unsupported source_type: {data_source.source_type}")

    async def resolve_data_frame(
        self, data_frame: "PlatformDataFrame", assembly_info: "AssemblyInfo | None" = None
    ) -> "DataNodeResult":
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode
        from agent_platform.server.data_frames.data_node import (
            DataNodeFromDataReaderSheet,
            DataNodeFromInMemoryDataFrame,
        )
        from agent_platform.server.data_frames.data_reader import (
            create_file_data_reader,
            get_file_metadata,
        )

        if data_frame.data_frame_id in self._resolved_data_frames:
            return self._resolved_data_frames[data_frame.data_frame_id]

        if data_frame.input_id_type == "file":
            if data_frame.file_id is None and data_frame.file_ref is None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.PRECONDITION_FAILED,
                    message=(
                        "Error in database: Data frame is marked with having input "
                        "type file, but it has no file_id or file_ref!"
                    ),
                )

            file_metadata = await get_file_metadata(
                self._user.user_id,
                self._tid,
                self._storage,
                file_id=data_frame.file_id,
                file_ref=data_frame.file_ref,
            )
            data_reader = await create_file_data_reader(
                self._user,
                self._tid,
                self._storage,
                sheet_name=data_frame.sheet_name,
                file_metadata=file_metadata,
            )
            if data_reader.has_multiple_sheets():
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        "More than one sheet loaded when trying to load a single data "
                        f"frame (sheet_name passed: {data_frame.sheet_name}, file_id: "
                        f"{data_frame.file_id}, file_ref: {data_frame.file_ref}, "
                        f"thread_id: {self._tid}, data_frame.name: "
                        f"{data_frame.name}, data_frame_id: {data_frame.data_frame_id})"
                    ),
                )

            if assembly_info is not None:
                assembly_info.set_initial_data_frame(data_frame)

            data_node = DataNodeFromDataReaderSheet(data_frame, next(data_reader.iter_sheets()))
            self._resolved_data_frames[data_frame.data_frame_id] = data_node
            if assembly_info is not None:
                assembly_info.set_final_data_node(data_node)
            return data_node

        elif data_frame.input_id_type == "in_memory":
            if data_frame.parquet_contents is None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.PRECONDITION_FAILED,
                    message=(
                        "Error in database: Data frame is marked with having input "
                        "type in_memory, but it has no parquet_contents!"
                    ),
                )

            if assembly_info is not None:
                assembly_info.set_initial_data_frame(data_frame)

            data_node = DataNodeFromInMemoryDataFrame(data_frame)
            self._resolved_data_frames[data_frame.data_frame_id] = data_node
            if assembly_info is not None:
                assembly_info.set_final_data_node(data_node)
            return data_node

        elif data_frame.input_id_type == "sql_computation":
            from agent_platform.core.errors.base import PlatformError

            sql_query = data_frame.computation
            if sql_query is None:
                raise PlatformError(
                    message="Data frame has no computation SQL query defined, which "
                    f"is needed to compute it (input_id_type: {data_frame.input_id_type}). "
                    f"Data frame name: {data_frame.name}, id: "
                    f"{data_frame.data_frame_id}"
                )

            dependencies = await self._compute_data_frame_graph(data_frame, await self._get_name_to_data_frame())

            if assembly_info is not None:
                assembly_info.set_initial_data_frame(data_frame)
                assembly_info.set_dependencies(dependencies)

            data_node = await dependencies.resolve_graph(self, data_frame)
            if assembly_info is not None:
                assembly_info.set_final_data_node(data_node)

            self._resolved_data_frames[data_frame.data_frame_id] = data_node
            return data_node

        else:
            raise PlatformHTTPError(
                error_code=ErrorCode.PRECONDITION_FAILED,
                message=f"Unsupported input_id_type: {data_frame.input_id_type}",
            )

    def _get_required_backends_from_sources(
        self,
        computation_input_sources: "dict[str, DataFrameSource]",
    ) -> set["SupportedIbisBackends"]:
        """Get required backends from computation input sources.

        Simple helper to determine which backend(s) are needed to execute a query
        based on the data sources. Used by DML execution where we don't need
        table name or column mappings.

        Args:
            computation_input_sources: Sources mapping from _prepare_sql_execution

        Returns:
            Set of backends needed for execution
        """
        from agent_platform.server.data_frames.data_node import (
            DUCK_DB_BACKEND,
            SupportedIbisBackends,
            make_data_connection_backend,
        )

        required_backends: set[SupportedIbisBackends] = set()

        # Check each semantic data model source for its backend
        for source in computation_input_sources.values():
            if source.source_type == "semantic_data_model" and source.base_table is not None:
                data_connection_id = source.base_table.get("data_connection_id")
                if data_connection_id:
                    required_backends.add(make_data_connection_backend(data_connection_id))
                else:
                    # File reference or data frame reference - use duckdb
                    required_backends.add(DUCK_DB_BACKEND)

        # Default to duckdb if no backends found (e.g., "SELECT 1")
        if not required_backends:
            required_backends.add(DUCK_DB_BACKEND)

        return required_backends

    def _build_table_mappings_from_sources(
        self,
        computation_input_sources: "dict[str, DataFrameSource]",
    ) -> tuple[dict[str, str], dict[str, dict[str, str]], set["SupportedIbisBackends"]]:
        """Build table name and column mappings from computation input sources.

        This helper extracts common logic for mapping SDM table names to physical names
        and building column expression mappings. Used by both query execution and DML operations.

        Args:
            computation_input_sources: Sources mapping (table_name -> DataFrameSource)

        Returns:
            Tuple of:
            - table_name_to_expr: Mapping from SDM table names to actual physical names
            - table_name_to_column_names_to_expr: Column mappings per table
            - required_backends: Set of backends needed for execution
        """
        from agent_platform.server.data_frames.data_node import (
            DUCK_DB_BACKEND,
            SupportedIbisBackends,
            make_data_connection_backend,
        )

        table_name_to_expr: dict[str, str] = {}
        table_name_to_column_names_to_expr: dict[str, dict[str, str]] = {}
        required_backends: set[SupportedIbisBackends] = set()

        # Iterate over computation_input_sources with both keys (table names) and values
        for table_name, df_source in computation_input_sources.items():
            if df_source.source_type != "semantic_data_model" or df_source.base_table is None:
                continue

            # Store column mappings if available
            if df_source.column_names_to_expr:
                table_name_to_column_names_to_expr[table_name] = df_source.column_names_to_expr

            if df_source.base_table.get("data_connection_id") is not None:
                base_table = df_source.base_table
                actual_table_name = base_table.get("table")
                if actual_table_name:
                    schema = base_table.get("schema")
                    if schema:
                        actual_table_name = f"{schema}.{actual_table_name}"
                    table_name_to_expr[table_name] = actual_table_name

                data_connection_id = base_table.get("data_connection_id")
                if data_connection_id:
                    required_backends.add(make_data_connection_backend(data_connection_id))
            else:
                # File reference or data frame reference - use duckdb
                required_backends.add(DUCK_DB_BACKEND)

        # Default to duckdb if no backends found
        if not required_backends:
            required_backends.add(DUCK_DB_BACKEND)

        return table_name_to_expr, table_name_to_column_names_to_expr, required_backends

    async def execute_sql_returning_row_count(
        self,
        sql_query: str,
        computation_input_sources: "dict[str, DataFrameSource]",
        dialect: str,
    ) -> int:
        """Execute a DML query and return the number of rows affected.

        This method is for DML statements (INSERT/UPDATE/DELETE) that return a row count.
        DML queries are only supported against database tables, not file-based tables.
        No transformations are applied - the LLM generates queries with physical table/column names.

        Args:
            sql_query: The SQL DML query to execute
            computation_input_sources: Sources for backend resolution (from SDM)
            dialect: The resolved SQL dialect

        Returns:
            Number of rows affected by the statement

        Raises:
            PlatformError: If multiple backends required or execution fails
        """
        from agent_platform.core.errors.base import PlatformError

        # Determine which backend to use based on data sources
        # For DML, we only need backend resolution (no table/column mapping needed)
        required_backends = self._get_required_backends_from_sources(computation_input_sources)

        # DML operations require a single backend (no federation)
        if len(required_backends) != 1:
            raise PlatformError(
                message=f"Unable to execute DML query: multiple backends required: {required_backends}. "
                "Federation not supported for DML operations."
            )

        use_backend = required_backends.pop()

        # Get the connection
        con = await use_backend.create_connection(self._storage)

        # Execute DML directly - no transformations needed for database tables
        # The LLM generates queries with correct physical table/column names
        try:
            return await con.execute_dml(sql_query)
        except Exception as e:
            logger.error(
                "Error executing DML query",
                error=str(e),
                sql_query=sql_query,
                dialect=dialect,
            )
            raise PlatformError(message=f"Error executing DML query: {e}") from e
