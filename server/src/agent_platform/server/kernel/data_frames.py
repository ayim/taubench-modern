# ruff: noqa: E501, PLR0912, PLR0913, PLR0915, C901, PLR0911
from __future__ import annotations

import typing
from typing import Annotated, Any, Literal

from structlog import get_logger

from agent_platform.core.kernel import DataFramesInterface
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.data_frames.semantic_data_model_types import (
        SemanticDataModel,
        VerifiedQuery,
    )
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState
    from agent_platform.core.kernel_interfaces.thread_state import ThreadStateInterface
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelAndReferences,
    )
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)

DF_CREATE_FROM_SQL_TOOL_NAME = "data_frames_create_from_sql"
DF_DELETE_TOOL_NAME = "data_frames_delete"
DF_SLICE_TOOL_NAME = "data_frames_slice"
DF_CREATE_FROM_FILE_TOOL_NAME = "data_frames_create_from_file"
DF_CREATE_FROM_VERIFIED_QUERY_TOOL_NAME = "data_frames_create_from_verified_query"
DF_CREATE_FROM_JSON_TOOL_NAME = "data_frames_create_from_json"

_TOOLS_THAT_CAN_REFERENCE_DATA_FRAMES = (
    f"{DF_SLICE_TOOL_NAME}, {DF_DELETE_TOOL_NAME}, {DF_CREATE_FROM_SQL_TOOL_NAME} "
    "(may be referenced by the name as tables in the SQL query)"
)


def _clean_value_for_json(value: Any) -> Any:
    """Clean a value for JSON/DataFrame storage.

    Handles:
    - Complex objects (dict/list) → JSON string
    - NaN/None/inf → None
    - Everything else → as-is
    """
    import json
    import math

    import pandas as pd

    # Handle complex objects first (before pd.isna check)
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    # Handle NaN values (including float('nan'), pd.NA, np.nan, etc.)
    elif pd.isna(value):
        return None
    # Handle inf/-inf values
    elif isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    else:
        return value


async def create_data_frame_from_columns_and_rows(
    *,
    columns: list[str],
    rows: list[list],
    name: str,
    user_id: str,
    agent_id: str,
    thread_id: str,
    storage: BaseStorage,
    description: str | None = None,
    input_id_type: Literal["file", "sql_computation", "in_memory"] = "in_memory",
    num_sample_rows: int = 10,
    file_id: str | None = None,
    file_ref: str | None = None,
    sheet_name: str | None = None,
) -> PlatformDataFrame:
    """Create a data frame from columns and rows data.

    This shared implementation is used by both the kernel's auto-create functionality
    and the API endpoint for creating data frames from raw data.

    Args:
        columns: List of column names
        rows: List of rows, where each row is a list of values
        name: Name for the data frame
        user_id: User ID
        agent_id: Agent ID
        thread_id: Thread ID
        storage: Storage instance to save the data frame
        description: Optional description
        input_id_type: Type of input (e.g., "in_memory", "file", "sql_computation")
        num_sample_rows: Number of sample rows to store (for LLM context)
        file_id: Optional file ID if created from a file
        file_ref: Optional file reference if created from a file
        sheet_name: Optional sheet name if created from a spreadsheet

    Returns:
        The created PlatformDataFrame
    """
    import datetime
    import io
    from uuid import uuid4

    import pyarrow.parquet

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame

    # Clean all values in rows to handle complex objects (dict/list) and NaN values
    # This prevents PyArrow from failing when encountering unsupported types
    cleaned_rows = [[_clean_value_for_json(value) for value in row] for row in rows]

    # Convert rows and columns format to dictionary format for PyArrow
    # This allows PyArrow to automatically infer the schema
    col_data = list(zip(*cleaned_rows, strict=True)) if cleaned_rows else [[] for _ in columns]

    # Build the table
    pyarrow_df = pyarrow.Table.from_arrays([pyarrow.array(col) for col in col_data], names=columns)

    stream = io.BytesIO()
    pyarrow.parquet.write_table(pyarrow_df, stream)

    sample_rows = cleaned_rows[:num_sample_rows] if num_sample_rows > 0 else []

    data_frame = PlatformDataFrame(
        data_frame_id=str(uuid4()),
        name=name,
        description=description,
        user_id=user_id,
        agent_id=agent_id,
        thread_id=thread_id,
        num_rows=pyarrow_df.shape[0],
        num_columns=pyarrow_df.shape[1],
        column_headers=list(pyarrow_df.schema.names),
        input_id_type=input_id_type,
        created_at=datetime.datetime.now(datetime.UTC),
        parquet_contents=stream.getvalue(),
        computation_input_sources={},
        extra_data=PlatformDataFrame.build_extra_data(sample_rows=sample_rows),
        file_id=file_id,
        file_ref=file_ref,
        sheet_name=sheet_name,
    )

    await storage.save_data_frame(data_frame)
    return data_frame


