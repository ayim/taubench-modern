# ruff: noqa: E501
from __future__ import annotations

import typing

from structlog import get_logger

logger = get_logger(__name__)

if typing.TYPE_CHECKING:
    from typing import Any

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.data_frames.semantic_data_model_types import (
        Relationship,
        SemanticDataModel,
    )
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelAndReferences,
    )


async def get_semantic_data_model_name(data_frame: PlatformDataFrame) -> str | None:
    """Get the semantic data model name used to create a data frame.

    This function extracts the semantic data model name directly from the data frame's
    computation_input_sources. The SDM name is stored when the data frame is created.

    Args:
        data_frame: The data frame to analyze.

    Returns:
        The semantic data model name found in data frame's computation_input_sources.
        None if no semantic data model was used to create the data frame.
    """
    for source in data_frame.computation_input_sources.values():
        if source.source_type == "semantic_data_model" and source.semantic_data_model_name:
            return source.semantic_data_model_name
    return None


def infer_engine_for_semantic_model(
    semantic_data_model_and_refs: SemanticDataModelAndReferences,
    data_connection_id_to_engine: dict[str, str],
) -> str:
    """Infer the SQL engine/dialect for a semantic data model.

    Determines the appropriate SQL dialect based on the data connections
    used by the semantic data model.

    Args:
        semantic_data_model_and_refs: The semantic data model with its references
        data_connection_id_to_engine: Mapping from data connection IDs to engine names

    Returns:
        The inferred engine name (e.g., 'postgres', 'snowflake', 'duckdb')
        Defaults to 'duckdb' if multiple engines or no engines found
    """
    data_connection_ids = semantic_data_model_and_refs.references.data_connection_ids
    if data_connection_ids:
        engines = {data_connection_id_to_engine.get(data_connection_id) for data_connection_id in data_connection_ids}
        engines.discard(None)
        if len(engines) == 1:
            engine = engines.pop()
            if engine:
                return engine
    # Fallback to duckdb if we have multiple engines
    return "duckdb"


def get_semantic_data_models_with_engines(
    semantic_data_models: list[SemanticDataModelAndReferences],
    data_connection_id_to_engine: dict[str, str],
) -> list[tuple[SemanticDataModel, str]]:
    """Extract and prepare semantic data models with their inferred engines.

    Processes semantic data models to extract table information and determine
    the appropriate SQL engine for each model.

    Args:
        semantic_data_models: List of semantic data models with their references
        data_connection_id_to_engine: Mapping from data connection IDs to engine names

    Returns:
        List of tuples containing (semantic_data_model, engine_name)
        Only includes models that have tables defined
    """
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

    models_and_engines: list[tuple[SemanticDataModel, str]] = []
    if not semantic_data_models:
        return models_and_engines

    for semantic_data_model_and_refs in semantic_data_models:
        try:
            model: SemanticDataModel = semantic_data_model_and_refs.semantic_data_model_info["semantic_data_model"]
            new_model: SemanticDataModel = typing.cast(SemanticDataModel, {x: y for x, y in model.items() if y})

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

            engine = infer_engine_for_semantic_model(semantic_data_model_and_refs, data_connection_id_to_engine)
            models_and_engines.append((new_model, engine))
        except Exception:
            logger.exception(
                "Error creating semantic data model summary from semantic data model info",
                semantic_data_model_and_refs=semantic_data_model_and_refs,
            )
            continue

    return models_and_engines


def _format_table_field(k: str, v: Any) -> str:
    """Format a table field for display."""
    k = k.replace("_", " ").title()

    import yaml

    return f"{k}:\n{yaml.safe_dump(v, sort_keys=False)}"


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


def summarize_data_models(models_and_engines: list[tuple[SemanticDataModel, str]]) -> str:
    """Describe available semantic data models (structure only).

    Returns pure structural information: model names, tables, columns,
    and relationships. No SQL generation guidance.

    Args:
        models_and_engines: List of (semantic_data_model, engine) tuples

    Returns:
        Formatted description of model structures
    """
    from textwrap import indent

    if not models_and_engines:
        return "No semantic data models available."

    result = []

    for model, engine in models_and_engines:
        if not isinstance(model, dict):
            continue

        # Make a copy to avoid mutating the input
        model = model.copy()  # noqa: PLW2901

        # Model header
        name = model.pop("name", "Unnamed")
        description = model.pop("description", "")

        model_header = f"### Model: {name}"
        model_header += f"\nSQL dialect: {engine}"
        if description:
            model_header += f"\nDescription: {description}"
        result.append(model_header)

        # Tables (structural information only)
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
                        result.append(indent(_format_table_field(k, v), " "))

        # Pop verified_queries to remove them from the model dict (not included in summary)
        model.pop("verified_queries", None)

        # Handle relationships - format conditionally based on feature flag
        relationships = model.pop("relationships", [])
        from agent_platform.server.constants import SystemConfig

        if SystemConfig.enable_relationship_guidance and relationships:
            formatted_rels = _format_relationships(relationships)
            if formatted_rels:
                result.append("\n**Available Relationships:**\n")
                result.append(formatted_rels)

        # Handle what we haven't added yet (other fields)
        for k, v in model.items():
            if v:
                result.append(_format_table_field(k, v))

        result.append("")  # Empty line between models

    return "\n".join(result)
