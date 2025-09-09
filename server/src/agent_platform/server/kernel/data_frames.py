import typing
from typing import Annotated, Any

from structlog import get_logger

from agent_platform.core.kernel import DataFramesInterface
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)


class AgentServerDataFramesInterface(DataFramesInterface, UsesKernelMixin):
    """Handles interaction with data frames."""

    def __init__(self):
        super().__init__()
        self._name_to_data_frame: dict[str, PlatformDataFrame] = {}
        self._data_frame_tools: tuple[ToolDefinition, ...] = ()

    def is_enabled(self) -> bool:
        import os

        enable_data_frames = os.getenv("SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES") in ("1", "true")
        if not enable_data_frames:
            agent_settings = self.kernel.agent.extra.get("agent_settings", {})
            enable_data_frames = agent_settings.get("enable_data_frames", False)

        return enable_data_frames

    async def step_initialize(
        self, *, storage: "BaseStorage|None" = None, state: "DataFrameArchState"
    ):
        from typing import Literal

        from agent_platform.server.storage.option import StorageService

        previous_state: Literal["enabled", ""] = state.data_frames_tools_state

        try:
            storage = StorageService.get_instance() if storage is None else storage
            data_frames = tuple(
                await storage.list_data_frames(thread_id=self.kernel.thread.thread_id)
            )
        except Exception:
            logger.exception("Error getting data frames")
            data_frames = ()

        self._name_to_data_frame = {data_frame.name: data_frame for data_frame in data_frames}

        assert storage is not None, "Storage is required to create data frame tools"
        data_frame_tools = _DataFrameTools(
            self.kernel.user, self.kernel.thread.thread_id, self._name_to_data_frame, storage
        )
        if data_frames or previous_state == "enabled":
            if not previous_state:
                state.data_frames_tools_state = "enabled"

            self._data_frame_tools = (
                ToolDefinition.from_callable(
                    data_frame_tools.create_data_frame_from_file,
                    name="data_frames_create_from_file",
                ),
                ToolDefinition.from_callable(
                    data_frame_tools.delete_data_frame, name="data_frames_delete"
                ),
                ToolDefinition.from_callable(
                    data_frame_tools.data_frame_slice, name="data_frames_slice"
                ),
                ToolDefinition.from_callable(
                    data_frame_tools.create_data_frame_from_sql, name="data_frames_create_from_sql"
                ),
            )
        else:
            # Creating from a file should be always there (i.e.: the user should be able to
            # create a data frame from a file even if there are no data frames yet).
            self._data_frame_tools = (
                ToolDefinition.from_callable(
                    data_frame_tools.create_data_frame_from_file,
                    name="data_frames_create_from_file",
                ),
            )

    @property
    def data_frames_system_prompt(self) -> str:
        if not self.thread_has_data_frames:
            # i.e.: For now return empty (so that we don't change anything in the system prompt
            # if the user hasn't created a data frame).
            return ""

        return f"## Data Frames Summary:\n{self.data_frames_summary}"

    @property
    def data_frames_summary(self) -> str:
        import json

        if not self._name_to_data_frame:
            return "You have no data frames to work with."

        summary = [f"You have {len(self._name_to_data_frame)} data frames to work with. Details:\n"]
        data_frames_info = []
        for data_frame in self._name_to_data_frame.values():
            data_frames_info.append(self._data_frame_summary(data_frame))
        summary.append(json.dumps(data_frames_info, indent=1))
        return "\n".join(summary)

    def _data_frame_summary(self, data_frame: "PlatformDataFrame") -> dict[str, Any]:
        info: dict[str, Any] = {"name": data_frame.name}
        if data_frame.description:
            info["description"] = data_frame.description
        if data_frame.num_rows:
            info["nrows"] = data_frame.num_rows
        if data_frame.num_columns:
            info["ncols"] = data_frame.num_columns
        if data_frame.column_headers:
            info["column_names"] = data_frame.column_headers
        if data_frame.sample_rows:
            info["sample_data"] = data_frame.sample_rows
        return info

    @property
    def thread_has_data_frames(self) -> bool:
        return bool(self._name_to_data_frame)

    def get_data_frame_tools(
        self,
    ) -> tuple[ToolDefinition, ...]:
        return self._data_frame_tools

    async def _create_in_memory_data_frame(
        self, name: str, contents: dict[str, list], *, storage: "BaseStorage | None" = None
    ) -> "PlatformDataFrame":
        import datetime
        import io
        from uuid import uuid4

        import pyarrow.parquet

        from agent_platform.core.data_frames.data_frames import PlatformDataFrame
        from agent_platform.server.storage.option import StorageService

        columns = contents["columns"]
        rows = contents["rows"]

        # Convert rows and columns format to dictionary format for PyArrow
        # This allows PyArrow to automatically infer the schema
        col_data = list(zip(*rows, strict=True)) if rows else [[] for _ in columns]

        # Build the table
        pyarrow_df = pyarrow.Table.from_arrays(
            [pyarrow.array(col) for col in col_data], names=columns
        )

        stream = io.BytesIO()
        pyarrow.parquet.write_table(pyarrow_df, stream)

        sample_rows = rows[:10]

        data_frame = PlatformDataFrame(
            data_frame_id=str(uuid4()),
            name=name,
            user_id=self.kernel.thread.user_id,
            agent_id=self.kernel.thread.agent_id,
            thread_id=self.kernel.thread.thread_id,
            num_rows=pyarrow_df.shape[0],
            num_columns=pyarrow_df.shape[1],
            column_headers=list(pyarrow_df.schema.names),
            input_id_type="in_memory",
            created_at=datetime.datetime.now(datetime.UTC),
            parquet_contents=stream.getvalue(),
            computation_input_sources={},
            extra_data=PlatformDataFrame.build_extra_data(sample_rows=sample_rows),
        )

        storage = StorageService.get_instance() if storage is None else storage
        await storage.save_data_frame(data_frame)
        self._name_to_data_frame[name] = data_frame
        return data_frame

    async def auto_create_data_frame(self, tool_def: ToolDefinition, result_output: Any) -> Any:
        """Auto create a data frame from the result output.

        Args:
            tool_def: The tool definition that created the result output.
            result_output: The result output from the tool.

        Returns:
            The new result that the LLM will see.
        """
        if not self.is_enabled():
            return result_output

        from sema4ai.common.text import slugify

        try:
            if isinstance(result_output, dict):
                possible_table = result_output.get("result", result_output)
                found_in_result = True
                if not possible_table:
                    found_in_result = False
                    possible_table = result_output

                if isinstance(possible_table, dict):
                    if set(("columns", "rows")) == set(possible_table.keys()):
                        slugified_name = slugify(tool_def.name)
                        name = f"data_frame_{slugified_name}"

                        i = 1
                        while name in self._name_to_data_frame:
                            name = f"data_frame_{slugified_name}_{i:02d}"
                            i += 1
                        data_frame = await self._create_in_memory_data_frame(
                            name=name,
                            contents=possible_table,
                        )
                        data_frame_summary = self._data_frame_summary(data_frame)
                        msg = f"Data frame {name} created from {tool_def.name}.\nDetails: "
                        for key, value in data_frame_summary.items():
                            msg += f"{key}: {value}\n"

                        new_result = result_output.copy()
                        if found_in_result:
                            new_result["result"] = msg
                            return new_result
                        else:
                            return msg

            return result_output  # Nothing changed
        except Exception:
            logger.exception(
                f"Error auto creating data frame from {tool_def.name} with result output"
                f" {result_output}"
            )

            return result_output