def _handle_some_table_field(k: str, v: Any) -> str:
    k = k.replace("_", " ").title()

    import yaml

    return f"{k}:\n{yaml.safe_dump(v, sort_keys=False)}"


def _get_postgres_json_guidance(model: SemanticDataModel) -> str:
    """
    Generate PostgreSQL-specific JSON/JSONB column guidance for a semantic data model.

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


def _get_snowflake_variant_guidance(model: SemanticDataModel) -> str:
    """
    Generate Snowflake-specific VARIANT/ARRAY/OBJECT column guidance for a semantic data model.
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


def _convert_semantic_data_model_to_context_string(
    data: list[tuple[SemanticDataModel, str]],
) -> str:
    """
    Convert data to a string that can be used in an LLM context.

    We try to format the data in a way that is easy to read and understand,
    but still trying to keep it concise so that we don't use few tokens
    (right now we use yaml.safe_dump to convert the data to a string).
    """
    import textwrap
    from textwrap import indent

    if not data:
        return "No semantic data models available."

    verified_queries = []
    result = []

    for model, engine in data:
        if not isinstance(model, dict):
            continue

        model = model.copy()  # noqa: PLW2901

        # Model header
        name = model.pop("name", "Unnamed")
        description = model.pop("description", "")

        model_header = f"### Model: {name}"
        model_header += f"\nSQL dialect: {engine}"
        if description:
            model_header += f"\nDescription: {description}"
        result.append(model_header)

        # Add database-specific guidance IMMEDIATELY after header for maximum visibility
        if engine == "snowflake":
            snowflake_guidance = _get_snowflake_variant_guidance(model)
            if snowflake_guidance:
                # Add prominent banner to make it unmissable
                result.append("\n" + "=" * 80)
                result.append("🚨 CRITICAL: SNOWFLAKE VARIANT/OBJECT/ARRAY COLUMN SYNTAX 🚨")
                result.append("=" * 80)
                result.append(snowflake_guidance)
                result.append("=" * 80 + "\n")
        elif engine == "postgres":
            postgres_guidance = _get_postgres_json_guidance(model)
            if postgres_guidance:
                result.append(postgres_guidance)

        # Tables
        tables = model.pop("tables", [])
        if tables:
            for table in tables:
                if not isinstance(table, dict):
                    continue

                table = table.copy()  # noqa: PLW2901
                table_name = table.pop("name")
                if not table_name:
                    continue
                table_desc = table.pop("description", "")

                table_line = f"Table: {table_name}"
                if table_desc:
                    table_line += f"\n Description: {table_desc}"
                result.append(table_line)

                for k, v in table.items():
                    if v:
                        result.append(indent(_handle_some_table_field(k, v), " "))

        verified_queries.extend(model.pop("verified_queries", None) or ())

        # Handle what we haven't added yet (relationships, etc.)
        for k, v in model.items():
            if v:
                result.append(_handle_some_table_field(k, v))

        result.append("")  # Empty line between models

    # Add verified queries
    if verified_queries:
        result.append(
            textwrap.dedent(f"""
        ### Verified Queries

        Note: These can be used to create data frames using the `{DF_CREATE_FROM_VERIFIED_QUERY_TOOL_NAME}` tool.
              by providing the "name" of the verified query as a parameter to the `{DF_CREATE_FROM_VERIFIED_QUERY_TOOL_NAME}` tool.

        Below is a list with the verified query names and a description on what the verified queries can be used for:
        """)
        )
        for verified_query in verified_queries:
            result.append(f"- name: {verified_query['name']}")
            result.append(f"  description: {verified_query['nlq']}")
            result.append("")

    return "\n".join(result)


