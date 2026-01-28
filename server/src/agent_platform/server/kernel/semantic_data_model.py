# ruff: noqa: E501
from __future__ import annotations

import typing

from structlog import get_logger

if typing.TYPE_CHECKING:
    from typing import Any

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.data_frames.semantic_data_model_types import (
        Relationship,
        SemanticDataModel,
    )
    from agent_platform.core.data_frames.semantic_data_model_validation import References
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelAndReferences,
    )


logger = get_logger(__name__)


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
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

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


def summarize_data_models(models_and_engines: list[tuple[SemanticDataModel, str]]) -> str:
    """Summarize a list of semantic data models."""
    if not models_and_engines:
        return "No semantic data models available."

    return "\n".join(summarize_data_model(model, engine) for model, engine in models_and_engines)


def summarize_data_model(model: SemanticDataModel, engine: str) -> str:
    """Describe available semantic data models (structure only).

    Returns pure structural information: model names, tables, columns,
    and relationships. No SQL generation guidance.

    Args:
        models_and_engines: List of (semantic_data_model, engine) tuples

    Returns:
        Formatted description of model structures
    """
    from textwrap import indent

    from agent_platform.core.data_frames.semantic_data_model_types import VerifiedQuery

    verified_queries: list[VerifiedQuery] = []
    result = []

    # Convert to dict to avoid mutating the input Pydantic model
    model_dict = model.model_dump()

    # Model header
    name = model_dict.pop("name", "Unnamed")
    description = model_dict.pop("description", "")

    model_header = f"### Model: {name}"
    model_header += f"\nSQL dialect: {engine}"
    if description:
        model_header += f"\nDescription: {description}"
    result.append(model_header)

    # Tables (structural information only)
    tables = model_dict.pop("tables", [])
    if tables:
        for table in tables:
            if not isinstance(table, dict):
                continue

            t = table.copy()
            table_name = t.pop("name")
            if not table_name:
                continue
            t.pop("base_table", None)  # Don't display base_table details
            table_desc = t.pop("description", "")

            table_line = f"Table: {table_name}"
            if table_desc:
                table_line += f"\n Description: {table_desc}"
            result.append(table_line)

            for k, v in t.items():
                if v:
                    result.append(indent(_format_table_field(k, v), " "))

    # Pop verified_queries to remove them from the model dict (not included in summary)
    verified_queries.extend(model_dict.pop("verified_queries", None) or ())
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
