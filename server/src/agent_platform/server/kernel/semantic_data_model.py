# ruff: noqa: E501
from __future__ import annotations

import typing
from collections.abc import Sequence
from textwrap import indent

from structlog import get_logger

if typing.TYPE_CHECKING:
    from typing import Any

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.semantic_data_model.types import (
        Relationship,
        SemanticDataModel,
        VerifiedQuery,
    )
    from agent_platform.core.semantic_data_model.validation import References
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelAndReferences,
    )
    from agent_platform.server.storage.base import BaseStorage


logger = get_logger(__name__)


async def get_semantic_data_model_name(
    data_frame: PlatformDataFrame,
    storage: BaseStorage,
    thread_id: str,
) -> str | None:
    """Get the semantic data model name used to create a data frame.

    This function extracts the semantic data model name from the data frame's
    computation_input_sources, checking both direct sources and recursive dependencies.
    When a source references another data frame, it will load and check that data frame.

    Args:
        data_frame: The data frame to analyze.
        storage: Storage instance for loading referenced data frames.
        thread_id: Thread ID for loading referenced data frames.

    Returns:
        The semantic data model name found in data frame's sources or dependencies.
        None if no semantic data model was used to create the data frame.
    """
    # Check direct computation_input_sources
    if data_frame.computation_input_sources:
        for source in data_frame.computation_input_sources.values():
            # Direct semantic data model source
            if source.source_type == "semantic_data_model" and source.semantic_data_model_name:
                return source.semantic_data_model_name

            # Data frame reference - need to load and check recursively
            if source.source_type == "data_frame":
                try:
                    # Load the referenced data frame
                    referenced_df = await storage.get_data_frame(
                        thread_id=thread_id,
                        data_frame_id=source.source_id,
                    )
                    # Recursively check the referenced data frame
                    sdm_name = await get_semantic_data_model_name(
                        referenced_df,
                        storage=storage,
                        thread_id=thread_id,
                    )
                    if sdm_name:
                        return sdm_name
                except Exception:
                    # If we can't load the referenced data frame, continue checking other sources
                    logger.exception(
                        f"Failed to load referenced data frame {source.source_id} "
                        f"when looking for semantic data model name"
                    )
                    continue

    return None


def get_semantic_data_model_tables(
    data_frame: PlatformDataFrame,
    sdm_name: str,
) -> list[str]:
    """Get the semantic data model table names used to create a data frame.

    This function extracts the logical table names from the data frame's
    computation_input_sources. These are the tables from the semantic data model
    that were actually used in the data frame's computation.

    Args:
        data_frame: The data frame to analyze.
        sdm_name: The SDM name to filter by. Only returns tables from this
            specific semantic data model.

    Returns:
        List of logical table names from the semantic data model.
        Empty list if no semantic data model tables were used.
    """
    table_names: list[str] = []

    for table_name, source in data_frame.computation_input_sources.items():
        if source.source_type != "semantic_data_model":
            continue

        # Filter by SDM name - only include tables from the specified SDM
        if source.semantic_data_model_name != sdm_name:
            continue

        # Add logical table name (which is the dict key)
        table_names.append(table_name)

    return table_names


async def get_dialect_from_semantic_data_model(
    semantic_data_model: SemanticDataModel,
    storage: BaseStorage,
) -> str | None:
    """Get SQL dialect from the semantic data model's data connections.

    Iterates through tables in the SDM to find the first available data connection
    and returns its engine type as the dialect.

    Args:
        semantic_data_model: The semantic data model to extract dialect from
        storage: Storage instance to fetch data connections

    Returns:
        SQL dialect string (e.g., 'postgres', 'snowflake', 'duckdb') or None if not found
    """
    tables = semantic_data_model.tables or []
    for table in tables:
        base_table = table.get("base_table")
        if base_table:
            data_connection_id = base_table.get("data_connection_id")
            if data_connection_id:
                try:
                    data_connection = await storage.get_data_connection(data_connection_id)
                    if data_connection:
                        return data_connection.engine
                except Exception:
                    # If we can't get the connection, continue to next table
                    logger.warning(
                        "Failed to fetch data connection", data_connection_id=data_connection_id, exc_info=True
                    )
                    continue
            elif "file_reference" in base_table:
                # File-based tables use DuckDB
                return "duckdb"
    return None


def infer_engine_for_semantic_model(
    references: References,
    data_connection_id_to_engine: dict[str, str],
) -> str:
    """Infer the SQL engine for a semantic data model based on its data connections.

    Args:
        references: The references from a semantic data model
        data_connection_id_to_engine: Mapping from data connection IDs to engine names

    Returns:
        The inferred engine name, defaulting to "duckdb" if multiple engines or none found
    """
    data_connection_ids = references.data_connection_ids
    if data_connection_ids:
        engines = {data_connection_id_to_engine.get(data_connection_id) for data_connection_id in data_connection_ids}
        engines.discard(None)
        if len(engines) == 1:
            engine = engines.pop()
            if engine:
                return engine
    # Fallback to duckdb if we have multiple engines
    return "duckdb"