class AgentServerDataFramesInterface(DataFramesInterface, UsesKernelMixin):
    """Handles interaction with data frames."""

    def __init__(self):
        super().__init__()
        self._name_to_data_frame: dict[str, PlatformDataFrame] = {}
        self._data_frame_tools: tuple[ToolDefinition, ...] = ()
        self._semantic_data_models: list[SemanticDataModelAndReferences] = []
        # verified_query_name -> VerifiedQuery
        self._verified_queries: dict[str, VerifiedQuery] = {}

        # Storage is needed to get data connections
        self._data_connection_id_to_engine: dict[str, str] = {}

    def is_enabled(self) -> bool:
        """Returns True if data frames are enabled (and False otherwise).
        Note: it's opt-out, so, by default data frames are enabled
        unless explicitly disabled (in env var or agent settings)."""
        import os

        agent_settings = self.kernel.agent.extra.get("agent_settings", {})
        if "enable_data_frames" in agent_settings:
            return bool(agent_settings["enable_data_frames"])

        if "SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES" in os.environ:
            disable_data_frames = os.environ["SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES"].lower() in (
                "0",
                "false",
            )
            return not disable_data_frames

        return True

    async def step_initialize(
        self, *, storage: BaseStorage | None = None, state: DataFrameArchState
    ) -> None:
        from agent_platform.core.data_frames.semantic_data_model_types import VerifiedQuery
        from agent_platform.server.data_frames.semantic_data_model_collector import (
            SemanticDataModelCollector,
        )
        from agent_platform.server.storage.option import StorageService

        # If data frames are not enabled, don't create any tools
        if not self.is_enabled():
            self._data_frame_tools = ()
            return

        # Initialize tools
        previous_state: Literal["enabled", ""] = state.data_frames_tools_state

        try:
            storage = StorageService.get_instance() if storage is None else storage
            data_frames = tuple(
                await storage.list_data_frames(thread_id=self.kernel.thread.thread_id)
            )
        except Exception:
            logger.exception("Error getting data frames")
            data_frames = ()

        assert storage is not None, "Storage is required to create data frame tools"

        self._name_to_data_frame = {data_frame.name: data_frame for data_frame in data_frames}

        collector = SemanticDataModelCollector(
            agent_id=self.kernel.thread.agent_id,
            thread_id=self.kernel.thread.thread_id,
            user=self.kernel.user,
            state=state,
        )
        self._semantic_data_models = await collector.collect_semantic_data_models(storage)
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
            data_connections = await storage.get_data_connections(list(all_data_connection_ids))
            for data_connection in data_connections:
                self._data_connection_id_to_engine[data_connection.id] = data_connection.engine

        data_frame_tools = _DataFrameTools(
            self.kernel.user,
            self.kernel.thread.thread_id,
            self._name_to_data_frame,
            storage,
            thread_state=self.kernel.thread_state,
            verified_queries=self._verified_queries,
        )
        if data_frames or previous_state == "enabled":
            if not previous_state:
                state.data_frames_tools_state = "enabled"

            tools_list = [
                ToolDefinition.from_callable(
                    data_frame_tools.create_data_frame_from_file,
                    name=DF_CREATE_FROM_FILE_TOOL_NAME,
                ),
                ToolDefinition.from_callable(
                    data_frame_tools.create_data_frame_from_json,
                    name=DF_CREATE_FROM_JSON_TOOL_NAME,
                ),
                ToolDefinition.from_callable(
                    data_frame_tools.delete_data_frame, name=DF_DELETE_TOOL_NAME
                ),
                ToolDefinition.from_callable(
                    data_frame_tools.data_frame_slice, name=DF_SLICE_TOOL_NAME
                ),
                ToolDefinition.from_callable(
                    data_frame_tools.create_data_frame_from_sql, name=DF_CREATE_FROM_SQL_TOOL_NAME
                ),
            ]

            # Add tool for verified queries if any exist
            if self._verified_queries:
                tools_list.append(
                    ToolDefinition.from_callable(
                        data_frame_tools.create_data_frame_from_verified_query,
                        name=DF_CREATE_FROM_VERIFIED_QUERY_TOOL_NAME,
                    )
                )

            self._data_frame_tools = tuple(tools_list)
        else:
            # Creating from a file or JSON should be always there (i.e.: the user should be able to
            # create a data frame from a file or JSON data even if there are no data frames yet).
            # Transform should also be available for general JSON manipulation.
            self._data_frame_tools = (
                ToolDefinition.from_callable(
                    data_frame_tools.create_data_frame_from_file,
                    name=DF_CREATE_FROM_FILE_TOOL_NAME,
                ),
                ToolDefinition.from_callable(
                    data_frame_tools.create_data_frame_from_json,
                    name=DF_CREATE_FROM_JSON_TOOL_NAME,
                ),
            )

            tools_list: list[ToolDefinition] = []
            if self._semantic_data_models:
                tools_list.append(
                    ToolDefinition.from_callable(
                        data_frame_tools.create_data_frame_from_sql,
                        name=DF_CREATE_FROM_SQL_TOOL_NAME,
                    )
                )

            # Add tool for verified queries if any exist
            if self._verified_queries:
                tools_list.append(
                    ToolDefinition.from_callable(
                        data_frame_tools.create_data_frame_from_verified_query,
                        name=DF_CREATE_FROM_VERIFIED_QUERY_TOOL_NAME,
                    )
                )

            if tools_list:
                self._data_frame_tools += tuple(tools_list)

    @property
    def data_frames_system_prompt_no_tools(self) -> str:
        from textwrap import dedent

        if not self.thread_has_data_frames and not self._semantic_data_models:
            return ""

        prompt = ""

        if self.thread_has_data_frames:
            prompt += dedent("""
            Data frames were made available in the prior conversation. You
            must not use any tools this turn, but should you need to reference the available data
            frames to discuss them or to better contextualize your response, you will find them
            here:
            """)
            prompt += self.data_frames_summary

        if self._semantic_data_models:
            prompt += dedent("""
            Semantic data models were made available in the prior conversation. You
            must not use any tools this turn, but should you need to reference the available
            semantic data models to discuss them or to better contextualize your response,
            you will find them here:
            """)
            prompt += self.semantic_data_models_summary

        return prompt

    @property
    def data_frames_system_prompt(self) -> str:
        if not self.thread_has_data_frames and not self._semantic_data_models:
            # i.e.: For now return empty (so that we don't change anything in the system prompt
            # if the user hasn't created a data frame).
            return ""

        ret = ""

        if self.thread_has_data_frames or self._semantic_data_models:
            if self.thread_has_data_frames:
                try:
                    ret += (
                        f"## Data Frames Summary"
                        "\n-- available to be used in the following tools: "
                        f"{_TOOLS_THAT_CAN_REFERENCE_DATA_FRAMES}"
                        f"\n\n{self.data_frames_summary}\n\n"
                    )
                    ret += (
                        "\n\nNote: It's possible to use an url such as "
                        "'data-frame://<data_frame_name>' "
                        "to get the data frame in json format to use in vega-lite charts.\n\n"
                    )
                except Exception:
                    logger.exception("Error creating data frames summary")

            if self._semantic_data_models:
                try:
                    ret += (
                        f"## Semantic Data Models (tables available to be used in the "
                        f"`{DF_CREATE_FROM_SQL_TOOL_NAME}` tool):\n"
                        f"{self.sdm_join_guidance}\n"
                        f"{self.semantic_data_models_summary}\n\n"
                    )
                except Exception:
                    logger.exception("Error creating semantic data models summary")
        return ret

    @property
    def sdm_join_guidance(self) -> str:
        from textwrap import dedent

        models_and_engines = self._semantic_data_models_with_engines()
        if not models_and_engines:
            return ""

        has_non_snowflake = any(
            engine and engine.lower() != "snowflake" for _, engine in models_and_engines
        )
        if not has_non_snowflake:
            return ""

        return dedent("""
        **IMPORTANT:** Always use table qualifiers (e.g., 'tbl.column_name') in SQL, especially
        in CTEs and JOINs. Unqualified columns may cause ambiguity errors.
        """)

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
    def semantic_data_models_summary(self) -> str:
        if not self._semantic_data_models:
            return "You have no semantic data models to work with."

        models_and_engines = self._semantic_data_models_with_engines()
        if not models_and_engines:
            return "No semantic data models available."

        return _convert_semantic_data_model_to_context_string(models_and_engines)

    @property
    def data_frames_summary(self) -> str:
        if not self._name_to_data_frame:
            return "You have no data frames to work with."

        summary = [f"You have {len(self._name_to_data_frame)} data frames to work with. Details:\n"]
        for data_frame in self._name_to_data_frame.values():
            summary.append(self._data_frame_summary(data_frame))
        ret = "\n".join(summary)

        return ret

    def _data_frame_summary(self, data_frame: PlatformDataFrame) -> str:
        result = [f"### Data Frame: {data_frame.name}"]
        if data_frame.sql_dialect:
            result.append(f"SQL dialect: {data_frame.sql_dialect}")
        if data_frame.description:
            result.append(f"Description: {data_frame.description}")
        if data_frame.num_rows:
            result.append(f"Number of rows: {data_frame.num_rows}")
        if data_frame.num_columns:
            result.append(f"Number of columns: {data_frame.num_columns}")
        if data_frame.column_headers:
            column_names_str = "\n- ".join([str(col) for col in data_frame.column_headers])
            result.append(f"Column names:\n- {column_names_str}")
        if data_frame.sample_rows:
            rows_as_list_str = "\n- ".join([str(row) for row in data_frame.sample_rows])
            result.append(f"Sample data:\n- {rows_as_list_str}")
        return "\n".join(result)

    @property
    def thread_has_data_frames(self) -> bool:
        return bool(self._name_to_data_frame)

    def get_data_frame_tools(
        self,
    ) -> tuple[ToolDefinition, ...]:
        return self._data_frame_tools

    async def _create_in_memory_data_frame(
        self,
        name: str,
        contents: dict[str, list],
        *,
        description: str | None = None,
        storage: BaseStorage | None = None,
    ) -> PlatformDataFrame:
        """Create an in-memory data frame from columns and rows.

        This is a wrapper around create_data_frame_from_columns_and_rows that provides
        the necessary context from the kernel.
        """
        from agent_platform.server.storage.option import StorageService

        storage = StorageService.get_instance() if storage is None else storage

        data_frame = await create_data_frame_from_columns_and_rows(
            columns=contents["columns"],
            rows=contents["rows"],
            name=name,
            description=description,
            user_id=self.kernel.thread.user_id,
            agent_id=self.kernel.thread.agent_id,
            thread_id=self.kernel.thread.thread_id,
            storage=storage,
            input_id_type="in_memory",
            num_sample_rows=10,
        )

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
        import keyword

        # If data frames are not enabled, don't auto create a data frame
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
                    name = possible_table.get("name")
                    description = possible_table.get("description")
                    found_keys = set(possible_table.keys())
                    found_keys.discard("name")
                    found_keys.discard("description")

                    if set(("columns", "rows")) == found_keys:
                        if name:
                            if not name.isidentifier() or keyword.iskeyword(name):
                                name = slugify(name).replace("-", "_")

                        if not name:
                            name = slugify(tool_def.name).replace("-", "_")

                        i = 1
                        base_name = name
                        while name in self._name_to_data_frame:
                            name = f"{base_name}_{i:02d}"
                            i += 1
                        data_frame = await self._create_in_memory_data_frame(
                            name=name,
                            contents=possible_table,
                            description=description,
                        )
                        data_frame_summary = self._data_frame_summary(data_frame)
                        logger.info(
                            f"Automatically created data frame {name} from {tool_def.name}."
                        )
                        msg = f"Data frame {name} created from {tool_def.name}.\nDetails: "
                        msg += data_frame_summary

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

    async def on_upload_file_build_prompt(
        self, file_details: UploadedFile, is_work_item_attachment: bool = False
    ) -> str | None:
        """Build a prompt related to data frames for the user after uploading a file.

        Args:
            file_details: The details of the uploaded file.
            is_work_item_attachment: Whether the uploaded file is a work item attachment.

        Returns:
            The prompt for the user after uploading a file, or None if no custom
            prompt should be added (based on data frames).
        """
        if not self.is_enabled():
            return None

        from textwrap import dedent

        from agent_platform.core.data_frames.data_frames import DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT
        from agent_platform.core.files.mime_types import TABULAR_DATA_MIME_TYPES
        from agent_platform.server.api.private_v2.threads_data_frames import (
            InspectFileAsDataFrame,
            create_data_frame_from_inspected_data_frame,
        )
        from agent_platform.server.storage.option import StorageService

        if file_details.mime_type not in TABULAR_DATA_MIME_TYPES:
            return None

        kernel = self.kernel

        try:
            inspector = InspectFileAsDataFrame(
                user=kernel.user,
                tid=kernel.thread.thread_id,
                storage=StorageService.get_instance(),
                num_samples=DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT,
                sheet_name=None,
                file_metadata=file_details,
            )
            found = await inspector.inspect_from_cache()
            if not isinstance(found, list):
                found = await inspector.inspect_and_cache_from_file()

            if isinstance(found, list) and len(found) > 0:
                if len(found) == 1:
                    storage = StorageService.get_instance()
                    # A file with a single sheet was found, create a data frame from it right away.
                    created_data_frame = await create_data_frame_from_inspected_data_frame(
                        kernel.user, kernel.thread.thread_id, storage, found[0]
                    )
                    if is_work_item_attachment:
                        return dedent(f"""
                            Note: a data frame named `{created_data_frame.name}` was created from
                            this file. Follow the runbook for instructions related to the data frame or uploaded files.
                            """).strip()
                    else:
                        return dedent(f"""
                            Note: a data frame named `{created_data_frame.name}` was created from
                            this file. Follow the runbook if it has instructions
                            related to the data frame or uploaded files, otherwise, do not call any tools at this point
                            and provide options of what information can be answered based on it.
                            """).strip()
                else:
                    # Multiple sheets found - ask LLM to show options
                    sheet_names = [
                        inspected_data_frame.sheet_name for inspected_data_frame in found
                    ]

                    if is_work_item_attachment:
                        return dedent(f"""
                            Note: This file has the following sheets: {sheet_names!r}.
                            Please follow the runbook for instructions related to data frames or uploaded files.
                            """).strip()
                    else:
                        return dedent(f"""
                            Note: This file has the following sheets: {sheet_names!r}.
                            Please follow the runbook if it has instructions related to data frames
                            or uploaded files, otherwise, provide options for the user to create data
                            frames from all or individual sheets, but don't call any tools at this point,
                            just provide options to the user based on the sheets found in the file.
                            """).strip()

            # No data frames found, provide details saying so to the user.
            if is_work_item_attachment:
                return dedent("""
                    Note: although this is a tabular data file, no data frames can be extracted from it.
                    Please follow the runbook if it has instructions related to uploaded files.
                    """).strip()
            else:
                return dedent("""
                    Note: although this is a tabular data file, no data frames can be extracted from it.
                    Please follow the runbook if it has instructions related to uploaded files,
                    otherwise, do not call any tools at this point and ask the user how to proceed to process it.
                    """).strip()

        except Exception as e:
            logger.exception("Error inspecting file as data frame")
            if is_work_item_attachment:
                return dedent(f"""
                    Note: although this is a tabular data file, it was not possible to automatically
                    extract data frame information from it (the following error happened: {e}).
                    Please follow the runbook for instructions related to uploaded files.
                    """).strip()
            else:
                return dedent(f"""
                    Note: although this is a tabular data file, it was not possible to automatically
                    extract data frame information from it (the following error happened: {e}).
                    Please follow the runbook if it has instructions related to uploaded files,
                    otherwise, do not call any tools at this point and ask the user how to proceed.
                    """).strip()

        raise RuntimeError("Should not get here, something went wrong with the file inspection")


