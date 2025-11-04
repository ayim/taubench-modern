# ruff: noqa: E501

from __future__ import annotations

import json
import typing

if typing.TYPE_CHECKING:
    from agent_platform.server.semantic_data_models.enhancer.prompts import EnhancementMode
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        SemanticDataModelForLLM,
    )


def render_user_prompt(  # noqa
    mode: EnhancementMode,
    current_semantic_model: SemanticDataModelForLLM,
    output_schema: str,
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
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
    if mode in {"full", "tables"}:
        table_text = "each table" if mode == "full" else "the specified table(s)"
        requirements += f"**For {table_text}:**\n"
        requirements += "   - Improve the logical name\n"
        requirements += "   - Add/improve the description explaining the table's purpose\n"
        requirements += (
            "   - Add/change relevant synonyms that users might use to improve discoverability\n"
        )

    if mode in {"full", "columns"}:
        column_text = "each column" if mode == "full" else "the specified column(s)"
        requirements += f"\n**For {column_text}:**\n"
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
    if mode != "full":
        output_format += "   Return ONLY "
    else:
        output_format += "   Return "

    if mode == "tables":
        output_format += "the enhanced table metadata"
    elif mode == "columns":
        output_format += "the enhanced column(s)"
    else:
        output_format += "the enhanced"

    output_format += " in JSON structure, but with improved:\n"

    name_text = "fields" if mode == "full" else "field"
    output_format += (
        f"   - `name` {name_text} (better logical name{'s' if mode == 'full' else ''})\n"
    )
    output_format += "   - `description` fields (clear, descriptive and concise descriptions)\n"

    synonyms_text = "fields" if mode == "full" else "field"
    output_format += (
        f"   - `synonyms` {synonyms_text} (relevant alternative terms to improve discoverability,\n"
    )
    output_format += "      make them user friendly"
    if mode in {"full", "columns"}:
        output_format += " and consider the units of the data if applicable"
    output_format += ")\n"

    if mode in {"full", "columns"}:
        output_format += "   - Proper categorization of columns into `dimensions`, `facts`, `metrics`, `time_dimensions`\n"

    output_format += "   - Optional fields that haven't changed should be ommitted in the output.\n"
    if mode in {"full", "columns"}:
        output_format += "   - The `sample_values` field should always be ommitted in the output.\n"

    # Build important section
    important = "**Important:**\n"
    important += "- Ensure all synonyms are unique across the model\n"
    important += "- Make names SQL-safe (no spaces, special characters)\n"

    if mode == "tables":
        important += "- Output ONLY the enhanced table metadata in JSON format\n"
        important += "- DO NOT include any column information\n"
    elif mode == "columns":
        important += "- Output ONLY the enhanced column(s) in JSON format\n"

    important += "- Output the JSON in the following format:\n"
    if mode == "full":
        important += " <semantic-data-model>...</semantic-data-model>\n"
    elif mode == "tables":
        important += " <table>...</table>\n"
    elif mode == "columns":
        important += " <column>...</column>\n"

    important += ".\n"
    important += "- Do not include any other text except the\n"
    if mode == "full":
        important += " <semantic-data-model>...</semantic-data-model>\n"
    elif mode == "tables":
        important += " <table>...</table>\n"
    elif mode == "columns":
        important += " <column>...</column>\n"
    important += " block.\n"

    must_text = "be the semantic data model in JSON format and MUST " if mode == "full" else ""
    important += f"- The output MUST {must_text}match the JSON schema below:\n\n"
    important += output_schema

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