def _format_table_field(k: str, v: Any) -> str:
    """Format a table field for display."""
    import yaml

    k = k.replace("_", " ").title()

    return f"{k}:\n{yaml.safe_dump(v, sort_keys=False)}"


def _format_columns(columns: list[dict], column_type: str, is_file_reference: bool = False) -> str:
    """Format columns with physical expressions as primary identifiers.

    Args:
        columns: List of column dictionaries (dimensions, facts, metrics, etc.)
        column_type: Type label for this column group
        is_file_reference: If True, format for file reference tables (use name, separate data_type line)

    Returns:
        Formatted string with physical-first column information
    """
    if not columns:
        return ""

    import yaml

    lines = [f"{column_type}:"]
    for original_col in columns:
        # Make a copy to avoid mutating the original
        col = original_col.copy()

        # Pop the column identifier and build the column dict
        if is_file_reference:
            # For file reference: use name, remove expr
            column_id = col.pop("name", "")
            col.pop("expr", None)  # Remove expr for file references
        else:
            # For data connection: use expr, remove name
            column_id = col.pop("expr", "")
            col.pop("name", None)  # Remove name for data connections

        # Start the column entry with the identifier
        lines.append(f"- name: {column_id}")

        # Use YAML to format remaining fields
        if col:
            yaml_output = yaml.safe_dump(col, sort_keys=False, default_flow_style=False)
            # Indent the YAML output by 2 spaces
            for line in yaml_output.rstrip().split("\n"):
                lines.append(f"  {line}")

    # Indent entire block by 1 space
    return "\n ".join(lines)


def _format_relationships(relationships: list[Relationship]) -> str:
    """Format relationships in the standardized JOIN guidance format.

    Args:
        relationships: List of relationship dictionaries from semantic data model

    Returns:
        Formatted relationship information matching the runbook format,
        or empty string if no valid relationships
    """
    if not relationships:
        return ""

    guidance_parts = []
    rel_idx = 0

    for rel in relationships:
        if not isinstance(rel, dict):
            continue

        rel_idx += 1

        rel_name = rel.get("name", "")
        left_table = rel.get("left_table", "")
        right_table = rel.get("right_table", "")
        rel_columns = rel.get("relationship_columns", [])

        if not left_table or not right_table or not rel_columns:
            continue

        # Format relationship header: "1. rel_name: left_table → right_table"
        rel_desc = f"{rel_idx}. {rel_name}: {left_table} → {right_table}"
        guidance_parts.append(rel_desc)

        # Format JOIN syntax: "   JOIN right_table ON join_clause"
        join_conditions = []
        for col_pair in rel_columns:
            if isinstance(col_pair, dict):
                left_col = col_pair.get("left_column", "")
                right_col = col_pair.get("right_column", "")
                if left_col and right_col:
                    join_conditions.append(f"{left_table}.{left_col} = {right_table}.{right_col}")

        if join_conditions:
            join_clause = " AND ".join(join_conditions)
            guidance_parts.append(f"   JOIN {right_table} ON {join_clause}")

    return "\n".join(guidance_parts)


def infer_engine_from_references(
    references: References,
    data_connections: list[DataConnection],
) -> str:
    """Infer SQL engine for a semantic data model from its references and data connections.

    This is a higher-level convenience function that handles the implementation details
    of building mappings and wrapper objects.

    Args:
        semantic_data_model: The semantic data model dict
        semantic_data_model_id: The ID of the semantic data model
        references: References extracted from the semantic data model
        data_connections: List of data connection objects from storage

    Returns:
        The inferred engine name (defaults to "duckdb" if multiple/no engines)
    """
    # Build data_connection_id_to_engine mapping
    data_connection_id_to_engine: dict[str, str] = {dc.id: dc.engine for dc in data_connections}

    return infer_engine_for_semantic_model(references, data_connection_id_to_engine)


def get_semantic_data_models_with_engines(
    semantic_data_models: list[SemanticDataModelAndReferences],
    data_connection_id_to_engine: dict[str, str],
) -> list[tuple[SemanticDataModel, str]]:
    """Process semantic data models and pair them with their inferred engines.

    Args:
        semantic_data_models: List of semantic data models with references
        data_connection_id_to_engine: Mapping from data connection IDs to engine names

    Returns:
        List of (processed_model, engine) tuples
    """
    from agent_platform.core.semantic_data_model.types import SemanticDataModel

    models_and_engines: list[tuple[SemanticDataModel, str]] = []
    if not semantic_data_models:
        return models_and_engines

    for semantic_data_model_and_refs in semantic_data_models:
        try:
            model_data = semantic_data_model_and_refs.semantic_data_model_info["semantic_data_model"]
            model = SemanticDataModel.model_validate(model_data)

            if not model.tables:
                continue  # No tables, so skip

            engine = infer_engine_for_semantic_model(
                semantic_data_model_and_refs.references, data_connection_id_to_engine
            )
            models_and_engines.append((model, engine))
        except Exception:
            logger.exception(
                "Error creating semantic data model summary from semantic data model info",
            )
            continue

    return models_and_engines


