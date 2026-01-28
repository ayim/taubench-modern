# ruff: noqa: E501
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated, Any

import structlog

from agent_platform.core.actions.action_utils import InternalToolResponse
from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.thread.content.sql_generation import SQLGenerationDetails
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.server.file_manager.option import FileManagerService
from agent_platform.server.kernel.data_frames import DF_CREATE_FROM_SQL_TOOL_NAME

if TYPE_CHECKING:
    from agent_platform.core.data_frames.semantic_data_model_validation import References
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.thread import Thread
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelCollector,
    )
    from agent_platform.server.file_manager.base import BaseFileManager
    from agent_platform.server.kernel.data_frames import _DataFrameTools
    from agent_platform.server.storage import BaseStorage


logger = structlog.get_logger(__name__)


class SqlGenerationStrategy(ABC):
    """Strategy for how SQL generation capability is provided to agents.

    Two approaches:
    1. Context-based (Legacy): Give current agent context/instructions, it generates SQL
    2. Tool-based (Agentic): Provide a tool that delegates to a specialized SQL agent
    """

    def __init__(self, data_frame_tools: "_DataFrameTools"):
        """Initialize the strategy with data frame tools.

        Args:
            data_frame_tools: The data frame tools instance containing all necessary dependencies
        """
        self._data_frame_tools = data_frame_tools

    @abstractmethod
    def get_context_additions(
        self,
        semantic_models_and_engines: list[tuple[SemanticDataModel, str]],
    ) -> str:
        """Get context to add to the agent's system prompt.

        Args:
            semantic_models_and_engines: Available semantic data models with their SQL engines

        Returns:
            Context string to add to system prompt
        """

    @abstractmethod
    def get_tools(self) -> tuple[ToolDefinition, ...]:
        """Get the tools provided by this strategy.

        Returns:
            Tuple of tool definitions for this strategy
        """