class _DataFrameTools:
    """Tools for data frames."""

    def __init__(
        self,
        user: AuthedUser,
        tid: str,
        name_to_data_frame: dict[str, PlatformDataFrame],
        storage: BaseStorage,
        thread_state: ThreadStateInterface | None = None,
        verified_queries: dict[str, VerifiedQuery] | None = None,
    ):
        assert isinstance(name_to_data_frame, dict), (
            f"Expected a dict, got {type(name_to_data_frame)}"
        )
        self._user = user
        self._tid = tid
        self._name_to_data_frame = name_to_data_frame
        self._storage = storage
        self._thread_state = thread_state
        self._verified_queries = verified_queries or {}

    def _create_data_frames_kernel(self) -> DataFramesKernel:
        from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel

        return DataFramesKernel(self._storage, self._user, self._tid)

    async def create_data_frame_from_file(
        self,
        data_frame_name: Annotated[
            str,
            """The name of the data frame to create (IMPORTANT: It must be a valid variable name
            such as 'my_data_frame', only ascii letters, numbers and underscores are allowed
            and it cannot start with a number or be a python keyword. IMPORTANT: The name must
            be unique in the thread (updating an existing data frame is not possible).""",
        ],
        file_ref: Annotated[
            str,
            "The file reference to create the data frame from. This should be the filename only "
            "(e.g., 'data.xlsx' or 'data.csv'), not a file ID or path with UUID.",
        ],
        sheet_name: Annotated[str | None, "The name of the sheet to inspect."] = None,
        description: Annotated[str | None, "The description for the data frame."] = None,
        num_samples: Annotated[int, "The number of samples to return for each data frame."] = 0,
    ) -> dict[str, Any]:
        """Creates a data frame from a file. This should only be used for files containing tabular
        data such as .csv, .xlsx, .xls (creating a data frame is only useful when further analysis
        of the data is needed in a tabular format)."""
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
        # Remove binary data that can't be JSON serialized
        ret_as_dict.pop("parquet_contents", None)
        if "created_at" in ret_as_dict:
            ret_as_dict["created_at"] = ret_as_dict["created_at"].isoformat()
        return ret_as_dict

    async def create_data_frame_from_json(
        self,
        data_frame_name: Annotated[
            str,
            "The name of the data frame to create. The name must be unique in the thread.",
        ],
        tool_call_ref_or_json_data: Annotated[
            str,
            """A previous tool call result (or alternatively the JSON data) to convert.

            This can be:
            1. A message reference using out.tool_name[index] format, where the index is 1-indexed and
            tool_name is actually the name of the tool that you want to get the result from, e.g: parse_document.
            Examples:
               - out.extract_document[1] = Get result from 1st call to extract_document
               - out.extract_document[3] = Get result from 3rd call to extract_document
               - out.extract_document[-1] = Get result from last call to extract_document
               - out.parse_document[-2] = Get result from second to last call to parse_document
            2. A JSON string: '{\"items\": [{\"product\": \"A\", \"price\": 10}]}'

            When using a reference, the tool will look for the tool result
            and use it as the JSON data.
            Always try to use a reference when possible instead of copying JSON.
            """,
        ],
        jq_expression: Annotated[
            str | None,
            """JQ expression to transform/select the JSON data into tabular format.
            If not provided, the JSON data is used as is.

            NOTE: We use pyjaq (stricter than standard jq).

            Common patterns:
            - Extract array of objects: '.items[]' - each object becomes a row
            - Filter and extract: '.items[] | select(.price > 10)'
            - Create custom columns: '.items[] | {code, total: (.price * .qty)}'
            - Navigate nested data: '.invoice.line_items[]'
            - Use variables: '.items[] | select(.price > 10) as $item | {code: $item.code}'
            - Remove non-numeric chars: 'gsub("[^0-9.]";"")'

            Best Practices:
            - Keep expressions simple and prefer one-liners
            - Use contains("text") instead of regex test() when possible
            - Always return structured JSON (objects/arrays), not raw text
            - Use 'as $var' for temporary variables to improve readability

            Avoid:
            - Escaped parentheses or dollar signs (\\(, \\$) - use plain syntax
            - Extra quotes around the entire expression
            - Mixing shell quoting rules
            - Building expressions with string concatenation or f-strings
            - jq-only extensions not in jaq (like sub() with flags)
            """,
        ],
        description: Annotated[str | None, "The description for the data frame."] = None,
        num_samples: Annotated[int, "The number of samples to return for each data frame."] = 0,
    ) -> dict[str, Any]:
        """Creates a data frame from JSON data using JQ to select and transform data.

        This tool:
        1. Gets JSON data (either directly or by looking up a tool call's output)
        2. Applies a JQ expression to extract/transform into tabular format
        3. Converts the result to a DataFrame
        """
        # Use _transform_json to handle JSON parsing, reference lookup, and JQ transformation
        # If no jq_expression provided, use identity transform to pass through the data
        effective_jq_expression = jq_expression if jq_expression is not None else "."

        transform_result = await self._transform_json(
            tool_call_ref_or_json_data, effective_jq_expression
        )

        if "error_code" in transform_result:
            return transform_result

        # Extract the transformed data
        transformed_data = transform_result["result"]

        from agent_platform.server.api.private_v2.threads_data_frames import (
            _convert_jq_result_to_columns_rows,
        )

        try:
            columns, rows = _convert_jq_result_to_columns_rows(transformed_data)
        except ValueError as e:
            error_msg = str(e)
            if "empty array" in error_msg:
                return {
                    "error_code": "empty_result",
                    "message": error_msg,
                }
            else:
                return {
                    "error_code": "invalid_jq_result",
                    "message": error_msg,
                }

        from dataclasses import asdict

        from agent_platform.core.data_frames.data_frames import DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT

        # Determine the number of samples to use
        if num_samples < 0:
            use_num_samples = num_samples
        else:
            use_num_samples = max(num_samples, DATAFRAMES_LLM_SAMPLE_ROWS_LIMIT)

        # Get the thread to find the agent_id
        thread = await self._storage.get_thread(self._user.user_id, self._tid)
        if not thread:
            return {
                "error_code": "thread_not_found",
                "message": f"Thread {self._tid!r} not found",
            }

        # Create the data frame
        ret = await create_data_frame_from_columns_and_rows(
            columns=columns,
            rows=rows,
            name=data_frame_name,
            user_id=self._user.user_id,
            agent_id=thread.agent_id,
            thread_id=self._tid,
            storage=self._storage,
            description=description,
            input_id_type="in_memory",
            num_sample_rows=use_num_samples,
        )

        ret_as_dict = asdict(ret)
        # Remove binary data that can't be JSON serialized
        ret_as_dict.pop("parquet_contents", None)
        if "created_at" in ret_as_dict:
            ret_as_dict["created_at"] = ret_as_dict["created_at"].isoformat()
        return ret_as_dict

    async def _transform_json(
        self,
        tool_call_ref_or_json_data: Annotated[
            str,
            "A previous tool call result (or alternatively the JSON data) to convert.",
        ],
        jq_expression: Annotated[
            str,
            """JQ expression to transform/filter the JSON data.""",
        ],
    ) -> dict:
        """Transforms JSON data using a JQ expression.

        This tool:
        1. Gets JSON data (either directly or by looking up a tool call's output)
        2. Applies a JQ expression to transform/filter the data
        3. Returns the transformed JSON

        Use this when you need to extract, filter, or transform JSON data
        without creating a DataFrame.
        """
        import json

        # Step 1: Try to parse as JSON directly
        try:
            _parsed_json_data = json.loads(tool_call_ref_or_json_data)
        except (json.JSONDecodeError, TypeError):
            # Not JSON, must be a message reference (out.tool_name[index])
            ref = tool_call_ref_or_json_data.strip()

            if self._thread_state is None:
                return {
                    "error_code": "thread_state_not_available",
                    "message": "Thread state is not available for message reference lookup",
                }

            from agent_platform.server.kernel.thread_utils import get_tool_result_by_ref

            result = get_tool_result_by_ref(self._thread_state, ref)

            if isinstance(result, dict) and "error_code" in result:
                return result

            _parsed_json_data = result

        from agent_platform.orchestrator._jq_transform import apply_jq_transform

        try:
            transformed_data = apply_jq_transform(_parsed_json_data, jq_expression)
        except NotImplementedError as e:
            return {
                "error_code": "not_implemented",
                "message": str(e),
            }
        except Exception as e:
            return {
                "error_code": "jq_error",
                "message": f"Error applying JQ expression: {e!s}",
            }

        return {"result": transformed_data}

    async def delete_data_frame(
        self,
        data_frame_name: Annotated[str, "The name of the existing data frame to delete."],
    ) -> dict[str, Any]:
        """Deletes a data frame from this thread."""
        if data_frame_name not in self._name_to_data_frame:
            return {
                "error_code": "data_frame_not_found",
                "message": f"Data frame {data_frame_name!r} not found",
            }

        try:
            await self._storage.delete_data_frame_by_name(self._tid, data_frame_name)
            self._name_to_data_frame.pop(data_frame_name)
        except Exception as e:
            logger.exception(f"Error deleting data frame {data_frame_name} in thread {self._tid}")
            return {
                "error_code": "unable_to_delete_data_frame",
                "message": (
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
                "message": f"Data frame {data_frame_name!r} not found",
            }

        if limit <= 0:
            return {
                "error_code": "invalid_limit",
                "message": "limit must be > 0",
            }

        max_limit = 500
        if limit > max_limit:
            return {
                "error_code": "invalid_limit",
                "message": f"limit must be <= {max_limit}",
            }

        try:
            data_frames_kernel = self._create_data_frames_kernel()
            resolved_df = await data_frames_kernel.resolve_data_frame(data_frame)

            sliced_data = await resolved_df.slice(
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
                "message": f"Unable to sample data frame. Error: {e!r}",
            }

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
        - After 3 failed attempts with different SQL variations, explain the issue to the user
        - Do NOT keep retrying the same SQL - each retry should incorporate the feedback from previous attempts

        If the query is not valid, a structured response will be returned with guidance so it can be corrected and retried.
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

            resolved_df, _samples_table = await create_data_frame_from_sql_computation_api(
                data_frames_kernel=data_frames_kernel,
                storage=self._storage,
                new_data_frame_name=new_data_frame_name,
                sql_query=sql_query,
                dialect=None,  # Computed based on dependencies (semantic data model and data frames)
                description=new_data_frame_description,
                num_samples=num_samples if num_samples > 0 else 0,
            )

            self._name_to_data_frame[new_data_frame_name] = resolved_df.platform_data_frame

            if num_samples <= 0:
                return {
                    "status": "success",
                    "result": f"Data frame {new_data_frame_name} created from SQL query",
                    "data_frame_name": new_data_frame_name,
                }

            sliced_data = await resolved_df.slice(
                offset=0,
                limit=num_samples,
                column_names=None,
                output_format="table",
            )

            assert isinstance(sliced_data, Table), f"Expected a Table, got {type(sliced_data)}"

            return {
                "status": "success",
                "result": f"Data frame {new_data_frame_name} created from SQL query",
                "sample_data": sliced_data.model_dump(),
                "data_frame_name": new_data_frame_name,
            }
        except Exception as e:
            logger.error(
                f"SQL query failed in thread {self._tid}",
                error=str(e),
                sql_query=sql_query,
                data_frame_name=new_data_frame_name,
            )

            # Instead of returning an actual error, we return a status to indicate the need to
            # retry. This allows the LLM to see the suggestion and rewrite the query without
            # alerting the user of the agent into thinking there is a fundamental issue with
            # the agent or this tool.
            # TODO: We need to implement proper SQL healing/fixing in the SDM modules.
            return {
                "status": "needs_retry",
                "message": str(e),
                "data_frame_name": None,
                "sample_data": None,
            }

    async def create_data_frame_from_verified_query(
        self,
        verified_query_name: Annotated[
            str,
            "The name of the verified query to use to create a data frame.",
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
        """Create a data frame from a verified query that was previously saved in a semantic data model.

        Verified queries are pre-validated SQL queries that have been saved in semantic data models.
        This tool allows you to execute a verified query to create a new data frame.

        The verified query name must match one of the verified queries available in the semantic data models
        associated with this thread or agent.
        """
        if verified_query_name not in self._verified_queries:
            available_queries = (
                ", ".join(sorted(self._verified_queries.keys()))
                if self._verified_queries
                else "none"
            )
            return {
                "error": (
                    f"Verified query '{verified_query_name}' not found. "
                    f"Available verified queries: {available_queries}"
                ),
            }

        verified_query = self._verified_queries[verified_query_name]

        # Use the existing create_data_frame_from_sql method with the verified query's SQL
        return await self.create_data_frame_from_sql(
            sql_query=verified_query["sql"],
            new_data_frame_name=new_data_frame_name,
            new_data_frame_description=new_data_frame_description,
            num_samples=num_samples,
        )