def summarize_data_models(models_and_engines: Sequence[tuple[SemanticDataModel, str]]) -> str:
    """Summarize a list of semantic data models."""
    if not models_and_engines:
        return "No semantic data models available."

    return "\n".join(summarize_data_model(model, engine) for model, engine in models_and_engines)


def summarize_data_model(
    model: SemanticDataModel,
    engine: str,
    table_names: list[str] | None = None,
) -> str:
    """Describe available semantic data models (structure only).

    Returns structural information with physical table/column names as primary
    identifiers. No SQL generation guidance.

    Args:
        model: The semantic data model to summarize
        engine: The SQL engine/dialect for this model (must be non-empty)
        table_names: Optional list of table names to include. If None, includes all tables.

    Returns:
        Formatted description of model structures with physical-first naming

    Raises:
        ValueError: If engine is empty or None
    """
    if not engine:
        raise ValueError("engine must be a non-empty string")

    result = []

    # Convert to dict to avoid mutating the input Pydantic model
    model_dict = model.model_dump()

    # Model header
    name = model_dict.pop("name", "Unnamed")
    description = model_dict.pop("description", "")

    model_header = f"### Model: {name}"
    if engine:
        model_header += f"\nSQL dialect: {engine}"
    if description:
        model_header += f"\nDescription: {description}"
    result.append(model_header)

    # Tables (structural information only)
    tables = model_dict.pop("tables", [])

    # Filter tables if specific names provided
    if table_names is not None:
        table_names_set = set(table_names)
        tables = [t for t in tables if isinstance(t, dict) and t.get("name") in table_names_set]
    if tables:
        for table in tables:
            if not isinstance(table, dict):
                continue

            t = table.copy()
            logical_table_name = t.pop("name", "")
            if not logical_table_name:
                continue

            # Extract physical table name from base_table
            base_table = t.pop("base_table", {})
            table_desc = t.pop("description", "")

            # Determine physical table name based on source type
            physical_table_name = None
            is_file_reference = False
            if base_table and isinstance(base_table, dict):
                # File-based tables: use table name as both display and physical name
                if base_table.get("file_reference"):
                    physical_table_name = logical_table_name
                    is_file_reference = True
                # Data connection tables: use base_table.table as physical name
                elif base_table.get("data_connection_id") or base_table.get("data_connection_name"):
                    physical_table_name = base_table.get("table")

            # Use physical table name as primary
            if physical_table_name:
                table_line = f"Table: {physical_table_name}"
            else:
                # Fallback: no base_table info provided
                table_line = f"Table: {logical_table_name}"

            if table_desc:
                table_line += f"\n Description: {table_desc}"
            result.append(table_line)

            # Format each column type explicitly with physical-first formatting
            from agent_platform.core.semantic_data_model.types import CATEGORIES

            for category in CATEGORIES:
                if columns := t.pop(category, None):
                    # Convert category name to title case for display
                    category_display = category.replace("_", " ").title()
                    result.append(indent(_format_columns(columns, category_display, is_file_reference), " "))

            # Handle any remaining fields (primary_key, filters, etc.) with old formatter
            for k, v in t.items():
                if v:
                    result.append(indent(_format_table_field(k, v), " "))

    # Pop verified_queries to remove them from the model dict (not included in summary)
    model_dict.pop("verified_queries", None)

    # Handle relationships - format conditionally based on feature flag
    relationships = model_dict.pop("relationships", [])
    from agent_platform.server.constants import SystemConfig

    if SystemConfig.enable_relationship_guidance and relationships:
        formatted_rels = _format_relationships(relationships)
        if formatted_rels:
            result.append("\n**Available Relationships:**\n")
            result.append(formatted_rels)

    # Handle what we haven't added yet (other fields)
    for k, v in model_dict.items():
        if v:
            result.append(_format_table_field(k, v))

    result.append("")  # Empty line at the end of this summary

    return "\n".join(result)


def summarize_verified_query(verified_query: VerifiedQuery) -> str:
    """Summarize a verified query for prompt context.

    Args:
        verified_query: The verified query to summarize

    Returns:
        Formatted string with query details including SQL, NLQ, name, and parameters
    """
    lines = [
        f"**Query Name:** {verified_query.name}",
        f"**Natural Language Question:** {verified_query.nlq}",
        f"**SQL:** {verified_query.sql}",
    ]

    # Format parameters
    parameters = verified_query.parameters or []
    if parameters:
        lines.append("\n**Parameters:**")
        for param in parameters:
            name = param.name
            data_type = param.data_type
            example = param.example_value
            description = param.description or "(no description)"

            lines.append(f"- **{name}** ({data_type})")
            lines.append(f"  - Example value: {example}")
            lines.append(f"  - Description: {description}")
    else:
        lines.append("\n**Parameters:** No parameters")

    return "\n".join(lines)