class _DataFrameTools:
    """Tools for data frames."""

    def __init__(
        self,
        user: "AuthedUser",
        tid: str,
        name_to_data_frame: "dict[str, PlatformDataFrame]",
        storage: "BaseStorage",
    ):
        assert isinstance(name_to_data_frame, dict), (
            f"Expected a dict, got {type(name_to_data_frame)}"
        )
        self._user = user
        self._tid = tid
        self._name_to_data_frame = name_to_data_frame
        self._storage = storage

    def _create_data_frames_kernel(self) -> "DataFramesKernel":
        from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel

        return DataFramesKernel(self._storage, self._user, self._tid)

    async def create_data_frame_from_file(
        self,
        data_frame_name: Annotated[
            str,
            """The name of the data frame to create (IMPORTANT: It must be a valid variable name
            such as 'my_data_frame', only ascii letters, numbers and underscores are allowed
            and it cannot start with a number or be a python keyword.""",
        ],
        file_ref: Annotated[
            str, "The file reference to create the data frame from (usually the file name)."
        ],
        sheet_name: Annotated[str | None, "The name of the sheet to inspect."] = None,
        description: Annotated[str | None, "The description for the data frame."] = None,
        num_samples: Annotated[int, "The number of samples to return for each data frame."] = 0,
    ) -> dict[str, Any]:
        """Creates a data frame from a file."""
        from dataclasses import asdict

        from agent_platform.server.api.private_v2.threads_data_frames import (
            create_data_frame_from_file,
        )

        ret = await create_data_frame_from_file(
            user=self._user,
            tid=self._tid,
            storage=self._storage,
            file_ref=file_ref,
            name=data_frame_name,
            sheet_name=sheet_name,
            description=description,
            num_samples=num_samples,
        )
        ret_as_dict = asdict(ret)
        if "created_at" in ret_as_dict:
            ret_as_dict["created_at"] = ret_as_dict["created_at"].isoformat()
        return ret_as_dict

    async def delete_data_frame(
        self,
        data_frame_name: Annotated[str, "The name of the existing data frame to delete."],
    ) -> dict[str, Any]:
        """Deletes a data frame from this thread."""
        if data_frame_name not in self._name_to_data_frame:
            return {
                "error_code": "data_frame_not_found",
                "error": f"Data frame {data_frame_name!r} not found",
            }

        try:
            await self._storage.delete_data_frame_by_name(self._tid, data_frame_name)
            self._name_to_data_frame.pop(data_frame_name)
        except Exception as e:
            logger.exception(f"Error deleting data frame {data_frame_name} in thread {self._tid}")
            return {
                "error_code": "unable_to_delete_data_frame",
                "error": (
                    f"Unable to delete data frame {data_frame_name!r} in thread {self._tid}. "
                    f"Error: {e!r}"
                ),
            }

        return {"result": f"Data frame {data_frame_name!r} deleted"}

    async def data_frame_slice(
        self,
        data_frame_name: Annotated[str, "The name of the existing data frame to slice."],
        offset: Annotated[
            int, "From which row it should start to collect samples (starts at 0)"
        ] = 0,
        limit: Annotated[int, "The number of rows to sample (max 500)"] = 10,
        column_names: Annotated[list[str] | None, "The column names to include."] = None,
        order_by: Annotated[str | None, "The column name to order by."] = None,
    ) -> dict[str, Any]:
        """Returns the data frame data from a slice of a data frame."""
        from sema4ai.actions import Table

        from agent_platform.core.errors.base import PlatformHTTPError

        data_frame = self._name_to_data_frame.get(data_frame_name)
        if data_frame is None:
            return {
                "error_code": "data_frame_not_found",
                "error": f"Data frame {data_frame_name!r} not found",
            }

        if limit <= 0:
            return {
                "error_code": "invalid_limit",
                "error": "limit must be > 0",
            }

        max_limit = 500
        if limit > max_limit:
            return {
                "error_code": "invalid_limit",
                "error": f"limit must be <= {max_limit}",
            }

        try:
            data_frames_kernel = self._create_data_frames_kernel()
            resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)

            sliced_data = resolved_df.slice(
                offset=offset,
                limit=limit,
                column_names=column_names,
                output_format="table",
                order_by=order_by,
            )

            assert isinstance(sliced_data, Table), f"Expected a Table, got {type(sliced_data)}"
            return sliced_data.model_dump()
        except PlatformHTTPError as e:
            logger.exception(f"Error slicing data frame {data_frame_name} in thread {self._tid}")
            return e.to_log_context()
        except Exception as e:
            logger.exception(f"Error slicing data frame {data_frame_name} in thread {self._tid}")
            return {
                "error_code": "unable_to_sample_data_frame",
                "error": f"Unable to sample data frame. Error: {e!r}",
            }

    async def create_data_frame_from_sql(
        self,
        sql_query: Annotated[
            str,
            """
            A SQL query (using duckdb syntax) to execute against existing data frames.
            Any data frame can be referenced by its name in the SQL query.
            Some common SQL features:
                • SELECT statements with WHERE, ORDER BY, LIMIT, GROUP BY clauses
                • Aggregate functions like COUNT, SUM, AVG, MIN, MAX
                • String functions like CONCAT, UPPER, LOWER
                • Math functions and operators
                • JOIN operations (when using multiple data frames)
                • Common Table Expressions (CTEs)
            Examples:
                • 'SELECT * FROM my_data_frame WHERE age > 30'
                • 'SELECT country, COUNT(*) as count FROM my_data_frame GROUP BY country'
                • 'SELECT name, age FROM my_data_frame ORDER BY age DESC LIMIT 10'
                • 'SELECT UPPER(name) as name_upper FROM my_data_frame'
                • 'SELECT * FROM my_data_frame
                       JOIN another_data_frame ON my_data_frame.id = another_data_frame.id'
            """,
        ],
        new_data_frame_name: Annotated[
            str,
            """The name of the new data frame to create. IMPORTANT: It must be a valid variable name
            such as 'my_data_frame', only ascii letters, numbers and underscores are allowed
            and it cannot start with a number or be a python keyword.""",
        ],
        new_data_frame_description: Annotated[
            str | None,
            "The description of the new data frame to create.",
        ] = None,
        num_samples: Annotated[
            int,
            """The number of samples to return from the newly created data frame (number of rows
            to return). Default is 10 (max 500).
            """,
        ] = 10,
    ) -> dict[str, Any]:
        """Run a SQL query against the existing data frames and use its data to create a
        new data frame.

        A sample of the newly created data frame is returned (specified by num_samples).

        Use SQL using duckdb syntax. Existing data frames are available by their name in your query.
        DuckDB supports most common SQL operations including SELECT, WHERE, GROUP BY,
        ORDER BY, aggregate functions, and more.
        """
        import keyword

        from sema4ai.actions import Table

        from agent_platform.server.data_frames.data_frames_from_computation import (
            create_data_frame_from_sql_computation_api,
        )
        from sema4ai.common.text import slugify

        try:
            data_frames_kernel = self._create_data_frames_kernel()

            # If the LLM gives us a wrong name, try to auto-fix it (and in the return
            # we show the name that was actually used).
            if not new_data_frame_name.isidentifier() or keyword.iskeyword(new_data_frame_name):
                new_data_frame_name = slugify(new_data_frame_name).replace("-", "_")

            resolved_df, samples_table = await create_data_frame_from_sql_computation_api(
                data_frames_kernel=data_frames_kernel,
                storage=self._storage,
                new_data_frame_name=new_data_frame_name,
                sql_query=sql_query,
                dialect="duckdb",
                description=new_data_frame_description,
                num_samples=num_samples if num_samples > 0 else 0,
            )

            self._name_to_data_frame[new_data_frame_name] = resolved_df.platform_data_frame

            if num_samples <= 0:
                return {
                    "result": f"Data frame {new_data_frame_name} created from SQL query",
                }

            sliced_data = resolved_df.slice(
                offset=0,
                limit=num_samples,
                column_names=None,
                output_format="table",
            )

            assert isinstance(sliced_data, Table), f"Expected a Table, got {type(sliced_data)}"

            return {
                "result": f"Data frame {new_data_frame_name} created from SQL query",
                "sample_data": sliced_data.model_dump(),
            }
        except Exception as e:
            return {
                "error_code": "unable_to_create_data_frame",
                "error": f"Unable to create data frame from SQL query. Error: {e!r}",
            }
