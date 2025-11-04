# ruff: noqa: E501


def render_quality_check_user_prompt(
    enhanced_model: str,
    mode: str = "full",
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
) -> str:
    """Render the quality check user prompt template.

    Args:
        enhanced_model: The enhanced semantic data model to review.
        mode: The enhancement mode (full, tables, or columns).
        tables_to_enhance: The names of the tables that were enhanced (for tables/full mode).
        table_to_columns_to_enhance: Map of table names to column names that were enhanced (for columns/full mode).

    Returns:
        The rendered quality check user prompt.
    """
    # Build scope description
    scope_text = ""
    if mode == "tables" and tables_to_enhance:
        table_list = ", ".join(f'"{t}"' for t in sorted(tables_to_enhance))
        scope_text = f"\n\nScope: Only the following table(s) were enhanced:\n  - {table_list}\n\nOther tables/columns may not have complete enhancements.\n"
    elif mode == "columns" and table_to_columns_to_enhance:
        scope_parts = []
        for table_name, columns in sorted(table_to_columns_to_enhance.items()):
            column_list = ", ".join(f'"{c}"' for c in sorted(columns))
            scope_parts.append(f'  - Table "{table_name}": {column_list}')
        scope_text = (
            "\n\nScope: Only the following column(s) were enhanced:\n"
            + "\n".join(scope_parts)
            + "\n\nOther tables/columns may not have complete enhancements.\n"
        )
    elif mode == "full" and (tables_to_enhance or table_to_columns_to_enhance):
        # Partial full mode enhancement
        scope_parts = []

        if tables_to_enhance:
            table_list = "\n    - ".join(f'"{t}"' for t in sorted(tables_to_enhance))
            scope_parts.append(f"  Tables:\n    - {table_list}")

        if table_to_columns_to_enhance:
            col_lines = []
            for table_name, columns in sorted(table_to_columns_to_enhance.items()):
                column_list = ", ".join(f'"{c}"' for c in sorted(columns))
                col_lines.append(f'    - Table "{table_name}": {column_list}')
            scope_parts.append("  Columns:\n" + "\n".join(col_lines))

        scope_text = (
            "\n\nScope: The following item(s) were enhanced:\n"
            + "\n".join(scope_parts)
            + "\n\nOther tables/columns may not have complete enhancements.\n"
        )

    return f"""
Please review this enhanced semantic data model and determine if there are additional improvements needed:{scope_text}
```json
{enhanced_model}
```

Use the `provide_quality_response` tool to respond:
- If the enhancements are good enough, call the tool with `passed=true`
- If improvements are needed, call the tool with `passed=false` and provide a detailed `improvement_request` explaining what needs to be improved

"""
