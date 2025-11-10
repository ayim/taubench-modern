# ruff: noqa: E501

from agent_platform.server.semantic_data_models.enhancer.type_defs import EnhancementMode


def render_system_prompt(  # noqa
    mode: EnhancementMode,
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
) -> str:
    # Note that the tables_to_enhance and table_to_columns_to_enhance must be used to
    # determine whether there will be a selection of tables or columns to enhance
    # in full mode (where tables and columns are enhanced together) or in table or column mode
    # (where only tables or only columns are enhanced respectively).

    # Determine if we're dealing with single or multiple items
    is_single_table = mode == "tables" and tables_to_enhance and len(tables_to_enhance) == 1
    is_single_column = (
        mode == "columns"
        and table_to_columns_to_enhance
        and sum(len(cols) for cols in table_to_columns_to_enhance.values()) == 1
    )
    is_multiple_columns = (
        mode == "columns"
        and table_to_columns_to_enhance
        and sum(len(cols) for cols in table_to_columns_to_enhance.values()) > 1
    )

    # Build the task description
    parts = ["You are an expert data analyst and semantic model designer.\n"]
    parts.append("\nYour task is to enhance a ")

    if mode == "full":
        parts.append("semantic data model")
    elif mode == "tables":
        if is_single_table:
            parts.append("SINGLE TABLE'S METADATA in a semantic data model")
        else:
            parts.append("TABLE METADATA in a semantic data model")
    elif mode == "columns":
        if is_single_column:
            parts.append("SINGLE COLUMN in a semantic data model")
        else:
            parts.append("MULTIPLE COLUMNS in a semantic data model")

    parts.append(" by improving:\n")

    # Add model-level information section
    if mode == "full":
        parts.append("\n**Model-Level Information:**\n")
        parts.append(
            "   - A descriptive, domain-specific name for the semantic model that clearly indicates\n"
        )
        parts.append(
            "     what business domain or data subject it represents (e.g., 'Product Catalog',\n"
        )
        parts.append(
            "     'Sales Analytics', 'Customer Orders', NOT generic names like 'Semantic Data Model')\n"
        )
        parts.append(
            "   - An improved description that explains the business purpose and use cases\n"
        )

    # Add table information section
    if mode in {"full", "tables"}:
        parts.append("\n**Table Information:**\n")
        if mode == "full":
            parts.append("For each table:\n")
        parts.append("   - Better logical name for the table\n")
        parts.append("   - Improved description that explains the purpose of the table\n")
        parts.append("   - Synonyms that users might use to refer to this table\n")

    # Add column information section
    if mode in {"full", "columns"}:
        parts.append("\n**Column Information:**\n")
        if mode == "full" or is_multiple_columns:
            parts.append("For each column:\n")
        parts.append("\n")
        parts.append("   - Better logical name for the column\n")
        parts.append("   - Improved description that explains what the data represents\n")
        parts.append("   - Synonyms that users might use to refer to this column\n")
        parts.append(
            '   - Proper categorization into "dimension", "fact", "metric", or "time_dimension"\n'
        )

    # Add categorization guidelines section
    if mode in {"full", "columns"}:
        parts.append("\n**Categorization Guidelines:**\n")
        parts.append("   - **dimension**: Categorical data used for grouping/filtering\n")
        parts.append("     (e.g., product_name, customer_id, region)\n")
        parts.append(
            "   - **fact**: Numeric measures at row level (e.g., quantity, price, revenue)\n"
        )
        parts.append(
            "   - **metric**: Aggregated business KPIs (e.g., total_revenue, avg_order_value)\n"
        )
        parts.append(
            "   - **time_dimension**: Temporal data for time-based analysis (e.g., order_date, created_at)\n"
        )

    # Add quality standards section
    parts.append("\n**Quality Standards:**\n")

    # Names (singular or plural)
    if mode == "full" or is_multiple_columns:
        parts.append("   - Names should be clear and descriptive\n")
    else:
        parts.append("   - Name should be clear and descriptive\n")

    # Descriptions text
    if mode == "full":
        description_text = "table's and columns' purposes"
    elif mode == "tables":
        description_text = "table's purpose"
    else:
        description_text = "column's purpose"
    parts.append(
        f"   - Descriptions should be concise but informative and explain the {description_text}\n"
    )

    # Synonyms guidance
    parts.append(
        "   - Synonyms should cover common alternative terms and be user friendly. Note that technical\n"
    )
    parts.append(
        "     terms can be used, but the context here is that non-technical users will be using\n"
    )

    # Reference text for synonyms
    if mode == "full":
        reference_text = "tables and columns"
    elif mode == "tables":
        reference_text = "tables"
    else:
        reference_text = "columns"
    parts.append(
        f"     the synonyms to reference the {reference_text} in a non-technical way using natural language.\n"
    )

    # Table synonyms examples
    if mode in {"full", "tables"}:
        parts.append("     Examples of synonyms for tables:\n")
        parts.append(
            '     - synonyms for orders_table: "orders", "customer orders", "order data"\n'
        )
        parts.append('     - synonyms for product_catalog: "products", "product list", "catalog"\n')
        parts.append(
            '     - synonyms for user_profiles: "users", "user data", "customer profiles"\n'
        )

    # Column synonyms examples
    if mode in {"full", "columns"}:
        parts.append("     Examples of synonyms for columns:\n")
        parts.append('     - synonyms for shipment_duration: "shipping time", "shipment time"\n')
        parts.append('     - synonyms for product_name: "product name", "product"\n')
        parts.append('     - synonyms for customer_id: "customer id", "customer"\n')
        parts.append('     - synonyms for net_revenue: "revenue after discount", "net sales"\n')
        parts.append('     - synonyms for qty_products: "quantity", "quantity of products"\n')
        parts.append('     - synonyms for dt_created: "created at", "created date"\n')
        parts.append('     - synonyms for total_amount: "total", "total amount"\n')
        parts.append("   - Categorization should be accurate based on the column information\n")

    # Add mode-specific instructions
    if mode == "full":
        parts.append("\n")
        parts.append(
            "You will receive the current semantic model and should return an enhanced version with improvements.\n"
        )
        parts.append(
            "Focus on making the model more useful so that later it's easier to generate SQL queries from natural\n"
        )
        parts.append("language based on the semantic data model.\n")
    elif mode == "tables":
        parts.append("\n")
        table_text = "table" if is_single_table else "table(s)"
        parts.append(
            "You will receive the full semantic model for context, but you should ONLY enhance the specific\n"
        )
        verb = "is" if is_single_table else "are"
        focus_text = "this single table" if is_single_table else "these tables"
        parts.append(
            f"{table_text} that {verb} highlighted. Focus on making {focus_text}'s metadata more useful so that later\n"
        )
        parts.append(
            "it's easier to generate SQL queries from natural language based on the semantic data model.\n"
        )
        parts.append("\n")
        parts.append(
            "**IMPORTANT:** You should NOT regenerate or modify any column information. Only provide metadata\n"
        )
        parts.append("for the table itself (name, description, synonyms).\n")
    elif mode == "columns":
        parts.append("\n")
        column_text = "column" if is_single_column else "columns"
        parts.append(
            "You will receive the full semantic model for context, but you should ONLY enhance the specific\n"
        )
        verb = "is" if is_single_column else "are"
        focus_text = "this single column" if is_single_column else "these columns"
        parts.append(
            f"{column_text} that {verb} highlighted. Focus on making {focus_text} more useful so that later it's\n"
        )
        parts.append(
            "easier to generate SQL queries from natural language based on the semantic data model.\n"
        )

    # Add tool usage instructions
    parts.append("\n**Output Instructions:**\n")
    parts.append(
        "Use the provided tool to submit your enhanced result. The tool will validate your output against\n"
    )
    parts.append(
        "the expected schema. If your first attempt has validation errors, you will be asked to correct them.\n"
    )

    return "".join(parts)
