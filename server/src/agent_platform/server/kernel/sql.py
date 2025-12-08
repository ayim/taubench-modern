# ruff: noqa: E501
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated, Any

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.tools.tool_definition import ToolDefinition

if TYPE_CHECKING:
    from agent_platform.server.kernel.data_frames import _DataFrameTools


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

    @abstractmethod
    def get_sql_query_parameter_prompt(self) -> str:
        """Get the prompt text for the sql_query parameter in create_data_frame_from_sql.

        This prompt describes what SQL queries the agent should write and how.

        Returns:
            Prompt text for the sql_query parameter
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

    def get_sql_query_parameter_prompt(self) -> str:
        """Get the SQL query prompt for LegacySqlStrategy.

        This is used when the agent generates SQL directly.
        """
        return """
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
            """

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
        )


def _get_sql_generation_instructions(  # noqa: C901
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
    has_non_snowflake = any(
        engine and engine.lower() != "snowflake" for _, engine in models_and_engines
    )
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
        if not isinstance(model, dict):
            continue

        if engine == "snowflake":
            snowflake_guidance = _get_snowflake_variant_guidance(model)
            if snowflake_guidance:
                # Add prominent banner to make it unmissable
                instructions_parts.append("\n" + "=" * 80)
                instructions_parts.append(
                    "🚨 CRITICAL: SNOWFLAKE VARIANT/OBJECT/ARRAY COLUMN SYNTAX 🚨"
                )
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


def _get_postgres_json_guidance(model: SemanticDataModel) -> str:  # noqa: C901
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
    tables = model.get("tables", [])

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


def _get_snowflake_variant_guidance(model: SemanticDataModel) -> str:  # noqa: C901, PLR0912
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
    tables = model.get("tables", [])

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
    tables = model.get("tables", [])

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

        from agent_platform.server.kernel.semantic_data_model import summarize_data_models

        # Only provide WHAT data is available, not HOW to write SQL
        # The specialized SQL agent will handle the HOW
        return summarize_data_models(semantic_models_and_engines)

    def _choose_sdm_for_query_prompt(self) -> str:
        """Instructions for the agent to choose the semantic data model to use for the query."""
        from textwrap import dedent

        from agent_platform.server.kernel.data_frames import DF_GENERATE_SQL_TOOL_NAME

        return dedent(f"""
        **Choose Semantic Data Model for Query**
        When interacting with a Semantic Data Model, you need to determine the intent of the user's
        request. From this intent, you should analyze the available Semantic Data Models and choose
        the Semantic Data Model which is most relevant to the request. You should determine the best
        Semantic Data Model that contains tables that are most relevant to the request.

        Once you have identified the best Semantic Data Model, you should use the {DF_GENERATE_SQL_TOOL_NAME}
        tool to generate a SQL query. You should never generate SQL queries directly, always use the tool
        to generate a query. If this tool responds that it was unable to generate a query against the
        specified Semantic Data Model, you may attempt to choose a different Semantic Data Model. You
        should only attempt to choose a different Semantic Data Model if there is another likely
        Semantic Data Model that may also be relevant.
        """)

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

    def get_sql_query_parameter_prompt(self) -> str:
        """Get the SQL query prompt for AgenticSqlStrategy.

        This is a placeholder for when SQL generation is delegated to a specialized agent.
        """
        from agent_platform.server.kernel.data_frames import DF_GENERATE_SQL_TOOL_NAME

        return f"""
            A SQL query to execute against existing data frames
            or "logical" tables in semantic data models. You should only provide
            a query as constructed by the {DF_GENERATE_SQL_TOOL_NAME} tool.
            """

    async def create_data_frame_from_sql(
        self,
        sql_query: Annotated[
            str,
            """
            A SQL query to execute against existing data frames
            or tables in semantic data models. You should only provide
            a query as constructed by the generate_sql tool.
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
        """Run a SQL query against the existing data frames or "logical" tables in semantic
        data models and use its data to create a new data frame.

        A sample of the newly created data frame is returned (specified by num_samples).
        """
        assert self._data_frame_tools._create_data_frame_from_sql_impl is not None, (
            "create_df_from_sql_impl is required for SQL operations"
        )
        return await self._data_frame_tools._create_data_frame_from_sql_impl(
            sql_query=sql_query,
            new_data_frame_name=new_data_frame_name,
            new_data_frame_description=new_data_frame_description,
            num_samples=num_samples,
        )

    async def generate_sql(
        self,
        query_intent: Annotated[
            str, "The natural language intent of the query to generate SQL for."
        ],
        semantic_data_model_name: Annotated[
            str, "The name of the semantic data model to generate SQL for."
        ],
    ) -> str:
        """Generate SQL from a natural language query."""
        return "TODO"
