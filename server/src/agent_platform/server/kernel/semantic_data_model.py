# ruff: noqa: E501
from __future__ import annotations

import typing

from agent_platform.core.data_frames.semantic_data_model_types import VerifiedQuery

if typing.TYPE_CHECKING:
    from typing import Any

    from agent_platform.core.data_frames.semantic_data_model_types import (
        Relationship,
        SemanticDataModel,
    )


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
    relationships, verified queries. No SQL generation guidance.

    Args:
        models_and_engines: List of (semantic_data_model, engine) tuples

    Returns:
        Formatted description of model structures
    """
    import textwrap
    from textwrap import indent

    if not models_and_engines:
        return "No semantic data models available."

    verified_queries: list[VerifiedQuery] = []
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

        verified_queries.extend(model.pop("verified_queries", None) or ())

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

    # Add verified queries
    if verified_queries:
        # Import here to avoid circular dependency
        from agent_platform.server.kernel.data_frames import (
            DF_CREATE_FROM_VERIFIED_QUERY_TOOL_NAME,
        )

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
