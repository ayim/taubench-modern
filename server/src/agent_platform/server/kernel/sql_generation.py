import typing
from typing import Annotated, Any, ClassVar, Literal

from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import (
    SemanticDataModel,
    VerifiedQuery,
)
from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.kernel_interfaces.sql_generation import SQLGenerationInterface
from agent_platform.core.thread.content.sql_generation import SQLGenerationContent
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.server.data_frames.semantic_data_model_collector import (
    SemanticDataModelAndReferences,
    SemanticDataModelCollector,
)
from agent_platform.server.kernel.sql import LegacySqlStrategy
from agent_platform.server.storage.option import StorageService

logger = get_logger(__name__)

CREATE_DF_FROM_LOGICAL_SQL_TOOL_NAME = "create_data_frame_from_logical_sql"
DESCRIBE_TABLE_TOOL_NAME = "describe_table"
PEEK_TABLE_TOOL_NAME = "peek_table"
FINALIZE_SQL_GENERATION_TOOL_NAME = "finalize_sql_generation"

ENABLE_SQL_GENERATION_SETTING_NAME = "enable_sql_generation"

# Maximum number of rows allowed for peek_table
_PEEK_TABLE_MAX_ROWS = 50
_PEEK_TABLE_DEFAULT_ROWS = 10


