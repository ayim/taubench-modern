import typing

from structlog.stdlib import get_logger

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.thread.thread import Thread
    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.storage.base import BaseStorage

    from .data_node import DataNodeResult

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

    def __init__(self):
        self._data_frames: list[PlatformDataFrame] = []

    def add_data_frame_dependency(self, data_frame: "PlatformDataFrame"):
        self._data_frames.append(data_frame)

    def iter_deps(self) -> "Iterator[PlatformDataFrame]":
        return iter(self._data_frames)


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

        # Dict of data frame id to resolved data frame.
        # This is used to avoid resolving the same data frame multiple times.
        self._resolved_data_frames: dict[str, DataNodeResult] = {}
        self._computing_data_frames: set[str] = set()

        self._data_frames: list[PlatformDataFrame] | None = None

    async def get_thread(self) -> "Thread":
        return await self._storage.get_thread(self._user.user_id, self._tid)

    async def list_data_frames(self) -> list["PlatformDataFrame"]:
        if self._data_frames is None:
            self._data_frames = await self._storage.list_data_frames(self._tid)
        return self._data_frames

    async def _get_name_to_data_frame(self) -> "dict[str, PlatformDataFrame]":
        data_frames = await self.list_data_frames()
        return {df.name: df for df in data_frames}

    @property
    def tid(self) -> str:
        return self._tid

    @property
    def user_id(self) -> str:
        return self._user.user_id

    def _extract_variable_names_required_from_sql_computation(
        self, sql_query: str, dialect: str
    ) -> "set[str]":
        import sqlglot

        from agent_platform.core.errors.base import PlatformError

        expressions = sqlglot.parse(sql_query, dialect=dialect)
        if len(expressions) != 1:
            raise PlatformError(
                message=f"SQL query must be a single expression. Found: {len(expressions)} "
                f"SQL query: {sql_query!r}"
            )
        expr = expressions[0]
        if expr is None or not hasattr(expr, "key"):
            raise PlatformError(message=f"SQL query is not a valid expression: {sql_query!r}")
        if expr.key != "select":
            raise PlatformError(message=f"SQL is not a SELECT statement: {sql_query}")
        tables = expr.find_all(sqlglot.expressions.Table)  # type: ignore

        required_variable_names = {t.name for t in tables}
        return required_variable_names

    async def _compute_data_frame_dependencies(
        self,
        data_frame: "PlatformDataFrame",
        name_to_data_frame: "dict[str, PlatformDataFrame]",
        dependencies: "Dependencies",
    ) -> None:
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
            required_variable_names = self._extract_variable_names_required_from_sql_computation(
                sql_query, dialect=data_frame.sql_dialect
            )

            # These have to be done last as they may depend on other data frames.
            do_last = []

            for name in required_variable_names:
                df = name_to_data_frame.get(name)
                if df is None:
                    raise PlatformError(message=f"Data frame with name {name} not found")

                if df.input_id_type == "sql_computation":
                    do_last.append(df)
                else:
                    if df.input_id_type not in ("in_memory", "file"):
                        raise PlatformError(
                            message=f"Unsupported input_id_type: {df.input_id_type} for "
                            f"data frame: {df.name}, id: {df.data_frame_id}"
                        )

                    dependencies.add_data_frame_dependency(df)

            for df in do_last:
                await self._compute_data_frame_dependencies(df, name_to_data_frame, dependencies)
                # The order is important, first add dependencies and only to finish add the
                # one that depends on them.
                dependencies.add_data_frame_dependency(df)

        elif data_frame.input_id_type in ("in_memory", "file"):
            pass  # no deps
        else:
            raise PlatformError(
                message=f"Unsupported input_id_type: {data_frame.input_id_type} for data frame: "
                f"{data_frame.name}, id: {data_frame.data_frame_id}"
            )

    @recursion_guard
    async def _resolve_sql_computation_data_frame(  # noqa: PLR0912, C901
        self, data_frame: "PlatformDataFrame"
    ) -> "DataNodeResult":
        import asyncio
        from collections.abc import Coroutine
        from typing import Any

        import ibis

        from agent_platform.core.errors.base import PlatformError
        from agent_platform.server.data_frames.data_node import (
            DataNodeFromIbisResult,
            DataNodeResult,
            SupportedIbisBackends,
        )

        if data_frame.data_frame_id in self._resolved_data_frames:
            return self._resolved_data_frames[data_frame.data_frame_id]

        sql_query = data_frame.computation
        if sql_query is None:
            raise PlatformError(
                message="Data frame has no computation SQL query defined, which "
                f"is needed to compute it (input_id_type: {data_frame.input_id_type}). "
                f"Data frame name: {data_frame.name}, id: "
                f"{data_frame.data_frame_id}"
            )

        dependencies = Dependencies()
        await self._compute_data_frame_dependencies(
            data_frame, await self._get_name_to_data_frame(), dependencies
        )

        # Collect in-memory and file data frames initially (those never have deps and
        # must be created in-memory for ibis to be able to use them).
        name_to_node: dict[str, DataNodeResult] = {}
        name_to_coro: dict[str, Coroutine[Any, Any, DataNodeResult]] = {}

        do_later = []
        for df in dependencies.iter_deps():
            if df.input_id_type == "sql_computation":
                do_later.append(df)
            else:
                assert df.input_id_type in ("in_memory", "file")
                name_to_coro[df.name] = self.resolve_data_frame(df)
        results = await asyncio.gather(*name_to_coro.values())
        for variable_name, result in zip(name_to_coro.keys(), results, strict=True):
            name_to_node[variable_name] = result

        # Note: the sql_computation data frames are always for 'any' backend,
        # so, it's ok they weren't considered here (when we have actual db connections
        # those have to be considered too).
        required_backends: set[SupportedIbisBackends] = set(
            node.required_backend for node in name_to_node.values()
        )
        # any means it accepts anything (so, a pure computation), no need to consider it.
        required_backends.discard("any")
        if len(required_backends) == 1:
            use_backend = required_backends.pop()
        else:
            # If more than one backend is required (or none if we had no inputs),
            # we need to use duckdb.
            use_backend = "duckdb"

        if use_backend == "duckdb":
            con = ibis.duckdb.connect()
        else:
            # When we go for databases we may have other backends...
            raise PlatformError(message=f"Unsupported required_backend: {use_backend}")

        # Fill in what came from in-memory and file data frames
        # (we should be in duck db in this case, so, we can just create the
        # tables directly).
        for variable_name, node in name_to_node.items():
            con.create_table(variable_name, node.to_ibis())

        # Now, we need to go on to the computation (deps should be in order already).
        # We have to add preconditions as:
        # WITH df AS (
        #   {con.compile(df)}
        # ),
        # df2 AS (
        #   {con.compile(df2)}
        # )
        full_sql_query = []
        for df in do_later:
            # Note: ibis uses sqlglot internally, so, it should format the sql
            # appropriately for the database dialect (regardless of the input sql dialect).
            precondition_sql = con.compile(con.sql(df.computation, dialect=df.sql_dialect))
            if not full_sql_query:
                full_sql_query.append(f"WITH {df.name} AS (")
            else:
                full_sql_query.append(f",\n{df.name} AS (")
            full_sql_query.append(precondition_sql)
            full_sql_query.append(")")

        full_sql_query.append(sql_query)
        full_sql_query_str = "\n".join(full_sql_query)

        # Execute the SQL query using ibis
        try:
            result = con.sql(full_sql_query_str, dialect=data_frame.sql_dialect)

            df = DataNodeFromIbisResult(data_frame, result)
            self._resolved_data_frames[data_frame.data_frame_id] = df
            return df

        except Exception as e:
            logger.error(
                "Error executing SQL computation",
                error=e,
                sql_query=sql_query,
                name_to_node_summary=str(name_to_node),
            )
            raise PlatformError(message=f"Error executing SQL query: {e!s}") from e

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
                # file_ref=data_frame.file_ref, # TODO: Add file_ref to the platform data frame
            )
            if data_reader.has_multiple_sheets():
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        "More than one sheet loaded when trying to load a single data "
                        f"frame (sheet_name passed: {data_frame.sheet_name}, file_id: "
                        f"{data_frame.file_id}, thread_id: {self._tid}, data_frame.name: "
                        f"{data_frame.name}, data_frame_id: {data_frame.data_frame_id})"
                    ),
                )

            df = DataNodeFromDataReaderSheet(data_frame, next(data_reader.iter_sheets()))
            self._resolved_data_frames[data_frame.data_frame_id] = df
            return df

        elif data_frame.input_id_type == "in_memory":
            if data_frame.parquet_contents is None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.PRECONDITION_FAILED,
                    message=(
                        "Error in database: Data frame is marked with having input "
                        "type in_memory, but it has no parquet_contents!"
                    ),
                )

            df = DataNodeFromInMemoryDataFrame(data_frame)
            self._resolved_data_frames[data_frame.data_frame_id] = df
            return df

        elif data_frame.input_id_type == "sql_computation":
            return await self._resolve_sql_computation_data_frame(data_frame)

        else:
            raise PlatformHTTPError(
                error_code=ErrorCode.PRECONDITION_FAILED,
                message=f"Unsupported input_id_type: {data_frame.input_id_type}",
            )
