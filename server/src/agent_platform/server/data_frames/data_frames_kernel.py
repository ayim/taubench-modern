import json
import typing

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any

    from agent_platform.core.data_frames.data_frames import DataFrameSource, PlatformDataFrame
    from agent_platform.core.thread.thread import Thread
    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.storage.base import BaseStorage

    from .data_node import DataNodeResult, SupportedIbisBackends


logger = get_logger(__name__)


def recursion_guard(func: typing.Callable) -> typing.Callable:
    """
    A decorator to prevent recursion.
    """

    def wrapper(self, data_frame: "PlatformDataFrame", *args, **kwargs):
        if data_frame.data_frame_id in self._computing_data_frames:
            from agent_platform.core.errors.base import PlatformError

            raise PlatformError(
                message=f"Recursion detected when computing data frame: {data_frame.data_frame_id}"
            )
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
        self._sub_dependencies: list[Dependencies] = []
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
        for sub_dependency in self._sub_dependencies:
            as_str = repr(sub_dependency)
            as_str = as_str.replace("\n", "\n  ")
            lst.append(as_str)
        return "\n".join(lst)

    def add_leaf_data_frame_dependency(self, name: str, data_frame: "PlatformDataFrame"):
        """
        Adds a "leaf" data frame dependency (i.e.: one which will load directly
        from a file or in-memory).
        """
        self._data_frames[name] = data_frame

    def add_leaf_data_frame_source_dependency(
        self, name: str, data_frame_source: "DataFrameSource"
    ):
        """
        Adds a data frame source dependency (i.e.: one which will load from a
        semantic data model).
        """
        self._data_frames_sources[name] = data_frame_source

    def add_sub_dependencies(self, sub_dependencies: "Dependencies"):
        """
        Add a full new dependency which has its own dependencies (this is
        expected to happen when a SQL references another SQL dataframe).
        """
        self._sub_dependencies.append(sub_dependencies)

    def _get_backend_from_df(self, df: "PlatformDataFrame") -> "SupportedIbisBackends | None":
        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.data_frames.data_node import DUCK_DB_BACKEND

        if df.input_id_type == "sql_computation":
            return None
        elif df.input_id_type in ("in_memory", "file"):
            return DUCK_DB_BACKEND
        else:
            raise PlatformError(message=f"Unsupported input_id_type: {df.input_id_type}")

    def _get_backend_from_df_source(
        self, df_source: "DataFrameSource"
    ) -> "SupportedIbisBackends|None":
        from agent_platform.core.data_frames.semantic_data_model_types import BaseTable
        from agent_platform.server.data_frames.data_node import (
            DUCK_DB_BACKEND,
            make_data_connection_backend,
        )

        if df_source.source_type == "semantic_data_model":
            base_table: BaseTable | None = typing.cast(BaseTable | None, df_source.base_table)
            if base_table is None:
                logger.info(
                    "Semantic data model base table is None in DataFrameSource",
                    df_source=df_source,
                )
                return None
            # Ok, we have a base table, let's see if it's a database or a file
            base_table_data_connection_id = base_table.get("data_connection_id")
            base_table_database = base_table.get("database")
            if base_table_data_connection_id is not None and base_table_database is not None:
                return make_data_connection_backend(
                    base_table_data_connection_id, base_table_database
                )
            elif base_table.get("file_reference") is not None:
                return DUCK_DB_BACKEND
            else:
                logger.info(
                    "It's not possible to find out the backend from the data frame source"
                    " (semantic_data_model is expected to have a base_table with a "
                    " data_connection_id and database or a file_reference)",
                    df_source=df_source,
                )
                return None

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

        for sub_dependencies in self._sub_dependencies:
            backends.update(sub_dependencies.get_required_backends_recursive())

        if not backends:
            # Default to duckdb if no backends are found (i.e.: "select 1" should work).
            backends.add(DUCK_DB_BACKEND)

        return backends

    async def resolve_graph(
        self, kernel: "DataFramesKernel", data_frame: "PlatformDataFrame"
    ) -> "DataNodeResult":
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
                import ibis

                con = ibis.duckdb.connect()
                return await self._resolve_sql_with_connection(kernel, data_frame, con)

            elif use_backend.backend == "data-connection":
                return await self._resolve_sql_with_data_connection_backend(
                    kernel, data_frame, use_backend
                )

            else:
                raise PlatformError(message=f"Unsupported required_backend: {use_backend}")

    def _iter_recursive_data_frames(self) -> "Iterator[PlatformDataFrame]":
        yield from self._data_frames.values()
        for sub_dependencies in self._sub_dependencies:
            yield from sub_dependencies._iter_recursive_data_frames()

    def _iter_recursive_data_frame_sources(self) -> "Iterator[DataFrameSource]":
        yield from self._data_frames_sources.values()
        for sub_dependencies in self._sub_dependencies:
            yield from sub_dependencies._iter_recursive_data_frame_sources()

    def _iter_recursive_sql_computation_data_frames(self) -> "Iterator[PlatformDataFrame]":
        for sub_dependencies in self._sub_dependencies:
            yield sub_dependencies._data_frame
            yield from sub_dependencies._iter_recursive_sql_computation_data_frames()

    async def _resolve_sql_with_data_connection_backend(
        self,
        kernel: "DataFramesKernel",
        data_frame: "PlatformDataFrame",
        use_backend: "SupportedIbisBackends",
    ) -> "DataNodeResult":
        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.kernel.data_connection_inspector import DataConnectionInspector

        data_connection_id = use_backend.data_connection_id
        database = use_backend.database
        if data_connection_id is None or database is None:
            raise PlatformError(
                message=f"Data connection id or database is None for backend: {use_backend}"
            )
        data_connection = await kernel._storage.get_data_connection(data_connection_id)
        con = await DataConnectionInspector.create_ibis_connection(data_connection)
        return await self._resolve_sql_with_connection(kernel, data_frame, con)

    async def _resolve_sql_with_connection(  # noqa: PLR0912, PLR0915, C901
        self,
        kernel: "DataFramesKernel",
        data_frame: "PlatformDataFrame",
        con: "Any",
    ) -> "DataNodeResult":
        import asyncio
        from collections.abc import Coroutine
        from typing import Any

        import sqlglot

        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.data_frames.data_node import (
            DataNodeFromIbisResult,
            DataNodeResult,
        )
        from agent_platform.server.data_frames.sql_manipulation import (
            build_ctes,
            update_table_names,
            update_with_clause,
        )

        # Collect in-memory and file data frames initially (those never have deps and
        # must be created in-memory for ibis to be able to use them).
        name_to_node: dict[str, DataNodeResult] = {}
        name_to_coro: dict[str, Coroutine[Any, Any, DataNodeResult]] = {}

        sql_query = data_frame.computation
        assert sql_query

        # These will become CTEs in the SQL query
        sql_computation_data_frames = [
            df for df in self._iter_recursive_sql_computation_data_frames()
        ]

        for df in self._iter_recursive_data_frames():
            # These need to be materialized as tables in duckdb
            assert df.input_id_type in ("in_memory", "file")
            name_to_coro[df.name] = kernel.resolve_data_frame(df)

        logical_table_name_to_actual_table_name: dict[str, str] = {}

        df_source: DataFrameSource
        for df_source in self._iter_recursive_data_frame_sources():
            if df_source.source_type == "semantic_data_model":
                if df_source.base_table is not None:
                    if df_source.base_table.get("file_reference") is not None:
                        assert df_source.logical_table_name is not None
                        name_to_coro[df_source.logical_table_name] = (
                            kernel._resolve_file_data_source(df_source)
                        )
                    elif df_source.base_table.get("data_connection_id") is not None:
                        assert df_source.logical_table_name is not None
                        base_table = df_source.base_table
                        if not base_table:
                            logger.critical(
                                "Base table is None for semantic data model", df_source=df_source
                            )
                            continue
                        actual_table_name = base_table.get("table")
                        if not actual_table_name:
                            logger.critical(
                                "Actual table name is None for semantic data model",
                                df_source=df_source,
                            )
                            continue
                        schema = base_table.get("schema")
                        if schema:
                            actual_table_name = f"{schema}.{actual_table_name}"
                        logical_table_name_to_actual_table_name[df_source.logical_table_name] = (
                            actual_table_name
                        )
                    else:
                        raise PlatformError(
                            message=f"Unsupported base table: {df_source.base_table}"
                        )

        results = await asyncio.gather(*name_to_coro.values())
        for variable_name, result in zip(name_to_coro.keys(), results, strict=True):
            name_to_node[variable_name] = result

        # Fill in what came from in-memory and file data frames
        # (we should be in duck db in this case, so, we can just create the
        # tables directly).
        for variable_name, node in name_to_node.items():
            assert con.name == "duckdb", (
                "Only duckdb is supported for materializing in-memory and file data frames"
            )
            con.create_table(variable_name, node.to_ibis())

        # Now, we need to go on to the computation (deps should be in order already).
        # We have to add preconditions as:
        # WITH df AS (
        #   {dep_sql_query}
        # ),
        # df2 AS (
        #   {dep_sql_query}
        # )
        name_to_cte_ast: dict[str, Any] = {}
        for df in sql_computation_data_frames:
            # Use sqlglot directly to parse and format the SQL for the target dialect
            assert df.computation is not None, "SQL computation data frame has no computation"
            expressions = sqlglot.parse(df.computation, dialect=df.sql_dialect)
            if len(expressions) != 1:
                raise PlatformError(
                    message=f"SQL query must be a single expression. Found: {len(expressions)} "
                    f"SQL query: {df.computation!r}"
                )

            # Now, create the cte with sqlglot
            cte_sql_ast = expressions[0]
            cte_sql_ast = update_table_names(cte_sql_ast, logical_table_name_to_actual_table_name)
            name_to_cte_ast[df.name] = cte_sql_ast

        ctes = build_ctes(name_to_cte_ast=name_to_cte_ast)
        main_sql_ast = sqlglot.parse_one(sql_query, dialect=data_frame.sql_dialect)
        main_sql_ast = update_table_names(main_sql_ast, logical_table_name_to_actual_table_name)
        main_sql_ast = update_with_clause(main_sql_ast, ctes)
        full_sql_query_str = main_sql_ast.sql(dialect=data_frame.sql_dialect, pretty=True)

        # Execute the SQL query using ibis
        try:
            result = con.sql(full_sql_query_str, dialect=data_frame.sql_dialect)

            df = DataNodeFromIbisResult(data_frame, result)
            return df

        except Exception as e:
            logger.error(
                "Error executing SQL computation",
                error=e,
                sql_query=sql_query,
                name_to_node_summary=str(name_to_node),
            )
            raise PlatformError(message=f"Error executing SQL query: {e!s}") from e


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
        self._semantic_data_models: list[BaseStorage.SemanticDataModelInfo] | None = None
        self._name_to_data_frame: dict[str, PlatformDataFrame] | None = None

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

    async def get_semantic_data_models(self) -> list["BaseStorage.SemanticDataModelInfo"]:
        if self._semantic_data_models is None:
            self._semantic_data_models = await self._storage.list_semantic_data_models(
                agent_id=await self.get_agent_id(), thread_id=self._tid
            )
        assert self._semantic_data_models is not None
        return self._semantic_data_models

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
            sql_ast = validate_sql_query(sql_query, data_frame.sql_dialect)
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
                    dependencies.add_sub_dependencies(sub_dependencies)

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

    async def _resolve_file_data_source(self, data_source: "DataFrameSource") -> "DataNodeResult":
        """
        A data frame source must be used to resolve contents from the semantic data model.
        """
        import datetime
        import uuid

        from agent_platform.core.data_frames.data_frames import PlatformDataFrame
        from agent_platform.core.data_frames.semantic_data_model_types import BaseTable
        from agent_platform.core.errors.base import PlatformError

        if data_source.source_type == "data_frame":
            raise RuntimeError("Must resolve as a data frame, not a data source")

        elif data_source.source_type == "semantic_data_model":
            base_table_info: BaseTable | None = typing.cast(
                BaseTable | None, data_source.base_table
            )
            if base_table_info is None:
                raise PlatformError(
                    message=f"Data source info is None for data source: {data_source}"
                )
            logical_table_name = data_source.logical_table_name
            if logical_table_name is None:
                raise PlatformError(
                    message=f"Logical table name is None for data source: {data_source}"
                )

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
                    name=logical_table_name,
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
                raise PlatformError(
                    message=f"file_reference is None for data source: {data_source}"
                )

        raise PlatformError(message=f"Unsupported source_type: {data_source.source_type}")

    async def resolve_data_frame(self, data_frame: "PlatformDataFrame") -> "DataNodeResult":
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode
        from agent_platform.server.data_frames.data_node import (
            DataNodeFromDataReaderSheet,
            DataNodeFromInMemoryDataFrame,
        )
        from agent_platform.server.data_frames.data_reader import (
            create_file_data_reader,
        )

        if data_frame.data_frame_id in self._resolved_data_frames:
            return self._resolved_data_frames[data_frame.data_frame_id]

        if data_frame.input_id_type == "file":
            if data_frame.file_id is None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.PRECONDITION_FAILED,
                    message=(
                        "Error in database: Data frame is marked with having input "
                        "type file, but it has no file_id!"
                    ),
                )
            data_reader = await create_file_data_reader(
                self._user,
                self._tid,
                self._storage,
                sheet_name=data_frame.sheet_name,
                file_id=data_frame.file_id,
                file_ref=data_frame.file_ref,
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

            data_node = DataNodeFromDataReaderSheet(data_frame, next(data_reader.iter_sheets()))
            self._resolved_data_frames[data_frame.data_frame_id] = data_node
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

            data_node = DataNodeFromInMemoryDataFrame(data_frame)
            self._resolved_data_frames[data_frame.data_frame_id] = data_node
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

            dependencies = await self._compute_data_frame_graph(
                data_frame, await self._get_name_to_data_frame()
            )

            data_node = await dependencies.resolve_graph(self, data_frame)
            self._resolved_data_frames[data_frame.data_frame_id] = data_node
            return data_node

        else:
            raise PlatformHTTPError(
                error_code=ErrorCode.PRECONDITION_FAILED,
                message=f"Unsupported input_id_type: {data_frame.input_id_type}",
            )