class AgentServerSQLGenerationInterface(SQLGenerationInterface, UsesKernelMixin):
    def __init__(self):
        self._storage = StorageService.get_instance()
        # TODO: Currently we are mimicing legacy in a subagent, but we should have our own tools
        # and guidance here eventually and can remove use of data frames interface.
        self._sql_generation_strategy: LegacySqlStrategy | None = None
        self._semantic_data_models: list[SemanticDataModelAndReferences] = []
        # verified_query_name -> VerifiedQuery
        self._verified_queries: dict[str, VerifiedQuery] = {}

        # Storage is needed to get data connections
        self._data_connection_id_to_engine: dict[str, str] = {}

    async def step_initialize(self) -> None:
        from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState
        from agent_platform.server.kernel.data_frames import _DataFrameTools

        self._sql_generation_strategy = LegacySqlStrategy(
            data_frame_tools=_DataFrameTools(
                user=self.kernel.user,
                tid=self.kernel.thread.thread_id,
                storage=self._storage,
                name_to_data_frame={},
            ),
        )

        # Initialize the SQL generation strategy
        self._sql_generation_strategy = LegacySqlStrategy(
            data_frame_tools=_DataFrameTools(
                user=self.kernel.user,
                tid=self.kernel.thread.thread_id,
                storage=self._storage,
                name_to_data_frame={},
            )
        )

        class _DataFrameArchState(DataFrameArchState):
            data_frames_tools_state: Literal["enabled", ""] = "enabled"
            empty_file_cache_key_to_matching_info: ClassVar[dict[str, dict]] = {}

        # This is a mock state for now since we don't really need it except to set to enabled,
        # but we should have our own tools and guidance here eventually and can remove use of
        # data frames interface.
        self._state = _DataFrameArchState()

        # TODO this is duplicating logic from AgentServerDataFramesInterface
        # We need to tease apart DataFrames from SDM later.
        collector = SemanticDataModelCollector(
            agent_id=self.kernel.thread.agent_id,
            thread_id=self.kernel.thread.thread_id,
            user=self.kernel.user,
            state=self._state,
        )
        self._semantic_data_models = await collector.collect_semantic_data_models(self._storage)
        all_data_connection_ids = set()

        # Collect verified queries from semantic data models
        self._verified_queries = {}
        for semantic_data_model_and_refs in self._semantic_data_models:
            all_data_connection_ids.update(
                semantic_data_model_and_refs.references.data_connection_ids
            )

            # Extract verified queries from this semantic data model
            semantic_data_model = semantic_data_model_and_refs.semantic_data_model_info[
                "semantic_data_model"
            ]
            verified_queries = semantic_data_model.get("verified_queries")
            if verified_queries:
                for verified_query in verified_queries:
                    if isinstance(verified_query, dict):
                        query_name = verified_query.get("name")
                        sql_query = verified_query.get("sql")
                        if query_name and sql_query:
                            self._verified_queries[query_name] = typing.cast(
                                VerifiedQuery, verified_query
                            )

        if all_data_connection_ids:
            data_connections = await self._storage.get_data_connections(
                list(all_data_connection_ids)
            )
            for data_connection in data_connections:
                self._data_connection_id_to_engine[data_connection.id] = data_connection.engine

    def is_enabled(self) -> bool:
        agent_settings = self.kernel.agent.agent_settings()

        if ENABLE_SQL_GENERATION_SETTING_NAME in agent_settings:
            return bool(agent_settings[ENABLE_SQL_GENERATION_SETTING_NAME])

        return False

    # TODO copied from data_frames.py
    def _semantic_data_models_with_engines(self) -> list[tuple[SemanticDataModel, str]]:
        from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

        models_and_engines: list[tuple[SemanticDataModel, str]] = []
        if not self._semantic_data_models:
            return models_and_engines

        for semantic_data_model_and_refs in self._semantic_data_models:
            try:
                model: SemanticDataModel = semantic_data_model_and_refs.semantic_data_model_info[
                    "semantic_data_model"
                ]
                new_model: SemanticDataModel = typing.cast(
                    SemanticDataModel, {x: y for x, y in model.items() if y}
                )

                tables = new_model.get("tables", [])
                if not tables:
                    continue  # No tables, so skip
                tables = [c.copy() for c in tables]
                for table in tables:
                    table.pop("base_table", None)
                    # Don't show empty fields
                    for k, v in list(table.items()):
                        if not v:
                            table.pop(k)
                new_model["tables"] = tables

                engine = self._infer_engine_for_semantic_model(semantic_data_model_and_refs)
                models_and_engines.append((new_model, engine))
            except Exception:
                logger.exception(
                    "Error creating semantic data model summary from semantic data model info",
                    semantic_data_model_and_refs=semantic_data_model_and_refs,
                )
                continue

        return models_and_engines

    # TODO copied from data_frames.py
    def _infer_engine_for_semantic_model(
        self,
        semantic_data_model_and_refs: SemanticDataModelAndReferences,
    ) -> str:
        data_connection_ids = semantic_data_model_and_refs.references.data_connection_ids
        if data_connection_ids:
            engines = {
                self._data_connection_id_to_engine.get(data_connection_id)
                for data_connection_id in data_connection_ids
            }
            engines.discard(None)
            if len(engines) == 1:
                engine = engines.pop()
                if engine:
                    return engine
        # Fallback to duckdb if we have multiple engines
        return "duckdb"

    @property
    def sql_generation_system_prompt(self) -> str:
        from textwrap import dedent

        if self.is_enabled():
            if self._sql_generation_strategy is None:
                raise ValueError("SQL generation strategy is not initialized")

            models_and_engines = self._semantic_data_models_with_engines()
            return dedent(f"""
            ## Semantic Data Models (tables available to be used in the \
            `{CREATE_DF_FROM_LOGICAL_SQL_TOOL_NAME}` tool):
            {self._sql_generation_strategy.get_context_additions(models_and_engines)}
            """)

        return ""

    def get_sql_generation_tools(self) -> tuple[ToolDefinition, ...]:
        if self.is_enabled():
            return (
                ToolDefinition.from_callable(self.describe_table, name=DESCRIBE_TABLE_TOOL_NAME),
                ToolDefinition.from_callable(self.peek_table, name=PEEK_TABLE_TOOL_NAME),
                ToolDefinition.from_callable(
                    self.create_data_frame_from_logical_sql,
                    name=CREATE_DF_FROM_LOGICAL_SQL_TOOL_NAME,
                ),
                ToolDefinition.from_callable(
                    self.finalize_sql_generation,
                    name=FINALIZE_SQL_GENERATION_TOOL_NAME,
                ),
            )
        return ()

    async def create_data_frame_from_logical_sql(
        self,
        logical_sql: Annotated[
            str,
            """
            A SQL "SELECT" query to execute against existing "logical" tables in your semantic
            data model.
            Any "logical" table can be referenced by its name in the SQL query.

            IMPORTANT: Always use explicit column names instead of SELECT *. Using SELECT *
            will return physical column names which may differ from the logical names in your
            semantic data model. Use `describe_table` or `peek_table` to discover logical
            column names before writing queries.

            Supported SQL features:
                • SELECT statements with WHERE, ORDER BY, LIMIT, GROUP BY clauses
                • Aggregate functions like COUNT, SUM, AVG, MIN, MAX
                • String functions like CONCAT, UPPER, LOWER
                • Math functions and operators
                • JOIN operations (when combining multiple tables)
                • Common Table Expressions (CTEs)

            Examples:
                • 'SELECT name, age FROM my_logical_table WHERE age > 30'
                • 'SELECT country, COUNT(*) as count FROM my_logical_table GROUP BY country'
                • 'SELECT name, age FROM my_logical_table ORDER BY age DESC LIMIT 10'
                • 'SELECT UPPER(name) as name_upper FROM my_logical_table'
                • 'SELECT t1.id, t1.name, t2.order_date
                       FROM customers t1
                       JOIN orders t2 ON t1.id = t2.customer_id'

            Note: The SQL dialect syntax used for the query should be inferred from the
                  SQL dialect specified in your semantic data model being used in
                  the query.
            """,
        ],
        new_data_frame_name: Annotated[
            str,
            """The name of the new data frame to create. IMPORTANT: It must be a valid variable name
            such as 'my_data_frame', only ascii letters, numbers and underscores are allowed
            and it cannot start with a number or be a python keyword. IMPORTANT: The name must be
            unique in the thread (updating an existing data frame is not possible).""",
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
        """Run a SQL query against the existing "logical" tables in your semantic
        data model and use its data to create a new data frame.

        A sample of the newly created data frame is returned (specified by num_samples).

        Use SQL using syntax matching the SQL dialect of your semantic data model being queried.
        Existing "logical" tables in your semantic data model are available by their name in
        your query.
        """
        if self._sql_generation_strategy is None:
            raise ValueError("SQL generation strategy is not initialized")

        # TODO: We need to consider how we handle actual errors and convert them to
        # "failed_approaches" so those can be returned and/or stored in the SDM.

        return await self._sql_generation_strategy.create_data_frame_from_sql(
            sql_query=logical_sql,
            new_data_frame_name=new_data_frame_name,
            new_data_frame_description=new_data_frame_description,
            num_samples=num_samples,
        )

    async def describe_table(
        self,
        table_name: Annotated[str, "The logical table name from the semantic data model"],
    ) -> dict[str, Any]:
        """Get schema information for a table including columns, types, and sample values.

        Returns structured schema information for a specific logical table from the
        semantic data model.
        """
        import typing

        from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

        # Search for the table in semantic data models
        for sdm_and_refs in self._semantic_data_models:
            semantic_data_model: SemanticDataModel = sdm_and_refs.semantic_data_model_info[
                "semantic_data_model"
            ]
            tables = semantic_data_model.get("tables", [])

            for table in tables:
                if table.get("name") == table_name:
                    # Cast TypedDicts to dict[str, Any] to satisfy type checker
                    return self._format_table_description(
                        typing.cast(dict[str, Any], table),
                        typing.cast(dict[str, Any], semantic_data_model),
                    )

        # Table not found
        available_tables = self._get_available_table_names()
        return {
            "error": f"Table '{table_name}' not found in semantic data model",
            "available_tables": available_tables,
        }

    def _get_available_table_names(self) -> list[str]:
        """Get list of all available table names from semantic data models."""
        from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

        table_names: list[str] = []
        for sdm_and_refs in self._semantic_data_models:
            semantic_data_model: SemanticDataModel = sdm_and_refs.semantic_data_model_info[
                "semantic_data_model"
            ]
            for table in semantic_data_model.get("tables", []):
                name = table.get("name")
                if name:
                    table_names.append(name)
        return table_names

    def _format_table_description(
        self,
        table: dict[str, Any],
        semantic_data_model: dict[str, Any],
    ) -> dict[str, Any]:
        """Format a logical table into a structured description."""
        result: dict[str, Any] = {
            "table_name": table.get("name"),
            "model_name": semantic_data_model.get("name"),
        }

        if table.get("description"):
            result["description"] = table["description"]

        # Collect columns from all column categories
        columns: list[dict[str, Any]] = []

        # Process dimensions
        for dim in table.get("dimensions", []) or []:
            columns.append(self._format_column(dim, "dimension"))

        # Process time_dimensions
        for td in table.get("time_dimensions", []) or []:
            columns.append(self._format_column(td, "time_dimension"))

        # Process facts
        for fact in table.get("facts", []) or []:
            columns.append(self._format_column(fact, "fact"))

        # Process metrics
        for metric in table.get("metrics", []) or []:
            columns.append(self._format_column(metric, "metric"))

        result["columns"] = columns
        result["column_count"] = len(columns)

        return result

    def _format_column(
        self,
        column: dict[str, Any],
        column_type: str,
    ) -> dict[str, Any]:
        """Format a single column definition."""
        formatted: dict[str, Any] = {
            "name": column.get("name"),
            "type": column_type,
            "data_type": column.get("data_type"),
        }

        if column.get("description"):
            formatted["description"] = column["description"]

        if column.get("sample_values"):
            formatted["sample_values"] = column["sample_values"]

        return formatted

    def _get_logical_column_names(self, table_name: str) -> list[str] | None:
        """Get all logical column names for a table from the SDM definition.

        Returns None if the table is not found.
        """
        import typing

        from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

        for sdm_and_refs in self._semantic_data_models:
            semantic_data_model: SemanticDataModel = sdm_and_refs.semantic_data_model_info[
                "semantic_data_model"
            ]
            for table in semantic_data_model.get("tables", []):
                if table.get("name") == table_name:
                    return self._extract_column_names_from_table(typing.cast(dict[str, Any], table))
        return None

    def _extract_column_names_from_table(self, table: dict[str, Any]) -> list[str]:
        """Extract all logical column names from a table definition."""
        from agent_platform.core.data_frames.semantic_data_model_types import CATEGORIES

        column_names: list[str] = []
        for category in CATEGORIES:
            for col in table.get(category, []) or []:
                if name := col.get("name"):
                    column_names.append(name.lower())
        return column_names

    async def peek_table(
        self,
        table_name: Annotated[str, "The logical table name to sample"],
        num_rows: Annotated[int, "Number of rows to return (default: 10, max: 50)"] = 10,
    ) -> dict[str, Any]:
        """Quick sample of table data. Creates a data frame with the sampled rows.

        This is a convenience tool for quickly exploring table contents. It automatically
        generates a data frame name and limits the number of rows to prevent requesting
        entire tables.
        """
        # Validate num_rows
        if num_rows <= 0:
            num_rows = _PEEK_TABLE_DEFAULT_ROWS
        elif num_rows > _PEEK_TABLE_MAX_ROWS:
            num_rows = _PEEK_TABLE_MAX_ROWS

        # Get logical column names (also verifies the table exists)
        column_names = self._get_logical_column_names(table_name)
        if column_names is None:
            available_tables = self._get_available_table_names()
            return {
                "error": f"Table '{table_name}' not found in semantic data model",
                "available_tables": available_tables,
            }

        # Generate auto data frame name
        data_frame_name = f"peek_{table_name}"

        # Build the SQL query using explicit logical column names
        columns_sql = ", ".join(column_names)
        sql_query = f"SELECT {columns_sql} FROM {table_name} LIMIT {num_rows}"

        # Call create_data_frame_from_logical_sql internally
        return await self.create_data_frame_from_logical_sql(
            logical_sql=sql_query,
            new_data_frame_name=data_frame_name,
            new_data_frame_description=f"Sample of {num_rows} rows from {table_name}",
            num_samples=num_rows,
        )

    async def finalize_sql_generation(
        self,
        data_frame_name: Annotated[
            str | None,
            "The name of the data frame that was created with the final SQL query. "
            "Required when SQL generation was successful.",
        ] = None,
        assumptions_used: Annotated[
            str | None,
            "Any assumptions made when generating the SQL query (e.g., interpreting ambiguous "
            "terms, choosing between similar columns).",
        ] = None,
        message_to_parent: Annotated[
            str | None,
            "A message to the parent agent when you need more information to proceed. "
            "Use this when you need clarification (e.g., 'Did you mean sales by region or by "
            "product?') or the request is ambiguous.",
        ] = None,
        error_message: Annotated[
            str | None,
            "An error message explaining why SQL generation completely failed. "
            "Use this when you cannot generate SQL and have given up (e.g., 'The semantic data "
            "model does not contain any tables related to the requested data.').",
        ] = None,
    ) -> dict[str, str]:
        """Finalize the SQL generation process and add results to the thread.

        This is a terminal tool that should be called once you have one of:
        1. Successfully generated SQL - provide the data_frame_name of the created data frame
        2. Need more information - provide message_to_parent explaining what you need
        3. Complete failure - provide error_message explaining why you cannot generate SQL

        For successful generation:
            - data_frame_name: The name of the data frame created with
              create_data_frame_from_logical_sql
            - assumptions_used: Any assumptions made during generation (optional)

        For needing more information (recoverable):
            - message_to_parent: Explain what clarification you need

        For complete failure (unrecoverable):
            - error_message: Explain why SQL generation failed and cannot proceed

        The results are added to the thread as file called "output.json".
        """
        from agent_platform.core.thread.content.sql_generation import SQLGenerationStatus

        content: SQLGenerationContent

        # FAILED case - complete failure, cannot generate SQL
        if error_message:
            content = SQLGenerationContent(
                status=SQLGenerationStatus.FAILED,
                error_message=error_message,
            )
        # NEEDS_INFO case - need clarification, might succeed with more info
        elif message_to_parent:
            content = SQLGenerationContent(
                status=SQLGenerationStatus.NEEDS_INFO,
                message_to_parent=message_to_parent,
            )
        # SUCCESS case - look up the data frame and extract SQL queries
        else:
            if not data_frame_name:
                raise ValueError(
                    "data_frame_name is required when not providing "
                    "message_to_parent or error_message"
                )

            # Get the data frame from storage
            data_frame = await self._storage.get_data_frame(
                self.kernel.thread.thread_id,
                data_frame_name=data_frame_name,
            )

            # The logical SQL is stored in the computation field
            logical_sql_query = data_frame.computation
            if not logical_sql_query:
                raise ValueError(f"Data frame '{data_frame_name}' does not have a SQL computation")

            content = SQLGenerationContent(
                status=SQLGenerationStatus.SUCCESS,
                sql_query=logical_sql_query,
                assumptions_used=assumptions_used,
            )

        # Attach the content as a JSON file to the thread so the parent agent can read it
        await self._upload_json_to_thread(content, filename="output.json")

        # Return a simple result for the tool
        return {
            "status": content.status.value,
            "message": content.as_text_content(),
        }

    async def _upload_json_to_thread(
        self,
        content: SQLGenerationContent,
        filename: str,
    ) -> None:
        """Upload JSON content as a file to the current thread.

        Args:
            content: The SQL generation content to serialize and upload
            filename: The name of the file to create (e.g., "output.json")
        """
        from io import BytesIO

        from fastapi import UploadFile
        from starlette.datastructures import Headers

        from agent_platform.core.payloads import UploadFilePayload
        from agent_platform.server.file_manager.option import FileManagerService

        # Marshal content to JSON
        json_bytes = content.model_dump_json().encode("utf-8")

        # Create in-memory file
        with BytesIO(json_bytes) as file_buffer:
            file_buffer.seek(0)

            # Wrap in UploadFile
            upload_file = UploadFile(
                filename=filename,
                file=file_buffer,
                headers=Headers({"content-type": "application/json"}),
            )

            # Get file manager and upload to thread
            file_manager = FileManagerService.get_instance(storage=self._storage)
            upload_payload = UploadFilePayload(file=upload_file)

            await file_manager.upload(
                files=[upload_payload],
                owner=self.kernel.thread,
                user_id=self.kernel.user.user_id,
            )
