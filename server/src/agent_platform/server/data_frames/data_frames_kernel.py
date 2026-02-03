# ruff: noqa: PLR0912, PLR0915, C901, E501
import json
import typing

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any

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
        from agent_platform.core.data_frames.semantic_data_model_types import BaseTable
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

    def _iter_recursive_data_frame_sources(self) -> "Iterator[DataFrameSource]":
        yield from self._data_frames_sources.values()
        for sub_dependencies in self._sub_dependencies.values():
            yield from sub_dependencies._iter_recursive_data_frame_sources()

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

    def _build_full_sql_query(
        self,
        data_frame: "PlatformDataFrame",
        sql_computation_data_frames: "list[PlatformDataFrame]",
        logical_table_name_to_actual_table_name: dict[str, str],
        table_name_to_column_names_to_expr: dict[str, dict[str, str]],
    ) -> str:
        import sqlglot

        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode
        from agent_platform.server.data_frames.sql_manipulation import (
            build_ctes,
            update_column_references,
            update_column_table_qualifiers,
            update_table_names,
            update_with_clause,
        )

        sql_query = data_frame.computation
        assert sql_query is not None

        # Collect all data frame names (both regular DFs and those that will become CTEs)
        # These should be excluded from SDM column mapping rewrites
        data_frame_names: set[str] = set()
        for df in self._iter_recursive_data_frames():
            data_frame_names.add(df.name)
        for df in sql_computation_data_frames:
            data_frame_names.add(df.name)

        name_to_cte_ast: dict[str, Any] = {}
        target_dialect = data_frame.sql_dialect  # The dialect we're targeting for the final SQL

        for df in sql_computation_data_frames:
            # Use sqlglot directly to parse and format the SQL for the target dialect
            if df.computation is None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.PRECONDITION_FAILED,
                    message=f"SQL computation data frame has no computation: {df.name}",
                )
            expressions = sqlglot.parse(df.computation, dialect=df.sql_dialect)
            if len(expressions) != 1:
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        f"SQL query must be a single expression. Found: {len(expressions)} "
                        f"SQL query: {df.computation!r}"
                    ),
                )
            if expressions[0] is None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=f"SQL query is not a valid expression. Found: {expressions[0]} "
                    f"SQL query: {df.computation!r}",
                )

            cte_sql_ast = expressions[0]

            # Transpile to target dialect if there's a mismatch
            # This prevents sqlglot from generating invalid SQL during final emission
            if df.sql_dialect != target_dialect:
                logger.info(
                    "Transpiling nested data frame SQL to target dialect",
                    df_name=df.name,
                    source_dialect=df.sql_dialect,
                    target_dialect=target_dialect,
                )
                try:
                    # Transpile by emitting with target dialect, then re-parsing
                    transpiled_sql = cte_sql_ast.sql(dialect=target_dialect)
                    cte_sql_ast = sqlglot.parse_one(transpiled_sql, dialect=target_dialect)
                except Exception as e:
                    logger.error(
                        "Failed to transpile nested data frame SQL to target dialect",
                        df_name=df.name,
                        source_dialect=df.sql_dialect,
                        target_dialect=target_dialect,
                        error=str(e),
                    )
                    raise PlatformHTTPError(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=(
                            f"Cannot transpile data frame '{df.name}' from dialect "
                            f"'{df.sql_dialect}' to '{target_dialect}'. "
                            f"Error: {e}"
                        ),
                    ) from e

            # Now apply transformations with consistent target dialect
            cte_sql_ast = update_table_names(cte_sql_ast, logical_table_name_to_actual_table_name)
            cte_sql_ast = update_column_table_qualifiers(cte_sql_ast, logical_table_name_to_actual_table_name)
            cte_sql_ast = update_column_references(
                cte_sql_ast,
                table_name_to_column_names_to_expr,
                logical_table_name_to_actual_table_name,
                data_frame_names,
            )
            name_to_cte_ast[df.name] = cte_sql_ast

        ctes = build_ctes(name_to_cte_ast=name_to_cte_ast)
        main_sql_ast = sqlglot.parse_one(sql_query, dialect=data_frame.sql_dialect)
        main_sql_ast = update_table_names(main_sql_ast, logical_table_name_to_actual_table_name)
        main_sql_ast = update_column_table_qualifiers(main_sql_ast, logical_table_name_to_actual_table_name)
        main_sql_ast = update_column_references(
            main_sql_ast,
            table_name_to_column_names_to_expr,
            logical_table_name_to_actual_table_name,
            data_frame_names,
        )
        main_sql_ast = update_with_clause(main_sql_ast, ctes)
        full_sql_query_str = main_sql_ast.sql(dialect=data_frame.sql_dialect, pretty=True)
        return full_sql_query_str

    async def _resolve_sql_with_connection(
        self,
        kernel: "DataFramesKernel",
        data_frame: "PlatformDataFrame",
        con: "AsyncIbisConnection",
    ) -> "DataNodeResult":
        import asyncio
        from collections.abc import Coroutine
        from typing import Any

        from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode
        from agent_platform.server.data_frames.data_node import (
            DataNodeFromIbisResult,
            DataNodeResult,
        )

        # Collect in-memory and file data frames initially (those never have deps and
        # must be created in-memory for ibis to be able to use them).
        name_to_node: dict[str, DataNodeResult] = {}
        name_to_coro: dict[str, Coroutine[Any, Any, DataNodeResult]] = {}

        sql_query = data_frame.computation
        assert sql_query

        # These will become CTEs in the SQL query
        sql_computation_data_frames = [df for df in self._iter_recursive_sql_computation_data_frames()]

        for df in self._iter_recursive_data_frames():
            # These need to be materialized as tables in duckdb
            assert df.input_id_type in ("in_memory", "file")
            name_to_coro[df.name] = kernel.resolve_data_frame(df)

        logical_table_name_to_actual_table_name: dict[str, str] = {}
        # Track column mappings per table: {table_name: {logical_col: physical_expr}}
        table_name_to_column_names_to_expr: dict[str, dict[str, str]] = {}

        df_source: DataFrameSource
        for df_source in self._iter_recursive_data_frame_sources():
            if df_source.source_type == "semantic_data_model":
                if df_source.base_table is not None:
                    # Store column mappings if available
                    if df_source.logical_column_names_to_expr and df_source.logical_table_name:
                        table_name_to_column_names_to_expr[df_source.logical_table_name] = (
                            df_source.logical_column_names_to_expr
                        )
                        logger.info(
                            "Collected column mappings for SDM table",
                            table_name=df_source.logical_table_name,
                            num_mappings=len(df_source.logical_column_names_to_expr),
                            mappings=df_source.logical_column_names_to_expr,
                        )
                    elif df_source.logical_table_name:
                        logger.warning(
                            "No column mappings available for SDM table",
                            table_name=df_source.logical_table_name,
                        )

                    if df_source.base_table.get("file_reference") is not None:
                        assert df_source.logical_table_name is not None
                        name_to_coro[df_source.logical_table_name] = kernel._resolve_file_data_source(df_source)
                    elif df_source.base_table.get("data_connection_id") is not None:
                        assert df_source.logical_table_name is not None
                        base_table = df_source.base_table
                        if not base_table:
                            logger.critical(f"Base table is None for semantic data model. df_source: {df_source}")
                            continue
                        actual_table_name = base_table.get("table")
                        if not actual_table_name:
                            logger.critical(
                                f"Actual table name is None for semantic data model. df_source: {df_source}"
                            )
                            continue
                        schema = base_table.get("schema")
                        if schema:
                            actual_table_name = f"{schema}.{actual_table_name}"
                        logical_table_name_to_actual_table_name[df_source.logical_table_name] = actual_table_name
                    else:
                        assert df_source.logical_table_name is not None
                        base_table = df_source.base_table
                        if not base_table:
                            logger.critical(f"Base table is None for semantic data model. df_source: {df_source}")
                            continue
                        data_frame_name = base_table.get("table")
                        if not data_frame_name:
                            logger.critical(f"'table' name is None for semantic data model. df_source: {df_source}")
                            continue
                        # Get the data frame by name from the thread
                        name_to_data_frame = await kernel._get_name_to_data_frame()
                        if data_frame_name not in name_to_data_frame:
                            raise PlatformHTTPError(
                                error_code=ErrorCode.NOT_FOUND,
                                message=f"Data frame '{data_frame_name}' referenced in semantic data model "
                                f"not found in thread {kernel._tid}",
                            )
                        df = name_to_data_frame[data_frame_name]
                        # Resolve the data frame and map logical table name to actual data frame name
                        name_to_coro[data_frame_name] = kernel.resolve_data_frame(df)
                        # Map logical table name to actual data frame name for SQL queries
                        logical_table_name_to_actual_table_name[df_source.logical_table_name] = data_frame_name

        if name_to_coro:
            if con.name != "duckdb":
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        f"Only duckdb is supported for materializing in-memory, file and "
                        f"computed data frames. Current backend: {con.name}"
                    ),
                )

        results = await asyncio.gather(*name_to_coro.values())
        for variable_name, result in zip(name_to_coro.keys(), results, strict=True):
            name_to_node[variable_name] = result

        # Fill in what came from in-memory and file data frames
        # (we should be in duck db in this case, so, we can just create the
        # tables directly).

        for variable_name, node in name_to_node.items():
            await con.create_table(variable_name, node.to_ibis())

        # Now, we need to go on to the computation (deps should be in order already).
        # We have to add preconditions as:
        # WITH df AS (
        #   {dep_sql_query}
        # ),
        # df2 AS (
        #   {dep_sql_query}
        # )
        full_sql_query_str = self._build_full_sql_query(
            data_frame,
            sql_computation_data_frames,
            logical_table_name_to_actual_table_name,
            table_name_to_column_names_to_expr,
        )

        # To get the one referencing the logical table names, build it again but with empty mappings.
        full_sql_query_logical_str = self._build_full_sql_query(
            data_frame,
            sql_computation_data_frames,
            logical_table_name_to_actual_table_name={},
            table_name_to_column_names_to_expr={},
        )

        try:
            result = await con.sql(full_sql_query_str, dialect=data_frame.sql_dialect)

            df = DataNodeFromIbisResult(
                data_frame,
                result,
                full_sql_query_str=full_sql_query_str,
                full_sql_query_logical_str=full_sql_query_logical_str,
            )
            return df
        except Exception as e:
            error_msg = str(e)

            # Make errors more actionable by adding context
            enhanced_error = error_msg

            # Column not found errors - guide LLM to check SDM
            column_not_found = "column" in error_msg.lower() and (
                "does not exist" in error_msg.lower() or "not found" in error_msg.lower()
            )
            if column_not_found:
                enhanced_error += (
                    "\n\nAction: Check the column names in the semantic data model. "
                    "The column name might be different than expected. "
                    "Review the available columns and their data types in the table definition."
                )

            # Set-returning function errors - guide to LATERAL JOIN (PostgreSQL-specific)
            elif (
                "set-returning function" in error_msg.lower()
                and "aggregate" in error_msg.lower()
                and data_frame.sql_dialect == "postgres"
            ):
                enhanced_error += (
                    "\n\nAction: Use LATERAL JOIN to unnest the array before aggregation. "
                    "Pattern: FROM table t, LATERAL (SELECT AGG(field) "
                    "FROM json_array_elements(...) x) AS agg"
                )

            logger.error(
                "Error executing SQL computation",
                error=error_msg,
                data_frame_name=data_frame.name,
                sql_query=sql_query,
                full_sql_query_str=full_sql_query_str,
                full_sql_query_logical_str=full_sql_query_logical_str,
                logical_table_name_to_actual_table_name=logical_table_name_to_actual_table_name,
                enhanced_error=enhanced_error,
            )

            raise PlatformError(message=f"Error executing SQL query: {enhanced_error}") from e


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
            base_table_info: BaseTable | None = typing.cast(BaseTable | None, data_source.base_table)
            if base_table_info is None:
                raise PlatformError(message=f"Data source info is None for data source: {data_source}")
            logical_table_name = data_source.logical_table_name
            if logical_table_name is None:
                raise PlatformError(message=f"Logical table name is None for data source: {data_source}")

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

    async def execute_sql_returning_row_count(
        self,
        sql_query: str,
        computation_input_sources: "dict[str, DataFrameSource]",
        dialect: str,
    ) -> int:
        """Execute a SQL query and return the number of rows affected.

        This method is for SQL statements that return a row count rather than
        a result set (e.g., INSERT/UPDATE/DELETE without RETURNING, CREATE TABLE, etc.).
        It uses raw_sql() to execute the query directly.

        Args:
            sql_query: The SQL query to execute
            computation_input_sources: Sources for table resolution (from SDM)
            dialect: The resolved SQL dialect

        Returns:
            Number of rows affected by the statement
        """
        import sqlglot

        from agent_platform.core.data_frames.data_frames import DataFrameSource
        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.data_frames.data_node import (
            DUCK_DB_BACKEND,
            SupportedIbisBackends,
            make_data_connection_backend,
        )
        from agent_platform.server.data_frames.sql_manipulation import (
            update_column_references,
            update_column_table_qualifiers,
            update_table_names,
        )

        # Build table name mappings and column mappings from computation_input_sources
        logical_table_name_to_actual_table_name: dict[str, str] = {}
        table_name_to_column_names_to_expr: dict[str, dict[str, str]] = {}
        required_backends: set[SupportedIbisBackends] = set()

        df_source: DataFrameSource
        sdm_sources = [
            s
            for s in computation_input_sources.values()
            if s.source_type == "semantic_data_model" and s.base_table is not None
        ]
        for df_source in sdm_sources:
            assert df_source.base_table is not None  # filtered above

            # Store column mappings if available
            if df_source.logical_column_names_to_expr and df_source.logical_table_name:
                table_name_to_column_names_to_expr[df_source.logical_table_name] = (
                    df_source.logical_column_names_to_expr
                )

            if df_source.base_table.get("data_connection_id") is not None:
                assert df_source.logical_table_name is not None
                base_table = df_source.base_table
                actual_table_name = base_table.get("table")
                if actual_table_name:
                    schema = base_table.get("schema")
                    if schema:
                        actual_table_name = f"{schema}.{actual_table_name}"
                    logical_table_name_to_actual_table_name[df_source.logical_table_name] = actual_table_name

                data_connection_id = base_table.get("data_connection_id")
                if data_connection_id:
                    required_backends.add(make_data_connection_backend(data_connection_id))
            else:
                # File reference or data frame reference - use duckdb
                required_backends.add(DUCK_DB_BACKEND)

        # Default to duckdb if no backends found
        if not required_backends:
            required_backends.add(DUCK_DB_BACKEND)

        # For row count operations, we only support single backend
        if len(required_backends) != 1:
            raise PlatformError(
                message=f"Unable to execute SQL: multiple backends required: {required_backends}. "
                "Federation not supported for row count operations."
            )

        use_backend = required_backends.pop()

        # Get the connection
        con = await use_backend.create_connection(self._storage)

        # Transform the SQL query with table name and column mappings
        # Parse and transform SQL
        sql_ast = sqlglot.parse_one(sql_query, dialect=dialect)
        sql_ast = update_table_names(sql_ast, logical_table_name_to_actual_table_name)
        sql_ast = update_column_table_qualifiers(sql_ast, logical_table_name_to_actual_table_name)
        sql_ast = update_column_references(
            sql_ast,
            table_name_to_column_names_to_expr,
            logical_table_name_to_actual_table_name,
            data_frame_names=set(),  # No data frames to exclude
        )
        full_sql_query_str = sql_ast.sql(dialect=dialect, pretty=True)

        # Execute DML and return row count
        try:
            return await con.execute_dml(full_sql_query_str)
        except Exception as e:
            logger.error(
                "Error executing SQL for row count",
                error=str(e),
                sql_query=sql_query,
                full_sql_query_str=full_sql_query_str,
            )
            raise PlatformError(message=f"Error executing SQL query: {e}") from e
