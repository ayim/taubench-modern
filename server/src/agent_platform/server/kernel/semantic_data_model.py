# ruff: noqa: E501
from __future__ import annotations

import typing

from agent_platform.core.data_frames.semantic_data_model_types import VerifiedQuery

if typing.TYPE_CHECKING:
    from typing import Any

    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel


def _format_table_field(k: str, v: Any) -> str:
    """Format a table field for display."""
    k = k.replace("_", " ").title()

    import yaml

    return f"{k}:\n{yaml.safe_dump(v, sort_keys=False)}"


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

        # Handle what we haven't added yet (relationships, etc.)
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