class LegacySqlStrategy(SqlGenerationStrategy):
    """Legacy: Give current agent SQL context, agent generates SQL directly.

    Provides detailed structural information and extensive SQL generation guidance
    including database-specific syntax rules. The current agent is responsible for
    generating SQL based on these instructions.
    """

    def get_context_additions(
        self,
        semantic_models_and_engines: list[tuple[SemanticDataModel, str]],
    ) -> str:
        """Provide SQL instructions and SDM summary to the current agent."""
        if not semantic_models_and_engines:
            return ""

        from agent_platform.server.kernel.semantic_data_model import (
            summarize_data_models,
        )

        parts = []

        # Add SQL generation instructions (HOW to write SQL)
        sql_instructions = _get_sql_generation_instructions(semantic_models_and_engines)
        parts.append(sql_instructions)

        # Add semantic data models summary (WHAT data is available)
        sdm_summary = summarize_data_models(semantic_models_and_engines)
        if sdm_summary:
            parts.append(sdm_summary)

        return "\n".join(parts)

    def get_tools(self) -> tuple[ToolDefinition, ...]:
        """Legacy mode provides create_data_frame_from_sql tool."""
        from agent_platform.server.kernel.data_frames import DF_CREATE_FROM_SQL_TOOL_NAME

        return (
            ToolDefinition.from_callable(
                self.create_data_frame_from_sql,
                name=DF_CREATE_FROM_SQL_TOOL_NAME,
            ),
        )

    async def create_data_frame_from_sql(
        self,
        sql_query: Annotated[
            str,
            """
            A SQL "SELECT" query to execute against existing data frames
            or "logical" tables in semantic data models.
            Any data frame or "logical" table can be referenced by its name in the SQL query.
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

            Note: The SQL dialect syntax used for the query should be inferred from the
                  SQL dialect specified in the semantic data model or data frame being used in
                  the query (if multiple engines are found, duckdb will be used for
                  queries across different engines, so, if a single engine is being used,
                  the SQL query syntax should be compatible with that specific engine, if more than
                  one engine is being used, duckdb syntax should be used for the query).
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
        semantic_data_model_name: Annotated[
            str | None,
            """The semantic data model name to use for executing the SQL query.
            If provided, only tables from this semantic data model will be used.
            When set, source resolution will skip data frames and other semantic data models.
            """,
        ] = None,
    ) -> dict[str, Any]:
        """Run a SQL query against the existing data frames or "logical" tables in semantic
        data models and use its data to create a new data frame.

        A sample of the newly created data frame is returned (specified by num_samples).

        Use SQL using syntax matching the SQL dialect of the semantic data model or data frame being queried.
        Existing data frames and "logical" tables in semantic data models are available by their name in your query.

        IMPORTANT RETRY BEHAVIOR:
        - If this tool returns status='needs_retry', read the error message carefully
        - The message contains specific guidance on what went wrong and how to fix it
        - Modify your SQL based on the feedback provided in the message
        - Call this tool again with the corrected SQL
        - After 5 failed attempts with different SQL variations, explain the issue to the user
        - Do NOT keep retrying the same SQL - each retry should incorporate the feedback from previous attempts

        If the query is not valid, a structured response will be returned with guidance so it can be corrected and retried.
        """
        assert self._data_frame_tools._create_data_frame_from_sql_impl is not None, (
            "create_df_from_sql_impl is required for SQL operations"
        )
        return await self._data_frame_tools._create_data_frame_from_sql_impl(
            sql_query=sql_query,
            new_data_frame_name=new_data_frame_name,
            new_data_frame_description=new_data_frame_description,
            num_samples=num_samples,
            semantic_data_model_name=semantic_data_model_name,
        )


def _get_sql_generation_instructions(
    models_and_engines: list[tuple[SemanticDataModel, str]],
) -> str:
    """Generate instructions for writing SQL against these models.

    Combines join guidance and database-specific syntax rules.
    """
    from textwrap import dedent

    if not models_and_engines:
        return ""

    instructions_parts = []

    # Add join guidance for non-Snowflake databases
    has_non_snowflake = any(engine and engine.lower() != "snowflake" for _, engine in models_and_engines)
    if has_non_snowflake:
        instructions_parts.append(
            dedent("""
            **SQL SYNTAX RULES:**
            - Reference tables by their logical name only (e.g., `FROM my_table`). Do NOT prefix with the model name.
            - Always qualify column names with their table (e.g., `my_table.column_name`), especially in CTEs and JOINs.
            """)
        )

    # Add database-specific guidance for each model
    for model, engine in models_and_engines:
        if engine == "snowflake":
            snowflake_guidance = _get_snowflake_variant_guidance(model)
            if snowflake_guidance:
                # Add prominent banner to make it unmissable
                instructions_parts.append("\n" + "=" * 80)
                instructions_parts.append("🚨 CRITICAL: SNOWFLAKE VARIANT/OBJECT/ARRAY COLUMN SYNTAX 🚨")
                instructions_parts.append("=" * 80)
                instructions_parts.append(snowflake_guidance)
                instructions_parts.append("=" * 80 + "\n")
        elif engine == "postgres":
            postgres_guidance = _get_postgres_json_guidance(model)
            if postgres_guidance:
                instructions_parts.append(postgres_guidance)
        elif engine == "mysql":
            mysql_guidance = _get_mysql_json_guidance(model)
            if mysql_guidance:
                instructions_parts.append(mysql_guidance)

    return "\n".join(instructions_parts)


def _get_postgres_json_guidance(model: SemanticDataModel) -> str:
    """Generate PostgreSQL-specific JSON/JSONB column guidance for a semantic data model.

    Scans the model for JSON and JSONB columns and returns targeted guidance
    on which functions to use and how to handle aggregations with LATERAL joins.

    Args:
        model: The semantic data model to scan for JSON columns

    Returns:
        A formatted guidance string if JSON columns are found, empty string otherwise
    """
    json_columns = []
    jsonb_columns = []
    tables = model.tables or []

    # Scan for JSON/JSONB columns in the semantic data model
    if tables:
        for table in tables:
            if not isinstance(table, dict):
                continue
            table_name = table.get("name", "")

            # Check all column categories
            for category in ["dimensions", "facts", "metrics", "time_dimensions"]:
                columns = table.get(category, [])
                if isinstance(columns, list):
                    for col in columns:
                        if isinstance(col, dict):
                            data_type = col.get("data_type", "").lower()
                            col_name = col.get("name", "")
                            if data_type == "json" and col_name:
                                json_columns.append(f"{table_name}.{col_name}")
                            elif data_type == "jsonb" and col_name:
                                jsonb_columns.append(f"{table_name}.{col_name}")

    # Generate guidance if JSON columns are detected
    if not json_columns and not jsonb_columns:
        return ""

    guidance_parts = ["\n  PostgreSQL JSON Column Rules:"]

    if json_columns:
        cols = ", ".join(json_columns)
        guidance_parts.append(
            f"• Type 'json' columns ({cols}): Use json_array_elements(), NOT jsonb_*\n"
            f"  Aggregation pattern: LATERAL (SELECT SUM((x->>'field')::numeric) FROM json_array_elements(col->'array') x)"
        )

    if jsonb_columns:
        cols = ", ".join(jsonb_columns)
        guidance_parts.append(
            f"• Type 'jsonb' columns ({cols}): Use jsonb_array_elements(), NOT json_*\n"
            f"  Aggregation pattern: LATERAL (SELECT SUM((x->>'field')::numeric) FROM jsonb_array_elements(col->'array') x)"
        )

    return "\n".join(guidance_parts)


def _get_snowflake_variant_guidance(model: SemanticDataModel) -> str:
    """Generate Snowflake-specific VARIANT/ARRAY/OBJECT column guidance for a semantic data model.

    Scans the model for these special Snowflake types and returns targeted guidance
    on how to query them properly.

    Args:
        model: The semantic data model to scan for Snowflake-specific columns

    Returns:
        A formatted guidance string if special columns are found, empty string otherwise
    """
    variant_columns = []
    array_columns = []
    object_columns = []
    tables = model.tables or []

    # Scan for Snowflake-specific column types in the semantic data model
    if tables:
        for table in tables:
            if not isinstance(table, dict):
                continue
            table_name = table.get("name", "")

            # Check all column categories
            for category in ["dimensions", "facts", "metrics", "time_dimensions"]:
                columns = table.get(category, [])
                if isinstance(columns, list) and columns:
                    for col in columns:
                        if isinstance(col, dict):
                            data_type = col.get("data_type", "").upper()
                            col_name = col.get("name", "")
                            if "VARIANT" in data_type and col_name:
                                variant_columns.append(f"{table_name}.{col_name}")
                            elif "ARRAY" in data_type and col_name:
                                array_columns.append(f"{table_name}.{col_name}")
                            elif "OBJECT" in data_type and col_name:
                                object_columns.append(f"{table_name}.{col_name}")

    # Generate guidance if Snowflake-specific columns are detected
    if not variant_columns and not array_columns and not object_columns:
        return ""

    all_special_cols = variant_columns + array_columns + object_columns
    guidance_parts = [
        "\n⚠️  SYNTAX REQUIREMENT: BRACKET NOTATION ONLY ⚠️",
        f"For columns: {', '.join(all_special_cols)}",
        "NEVER use colon notation (col:field) - it will cause 'Invalid expression' errors",
        "ALWAYS use bracket notation: col['field']\n",
    ]

    if variant_columns:
        cols = ", ".join(variant_columns)
        guidance_parts.append(
            f"• VARIANT columns ({cols}):\n"
            f"  - Syntax: col['field'] NOT col:field\n"
            f"  - Extract string: col['field']::TEXT or CAST(col['field'] AS TEXT)\n"
            f"  - Nested: col['field']['subfield']\n"
            f"  - Array element: col['field'][0]\n"
            f"  - Filter: WHERE col['brand']::TEXT = 'value'\n"
            f"  - WRONG: WHERE {cols}:brand = 'value'\n"
            f"  - CORRECT: WHERE {cols}['brand']::TEXT = 'value'"
        )

    if array_columns:
        cols = ", ".join(array_columns)
        guidance_parts.append(
            f"• ARRAY columns ({cols}):\n"
            f"  - Check if contains value: ARRAY_CONTAINS('value'::VARIANT, col)\n"
            f"  - Get array size: ARRAY_SIZE(col)\n"
            f"  - Access element by index: col[0] for first element (0-indexed)\n"
            f"  - Iterate/expand array: Use FLATTEN(col) in a lateral join or subquery"
        )

    if object_columns:
        cols = ", ".join(object_columns)
        guidance_parts.append(
            f"• OBJECT columns ({cols}):\n"
            f"  - Syntax: col['field'] NOT col:field\n"
            f"  - Extract string: col['field']::TEXT or CAST(col['field'] AS TEXT)\n"
            f"  - Nested: col['field']['subfield']\n"
            f"  - Filter: WHERE col['city']::TEXT = 'value'\n"
            f"  - WRONG: WHERE {cols}:city = 'value'\n"
            f"  - CORRECT: WHERE {cols}['city']::TEXT = 'value'"
        )

    return "\n".join(guidance_parts)


def _get_mysql_json_guidance(model: SemanticDataModel) -> str:
    """Generate MySQL-specific JSON column guidance for a semantic data model.

    Scans the model for JSON columns and returns targeted guidance on MySQL JSON
    syntax, operators, and functions.

    Args:
        model: The semantic data model to scan for JSON columns

    Returns:
        A formatted guidance string if JSON columns are found, empty string otherwise
    """
    json_columns = []
    tables = model.tables or []

    # Scan for JSON columns in the semantic data model
    if tables:
        for table in tables:
            if not isinstance(table, dict):
                continue
            table_name = table.get("name", "")

            # Check all column categories
            for category in ["dimensions", "facts", "metrics", "time_dimensions"]:
                columns = table.get(category, [])
                if isinstance(columns, list):
                    for col in columns:
                        if isinstance(col, dict):
                            data_type = col.get("data_type", "").lower()
                            col_name = col.get("name", "")
                            if data_type == "json" and col_name:
                                json_columns.append(f"{table_name}.{col_name}")

    # Generate guidance if JSON columns are detected
    if not json_columns:
        return ""

    cols = ", ".join(json_columns)
    guidance_parts = [
        "\n  MySQL JSON Column Rules:",
        f"• JSON columns ({cols}):",
        "  - Path syntax: ALWAYS use '$.path' (dollar sign required) for JSON_EXTRACT and paths",
        "  - Extract as JSON: col->'$.field' or JSON_EXTRACT(col, '$.field')",
        "  - Extract as string: col->>'$.field' or JSON_UNQUOTE(JSON_EXTRACT(col, '$.field'))",
        "  - Nested paths: col->'$.field.subfield' or col->'$.field.subfield[0]'",
        "  - Array elements: col->'$.array[0]' for first element (0-indexed)",
        "  - Filter: WHERE col->>'$.brand' = 'value' or WHERE JSON_EXTRACT(col, '$.brand') = '\"value\"'",
        "  - Check contains: JSON_CONTAINS(col, '\"value\"', '$.path')",
        "  - Search in JSON: JSON_SEARCH(col, 'one', 'searchtext', NULL, '$.path')",
        "",
        "  ⚠️ CRITICAL: Aggregating JSON arrays (SUM/COUNT/AVG):",
        "  - JSON_TABLE requires JSON type input - use JSON_EXTRACT (NOT JSON_UNQUOTE) or reference column directly",
        "  - WRONG: JSON_UNQUOTE(JSON_EXTRACT(col, '$.array')) then JSON_TABLE(result, ...) - converts to string!",
        "  - CORRECT: JSON_TABLE(col, '$.array[*]' ...) or JSON_TABLE(JSON_EXTRACT(col, '$.array'), '$[*]' ...)",
        "  - JSON_TABLE MUST be in FROM clause with CROSS JOIN - NEVER in SELECT",
        "  - Pattern: FROM base_table CROSS JOIN JSON_TABLE(base_table.json_col, '$.array[*]' COLUMNS (...)) AS alias",
        "  - Example:",
        "      SELECT base.id, SUM(items.amount) AS total",
        "        FROM my_table AS base",
        "        CROSS JOIN JSON_TABLE(base.json_col, '$.line_items[*]' COLUMNS (amount DECIMAL(10,2) PATH '$.amount')) AS items",
        "      GROUP BY base.id;",
        "",
        f"  - WRONG: WHERE {cols}:brand = 'value' (colon syntax doesn't work in MySQL)",
        f"  - CORRECT: WHERE {cols}->>'$.brand' = 'value' or JSON_EXTRACT({cols}, '$.brand') = '\"value\"'",
    ]

    return "\n".join(guidance_parts)


class AgenticSqlStrategy(SqlGenerationStrategy):
    """Agentic: Delegate SQL generation to specialized agent via tool.

    Provides minimal context (no SQL syntax rules) and exposes a generate_sql tool
    that delegates to a specialized SQL-generating agent. The specialized agent is
    responsible for understanding SQL syntax and generating queries.
    """

    def get_context_additions(
        self,
        semantic_models_and_engines: list[tuple[SemanticDataModel, str]],
    ) -> str:
        """Provide minimal context - just data availability, no SQL instructions."""
        if not semantic_models_and_engines:
            return ""

        from agent_platform.server.kernel.data_frames import DF_GENERATE_SQL_TOOL_NAME
        from agent_platform.server.kernel.semantic_data_model import summarize_data_models

        # Only provide WHAT data is available, not HOW to write SQL.
        # The specialized SQL agent will handle the HOW.
        # Include coaching as to how to use generate_sql in conjunction with create_data_frame_from_sql.
        return f"""
{summarize_data_models(semantic_models_and_engines)}

**Choose Semantic Data Model for Query**
When interacting with a Semantic Data Model, you need to determine the intent of the user's
request. From this intent, you should analyze the available Semantic Data Models and choose
the Semantic Data Model which is most relevant to the request. You should determine the best
Semantic Data Model that contains tables that are most relevant to the request.

Once you have identified the best Semantic Data Model, you should use the {DF_GENERATE_SQL_TOOL_NAME}
tool to generate a SQL query. You should never generate SQL queries directly, always use the tool
to generate a query. If the tool indicates success, you should immediately run the {DF_CREATE_FROM_SQL_TOOL_NAME}
tool to execute that query. If the tool indicates needs_info, you should use the included information
in the response to clarify intent with the user for clarification.
After you receive clarification, run generate_sql again with a more specific query intent.
If the tool indicates failure, you should inform the user of the failure, along with the reason for that failure.
"""

    def get_tools(self) -> tuple[ToolDefinition, ...]:
        """Agentic mode provides both generate_sql and create_data_frame_from_sql tools."""
        from agent_platform.server.kernel.data_frames import (
            DF_CREATE_FROM_SQL_TOOL_NAME,
            DF_GENERATE_SQL_TOOL_NAME,
        )

        return (
            ToolDefinition.from_callable(
                self.generate_sql,
                name=DF_GENERATE_SQL_TOOL_NAME,
            ),
            ToolDefinition.from_callable(
                self.create_data_frame_from_sql,
                name=DF_CREATE_FROM_SQL_TOOL_NAME,
            ),
        )

    async def create_data_frame_from_sql(
        self,
        sql_query: Annotated[
            str,
            """
            A SQL query to execute against existing data frames
            or tables in semantic data models. You should only provide
            a query as returned by the generate_sql tool.
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
        semantic_data_model_name: Annotated[
            str | None,
            """The semantic data model name to use for executing the SQL query.
            You should only provide the semantic data model name that was passed
            to the generate_sql tool.
            """,
        ] = None,
    ) -> dict[str, Any]:
        """Run a SQL query against the existing data frames or "logical" tables in semantic
        data models and use its data to create a new data frame.

        A sample of the newly created data frame is returned (specified by num_samples).
        """
        from time import perf_counter

        assert self._data_frame_tools._create_data_frame_from_sql_impl is not None, (
            "create_df_from_sql_impl is required for SQL operations"
        )

        # Start timing for query execution metrics
        start_time = perf_counter()

        # Get kernel for metrics (may be None if thread_state not initialized or doesn't have kernel)
        kernel = self._data_frame_tools._thread_state.kernel if self._data_frame_tools._thread_state else None

        result = await self._data_frame_tools._create_data_frame_from_sql_impl(
            sql_query=sql_query,
            new_data_frame_name=new_data_frame_name,
            new_data_frame_description=new_data_frame_description,
            num_samples=num_samples,
            semantic_data_model_name=semantic_data_model_name,
        )

        # Record query execution metrics
        if kernel is not None:
            duration = perf_counter() - start_time
            kernel.ctx.increment_counter("sdm.queries.executed.total")
            # For metrics related to duration, only record agent + run ID.
            # Thread ID does not make sense for duration metrics.
            kernel.ctx.record_metric(
                "sdm.query.execution.duration_seconds",
                duration,
                labels={
                    "agent_id": kernel.agent.agent_id,
                    "run_id": kernel.run.run_id,
                    "semantic_data_model": semantic_data_model_name or "unknown",
                    "status": result.get("status", "unknown"),
                },
            )

        return result

    async def generate_sql(
        self,
        query_intent: Annotated[str, "The natural language intent of the query to generate SQL for."],
        semantic_data_model_name: Annotated[str, "The name of the semantic data model to generate SQL for."],
    ) -> InternalToolResponse:
        """Generate SQL from a natural language query for the specified semantic data model.
        This tool may return a status of success, needs_info, or failure.

        If the status indicates success, the SQL query is ready for execution.
        If the status indicates failure, you should inform the user of the failure,
        along with the reason for that failure.
        If the status indicates needs_info, you should use the included information
        in the response to determine how to generate a more specific intent.
        """
        from time import perf_counter
        from uuid import uuid4

        from agent_platform.core.payloads import InitiateStreamPayload
        from agent_platform.core.thread import Thread, ThreadTextContent, ThreadUserMessage
        from agent_platform.server.data_frames.semantic_data_model_collector import (
            SemanticDataModelCollector,
        )
        from agent_platform.server.runs.sync import invoke_agent_sync
        from agent_platform.server.storage.option import StorageService

        # Get kernel and necessary context from thread_state
        if self._data_frame_tools._thread_state is None:
            raise RuntimeError("Thread state is required for SQL generation")

        kernel = self._data_frame_tools._thread_state.kernel
        storage = StorageService.get_instance()
        file_manager = FileManagerService.get_instance(storage=storage)

        # Start timing for nl2sql cycle metrics
        start_time = perf_counter()
        kernel.ctx.increment_counter(
            "sdm.nl2sql.cycles.total",
            labels={
                "agent_id": kernel.agent.agent_id,
                "run_id": kernel.run.run_id,
                "thread_id": kernel.thread.thread_id,
            },
        )

        # Find the SDM ID that matches the requested name
        sdm_result = await _find_sdm_by_name(storage, kernel.agent.agent_id, semantic_data_model_name)

        if not sdm_result:
            raise ValueError(f"Semantic data model '{semantic_data_model_name}' not found on the user's agent")

        sdm_id, target_sdm = sdm_result

        # Get or create SQL generation agent with well-known name
        # sql_agent = await _get_or_create_sql_agent(kernel, storage)
        from agent_platform.server.sql_generation.preinstalled_agent import get_sql_generation_agent

        sql_agent = await get_sql_generation_agent(storage)
        if sql_agent is None:
            raise ValueError("SQL generation agent not found, this should never happen")

        # The preinstalled agent doesn't have platform configs, so we add the user's platform configs.
        sql_agent = sql_agent.copy(
            platform_configs=kernel.agent.platform_configs,
        )

        thread_id = str(uuid4())
        status = "failure"  # Default to failure, update to success if completed
        try:
            # Create thread for the SQL generation agent
            sql_thread = Thread(
                name=f"SQL Generation: user agent thread {kernel.thread.thread_id}",
                user_id=kernel.user.user_id,
                agent_id=sql_agent.agent_id,
                thread_id=thread_id,
                messages=[],
            )
            await storage.upsert_thread(kernel.user.user_id, sql_thread)

            # Associate the specific SDM with just this thread
            await storage.set_thread_semantic_data_models(
                thread_id,
                [sdm_id],
            )

            # Use the collector to identify files in the user's thread which are referenced by this SDM.
            collector = SemanticDataModelCollector(
                agent_id=kernel.thread.agent_id,
                thread_id=kernel.thread.thread_id,
                user=kernel.user,
                state=None,
            )
            files_to_copy, references = await _collect_sdm_files(
                storage=storage,
                kernel=kernel,
                semantic_data_model=target_sdm,
                collector=collector,
            )

            # Then, upload all of those files to the SQL generation agent's thread.
            _ = await _upload_sdm_files(
                kernel=kernel,
                sql_thread=sql_thread,
                file_manager=file_manager,
                files_to_upload=files_to_copy,
            )

            # Build the initial messages for the SQL generation agent.
            # TODO: we could include both the query intent and an initial predicted query shape.
            #       in the initial message, but that's it hard to use with our quality tests. If we
            #       can inline this in the initial messages, that avoids an LLM tool-call roundtrip (few seconds)
            initial_message = ThreadUserMessage(
                role="user",
                content=[
                    ThreadTextContent(
                        text=f"Generate SQL for: {query_intent}\nUsing semantic data model: {semantic_data_model_name}"
                    )
                ],
            )

            payload = InitiateStreamPayload(
                agent_id=sql_agent.agent_id,
                thread_id=thread_id,
                name=sql_thread.name,
                messages=[initial_message],
            )

            # Invoke agent to completion
            thread, agent_messages = await invoke_agent_sync(
                agent=sql_agent,
                user=kernel.user,
                storage=storage,
                server_context=kernel.ctx,
                initial_payload=payload,
            )

            # Extract result and create response with delegated thread metadata
            result = await _create_internal_tool_response_from_sql_thread(
                thread=thread,
                storage=storage,
                user_id=kernel.user.user_id,
                details=SQLGenerationDetails(
                    intent=query_intent,
                    semantic_data_model_name=semantic_data_model_name,
                    agent_messages=agent_messages,
                ),
                file_manager=file_manager,
            )

            status = "success"
            return result

        except Exception as e:
            logger.error(
                "Invocation of the SQL generation agent failed",
                user_id=kernel.user.user_id,
                user_thread_id=kernel.thread.thread_id,
                sql_agent_id=sql_agent.agent_id,
                sql_thread_id=thread_id,
                error=str(e),
                exc_info=True,
            )
            raise e

        finally:
            # Record metrics consistently for both success and failure paths
            duration = perf_counter() - start_time
            # For metrics related to duration, only record agent + run ID.
            # Thread ID does not make sense for duration metrics.
            kernel.ctx.record_metric(
                "sdm.nl2sql.generation.duration_seconds",
                duration,
                labels={
                    "agent_id": kernel.agent.agent_id,
                    "semantic_data_model": semantic_data_model_name,
                    "status": status,
                    "run_id": kernel.run.run_id,
                },
            )


async def _create_internal_tool_response_from_sql_thread(
    thread: "Thread",
    storage: "BaseStorage",
    user_id: str,
    details: SQLGenerationDetails,
    file_manager: "BaseFileManager",
) -> "InternalToolResponse":
    """Extract SQL generation result and create InternalToolResponse with delegated thread metadata.

    Args:
        thread: The SQL generation agent's completed thread
        agent_messages: Messages from the SQL generation agent's thread
        storage: Storage instance for file retrieval
        user_id: User ID for file access

    Returns:
        InternalToolResponse containing the SQL result and thread messages metadata

    Raises:
        ValueError: If output.json is not found in the thread
    """
    import json

    from agent_platform.core.actions.action_utils import InternalToolResponse
    from agent_platform.core.thread.content.sql_generation import SQLGenerationContent

    # Retrieve output.json
    thread_files = await storage.get_thread_files(thread.thread_id, user_id)

    output_file = next(
        (f for f in thread_files if f.file_ref == "output.json"),
        None,
    )

    if not output_file:
        logger.error(
            "SQL generation agent did not produce output.json",
            messages=[m.model_dump() for m in details.agent_messages],
        )
        raise ValueError("SQL generation agent did not produce output.json")

    # Read file contents
    file_bytes = await file_manager.read_file_contents(
        file_id=output_file.file_id,
        user_id=user_id,
    )

    # Parse JSON to SQLGenerationContent
    file_json = json.loads(file_bytes.decode("utf-8"))
    sql_content = SQLGenerationContent.model_validate(file_json)

    # Return InternalToolResponse with execution metadata including sub-agent messages
    return InternalToolResponse(
        result=sql_content.model_dump_json(),
        execution_metadata={
            "sql_generation_details": details.model_dump(mode="json"),
        },
    )


async def _find_sdm_by_name(
    storage: "BaseStorage",
    agent_id: str,
    semantic_data_model_name: str,
) -> tuple[str, SemanticDataModel] | None:
    """Find the SDM ID for a given SDM name on an agent.

    Args:
        storage: Storage instance
        agent_id: ID of the agent to search
        semantic_data_model_name: Name of the semantic data model to find

    Returns:
        A tuple of (SDM ID, SemanticDataModel) if found, or None otherwise.
    """

    # Get parent agent's SDMs
    agent_sdm_ids = await storage.get_agent_semantic_data_model_ids(agent_id)

    # Find the SDM ID that matches the requested name
    for sdm_id in agent_sdm_ids:
        sdm_data = await storage.get_semantic_data_model(sdm_id)
        sdm = SemanticDataModel.model_validate(sdm_data)
        if sdm.name == semantic_data_model_name:
            return sdm_id, sdm

    return None


async def _collect_sdm_files(
    storage: "BaseStorage",
    kernel: "Kernel",
    semantic_data_model: "SemanticDataModel",
    collector: "SemanticDataModelCollector",
) -> "tuple[list[UploadedFile], References]":
    thread_files = await storage.get_thread_files(kernel.thread.thread_id, kernel.user.user_id)

    # Single API for extraction + (best-effort) file-ref resolution.
    (
        _resolved_sdm,
        references,
    ) = await collector.resolve_file_references_for_semantic_data_model(
        storage=storage,
        semantic_data_model=semantic_data_model,
    )

    # If we have no file references, no extra files to copy.
    if not references.file_references:
        return [], references

    # If the SDM has structural/reference errors, we can't reliably narrow files.
    if references.errors:
        raise RuntimeError(f"Semantic data model has reference errors: {references.errors!r}")

    # The name of thread files that are referenced by the SDM.
    sdm_referenced_file_names = {
        ref.file_ref for ref in references.file_references if ref.thread_id == kernel.thread.thread_id
    }

    return [f for f in thread_files if f.file_ref in sdm_referenced_file_names], references


async def _upload_sdm_files(
    kernel: "Kernel",
    sql_thread: "Thread",
    file_manager: "BaseFileManager",
    files_to_upload: "list[UploadedFile]",
) -> "list[UploadedFile]":
    """Uploads the given threads that are referenced by an SDM to the SQL generation agent's thread."""

    if not files_to_upload:
        return []

    from tempfile import SpooledTemporaryFile
    from typing import BinaryIO, cast

    from fastapi import UploadFile
    from starlette.datastructures import Headers

    from agent_platform.core.payloads import UploadFilePayload

    # TODO this is wasteful as we duplicate N files every time we call generate_sql. Ideally, we would
    # want to reference the same blob in the FileService but our file_owners table doesn't allow us to
    # do that currently.
    uploads: list[UploadFilePayload] = []
    temp_files: list[SpooledTemporaryFile] = []
    try:
        for uploaded_file in files_to_upload:
            file_bytes = await file_manager.read_file_contents(
                file_id=uploaded_file.file_id,
                user_id=kernel.user.user_id,
            )
            temp_file = SpooledTemporaryFile()
            temp_file.write(file_bytes)
            temp_file.seek(0)
            temp_files.append(temp_file)

            file_obj = cast(BinaryIO, temp_file)
            upload = UploadFile(
                filename=uploaded_file.file_ref,
                file=file_obj,
                headers=Headers(
                    {
                        "content-type": uploaded_file.mime_type or "application/octet-stream",
                    }
                ),
            )
            uploads.append(UploadFilePayload(file=upload))

        return await file_manager.upload(uploads, sql_thread, kernel.user.user_id)
    finally:
        for temp_file in temp_files:
            try:
                temp_file.close()
            except Exception:
                logger.warning("Failed to close temporary file", exc_info=True)
