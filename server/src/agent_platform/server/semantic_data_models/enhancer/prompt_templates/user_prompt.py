# ruff: noqa: E501

from __future__ import annotations

import json
import typing

if typing.TYPE_CHECKING:
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        EnhancementMode,
        SemanticDataModelForLLM,
    )


def render_user_prompt(  # noqa
    mode: EnhancementMode,
    current_semantic_model: SemanticDataModelForLLM,
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    data_connection_tables: set[str] | None = None,
) -> str:
    """Render the user prompt template with the given parameters."""
    semantic_model_json = json.dumps(current_semantic_model.model_dump(), indent=2)

    # Build the opening line
    if mode == "full":
        if not tables_to_enhance and not table_to_columns_to_enhance:
            opening = "Please improve the following semantic data model by improving table and column information."
        else:
            # Build specific enhancement requests
            parts = []
            if tables_to_enhance:
                if len(tables_to_enhance) == 1:
                    table_name = next(iter(tables_to_enhance))
                    parts.append(f'table "{table_name}"')
                else:
                    tables_list = ", ".join(f'"{t}"' for t in sorted(tables_to_enhance))
                    parts.append(f"tables {tables_list}")

            if table_to_columns_to_enhance:
                col_parts = []
                for table_name, columns in sorted(table_to_columns_to_enhance.items()):
                    if len(columns) == 1:
                        col_parts.append(f'column "{columns[0]}" in table "{table_name}"')
                    else:
                        cols_list = ", ".join(f'"{c}"' for c in columns)
                        col_parts.append(f'columns {cols_list} in table "{table_name}"')
                parts.append(", ".join(col_parts))

            items_text = ", ".join(parts)
            opening = f"Please improve the following specific {items_text} in the semantic data model while maintaining context."
    elif mode == "tables":
        if tables_to_enhance and len(tables_to_enhance) == 1:
            table_name = next(iter(tables_to_enhance))
            opening = f'Please improve ONLY the table metadata for table "{table_name}" within the following semantic data model.'
        else:
            tables_list = ", ".join(f'"{t}"' for t in sorted(tables_to_enhance or []))
            opening = f"Please improve ONLY the table metadata for tables {tables_list} within the following semantic data model."
    elif mode == "columns":
        if table_to_columns_to_enhance:
            items = []
            for table_name, columns in sorted(table_to_columns_to_enhance.items()):
                if len(columns) == 1:
                    items.append(f'column "{columns[0]}" in table "{table_name}"')
                else:
                    cols_list = ", ".join(f'"{c}"' for c in columns)
                    items.append(f'columns {cols_list} in table "{table_name}"')
            opening = f"Please improve ONLY the {', '.join(items)} within the following semantic data model."
        else:
            opening = "Please improve ONLY the specified columns within the following semantic data model."
    else:
        opening = "Please improve the following semantic data model."

    # Build the semantic model section
    if mode == "full":
        model_header = "**Current Semantic Data Model:**"
    else:
        model_header = "**Full Semantic Data Model (for context):**"

    # Build the target section
    target_section = ""
    if mode == "full":
        if tables_to_enhance or table_to_columns_to_enhance:
            target_section = "**Target Items to Enhance:**\n"
            # Track which tables have columns to avoid duplication
            tables_with_columns = set(
                table_to_columns_to_enhance.keys() if table_to_columns_to_enhance else []
            )

            # First, list tables that don't have columns (standalone tables)
            if tables_to_enhance:
                for table_name in sorted(tables_to_enhance):
                    if table_name not in tables_with_columns:
                        target_section += f"- Table: {table_name}\n"

            # Then, list tables with their columns grouped together
            if table_to_columns_to_enhance:
                for table_name, columns in sorted(table_to_columns_to_enhance.items()):
                    target_section += f"- Table: {table_name}\n"
                    for column_name in sorted(columns):
                        target_section += f"  - Column: {column_name}\n"
    elif mode == "tables":
        if tables_to_enhance:
            if len(tables_to_enhance) == 1:
                table_name = next(iter(tables_to_enhance))
                target_section = f"**Target Table to Enhance:**\n- Table: {table_name}\n"
            else:
                target_section = "**Target Tables to Enhance:**\n"
                for table_name in sorted(tables_to_enhance):
                    target_section += f"- Table: {table_name}\n"
    elif mode == "columns":
        if table_to_columns_to_enhance:
            target_section = "**Target Columns to Enhance:**\n"
            for table_name, columns in sorted(table_to_columns_to_enhance.items()):
                target_section += f"- Table: {table_name}\n"
                for column_name in sorted(columns):
                    target_section += f"  - Column: {column_name}\n"

    # Build enhancement requirements
    requirements = "**Enhancement Requirements:**\n\n"
    if mode == "full":
        requirements += "**For the semantic model:**\n"
        requirements += (
            "   - Choose a domain-specific name that reflects what the data represents\n"
        )
        requirements += (
            "     (e.g., 'Product Catalog', 'Sales Transactions', 'Customer Database')\n"
        )
        requirements += "   - Do NOT use generic names like 'Semantic Data Model' or 'Data Model'\n"
        requirements += "   - Add/improve the description explaining the business purpose and analytical use cases\n"
        requirements += "\n"
    if mode in {"full", "tables"}:
        table_text = "each table" if mode == "full" else "the specified table(s)"
        requirements += f"**For {table_text}:**\n"
        if data_connection_tables:
            requirements += "   - Improve the logical name (EXCEPT for data connection tables - keep their names unchanged)\n"
        else:
            requirements += "   - Improve the logical name\n"
        requirements += "   - Add/improve the description explaining the table's purpose\n"
        requirements += (
            "   - Add/change relevant synonyms that users might use to improve discoverability\n"
        )
        if data_connection_tables:
            tables_list = ", ".join(sorted(data_connection_tables))
            requirements += f"   - Data connection tables: {tables_list}\n"

    if mode in {"full", "columns"}:
        column_text = "each column" if mode == "full" else "the specified column(s)"
        requirements += f"\n**For {column_text}:**\n"
        if data_connection_tables:
            requirements += "   - Improve the logical name (EXCEPT for data connection tables - keep their names unchanged)\n"
        else:
            requirements += "   - Improve the logical name\n"
        requirements += "   - Add/improve the description explaining what the data represents\n"
        requirements += (
            "   - Add/change relevant synonyms that users might use to improve discoverability\n"
        )
        requirements += (
            "   - Ensure proper categorization (dimension, fact, metric, time_dimension)\n"
        )
        requirements += "     (the initial categorization should be treated as a hint)\n"

    # Build output format section
    output_format = "**Output Format:**\n"
    output_format += "   Use the provided tool to return your enhanced result. The tool will validate your output.\n"

    # Build important section
    important = "**Important:**\n"
    important += "- Ensure all synonyms are unique across the model\n"
    important += "- Make names SQL-safe (no spaces, special characters)\n"

    if mode == "tables":
        important += "- Output ONLY the enhanced table metadata (no column information)\n"
    elif mode == "columns":
        important += "- Output ONLY the enhanced column(s)\n"

    important += "- The tool will validate your output against the expected JSON schema\n"

    # Combine all sections
    prompt = f"""{opening}

{model_header}
```json
{semantic_model_json}
```

{target_section}{requirements}

{output_format}

{important}"""

    return prompt
