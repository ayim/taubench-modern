"""Functions to assist in parsing LLM responses for the Semantic Data Model Enhancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from agent_platform.server.semantic_data_models.enhancer.type_defs import (
    ColumnForLLM,
    LLMOutputSchemas,
)

if TYPE_CHECKING:
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.responses.content import ResponseToolUseContent
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.server.semantic_data_models.enhancer.prompts import EnhancementMode
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        Category,
        SemanticDataModelForLLM,
        TablesOutputSchema,
        TableToColumnsOutputSchema,
    )


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def get_tool_use_content(response: ResponseMessage) -> ResponseToolUseContent | None:
    """Extract ResponseToolUseContent from response without validation.

    Args:
        response: The ResponseMessage to extract from.

    Returns:
        The first ResponseToolUseContent found, or None if not present.
    """
    from agent_platform.core.responses.content import ResponseToolUseContent

    if not response.content:
        return None

    for content in response.content:
        if isinstance(content, ResponseToolUseContent):
            return content

    return None


def extract_tool_use_content(response: ResponseMessage) -> dict[str, Any]:
    """Extract and validate tool use content from the response.

    Args:
        response: The ResponseMessage to extract from.

    Returns:
        The tool input as a dictionary.

    Raises:
        EmptyResponseError: If response has no content
        NoToolCallError: If no tool call is found
        SchemaValidationError: If tool input is invalid
    """
    from agent_platform.server.semantic_data_models.enhancer.errors import (
        EmptyResponseError,
        EmptyToolInputError,
        NoToolCallError,
    )

    if not response.content:
        improvement_msg = (
            "Your response had no content. Please provide the enhanced data "
            "by calling the appropriate tool with the required parameters."
        )
        logger.error("Response had no content")
        raise EmptyResponseError(improvement_msg, response_message=response)

    tool_use_content = get_tool_use_content(response)

    if not tool_use_content:
        # No tool call found - this is a failure
        improvement_msg = (
            "Your response must use the provided tool to submit your enhancement. "
            "Please call the appropriate enhancement tool with your enhanced semantic data model."
        )
        logger.error("No tool call found in response")
        raise NoToolCallError(improvement_msg, response_message=response)

    # Validate tool input
    tool_input = tool_use_content.tool_input
    if not tool_input:
        improvement_msg = (
            "Your tool call had empty input. Please provide the enhanced data "
            "by calling the tool with the required parameters."
        )
        logger.error("Tool call had empty input")
        raise EmptyToolInputError(improvement_msg, response_message=response)

    return tool_input


def validate_and_parse_llm_response(
    response: ResponseMessage,
    mode: EnhancementMode = "full",
) -> LLMOutputSchemas:
    """
    Validate and parse the LLM response based on the mode.

    Args:
        response: The ResponseMessage from the LLM
        mode: The prompt mode (full, table, or column)

    Returns:
        - For "full" mode: SemanticDataModelForLLM
        - For "table" mode: LogicalTableMetadata
        - For "column" mode: Column

    Raises:
        EmptyResponseError: If response has no content or no tool call
        SchemaValidationError: If tool call doesn't match expected schema
    """
    from agent_platform.server.semantic_data_models.enhancer.errors import (
        SchemaValidationError,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        SemanticDataModelForLLM,
        TablesOutputSchema,
        TableToColumnsOutputSchema,
    )

    # Extract and validate tool use content
    tool_input = extract_tool_use_content(response)

    # Validate against schema based on mode
    try:
        if mode == "full":
            parsed_result = SemanticDataModelForLLM.model_validate(tool_input)
        elif mode == "tables":
            parsed_result = TablesOutputSchema.model_validate(tool_input)
        elif mode == "columns":
            parsed_result = TableToColumnsOutputSchema.model_validate(tool_input)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        return parsed_result
    except Exception as e:
        improvement_msg = (
            f"Your tool call parameters don't match the expected schema. Error: {e}.\n\n"
            "Please review the tool schema and ensure all required fields "
            "are present with the correct types and structure."
        )
        logger.error(f"Tool call schema validation error: {e}\nTool input: {tool_input}")
        raise SchemaValidationError(improvement_msg, response_message=response) from e


def update_semantic_data_model_with_semantic_data_model_from_llm(
    semantic_data_model: SemanticDataModel,
    semantic_data_model_for_llm: SemanticDataModelForLLM,
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
) -> None:
    """
    Update the semantic data model with the semantic data model for LLM.

    We should go over the changes and update the references in the existing semantic data model.

    The references are:
    - A table should be referenced by the `base_table.schema` and `base_table.table` fields to
      update the synonyms, description and name accordingly.
    - A column should be referenced by the table + the `expr` field to update accordingly.
    - A table may be moved from one group (dimensions, facts, time_dimensions, metrics) to another
      based on the category found for the column.

    While doing this we should also collect possible errors in a list.

    Some possible errors are:
    - If a table in semantic_data_model_for_llm does not have a reference, we should add an error
      saying so (and skip it).
    - If a column in semantic_data_model_for_llm does not have a reference, we should add an error
      saying so (and skip it).

    At the end, we should not have any additional tables or columns (but all existing ones
    should be updated and put in the correct group).
    """
    errors = []

    # Update semantic model name and description
    if semantic_data_model_for_llm.name:
        semantic_data_model["name"] = semantic_data_model_for_llm.name
    if semantic_data_model_for_llm.description is not None:
        semantic_data_model["description"] = semantic_data_model_for_llm.description

    # Get existing tables from the semantic data model
    existing_tables = semantic_data_model.get("tables") or []

    # Create a mapping of (schema, table) -> existing table for quick lookup
    existing_table_map = {}
    for table in existing_tables:
        base_table = table.get("base_table", {})
        schema = base_table.get("schema")
        table_name = base_table.get("table")
        if table_name:
            key = (schema, table_name)
            existing_table_map[key] = table

    # Process each table from the LLM model
    llm_tables = semantic_data_model_for_llm.tables or []
    for llm_table in llm_tables:
        base_table = llm_table.base_table
        schema = base_table.schema
        table_name = base_table.table

        # Find the corresponding existing table
        key = (schema, table_name)
        existing_table = existing_table_map.get(key)

        if not existing_table:
            errors.append(
                f"Table with schema '{schema}' and table '{table_name}' not found in existing semantic data model"
            )
            continue

        # Check if we should update this table based on tables_to_enhance filter
        logical_table_name = existing_table.get("name")
        # Process table if it's in tables_to_enhance OR has columns in table_to_columns_to_enhance
        should_process_table = (
            tables_to_enhance is None
            or logical_table_name in tables_to_enhance
            or (table_to_columns_to_enhance is not None and logical_table_name in table_to_columns_to_enhance)
        )
        if not should_process_table:
            continue

        # Determine if we should update table metadata
        # If the table is only specified in table_to_columns_to_enhance (not in tables_to_enhance),
        # we should only update columns, not the table's metadata
        should_update_table_metadata = tables_to_enhance is None or logical_table_name in tables_to_enhance

        # Update table properties only if appropriate
        if should_update_table_metadata:
            if llm_table.name:
                existing_table["name"] = llm_table.name
            if llm_table.description is not None:
                existing_table["description"] = llm_table.description
            if llm_table.synonyms is not None:
                existing_table["synonyms"] = llm_table.synonyms

        # Process columns from the LLM model
        if llm_table.columns:
            _update_table_columns(
                existing_table,
                llm_table.columns,
                errors,
                logical_table_name,
                table_to_columns_to_enhance,
            )

    # Check for tables in LLM model that weren't found in existing model
    llm_table_keys = set()
    for llm_table in llm_tables:
        base_table = llm_table.base_table
        key = (base_table.schema, base_table.table)
        llm_table_keys.add(key)

    # Report any tables that were in LLM model but not found in existing model
    for key in llm_table_keys:
        if key not in existing_table_map:
            schema, table_name = key
            errors.append(
                f"Table with schema '{schema}' and table '{table_name}' from LLM model "
                "not found in existing semantic data model"
            )


def _update_table_columns(
    existing_table: dict,
    llm_columns: list[ColumnForLLM],
    errors: list,
    logical_table_name: str | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
) -> None:
    """Update table columns based on LLM model columns."""
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        CATEGORY_TO_COLUMN_GROUP,
    )

    # Get all existing columns from all groups
    all_existing_columns = []

    for group in CATEGORY_TO_COLUMN_GROUP.values():
        columns = existing_table.get(group) or []
        for col in columns:
            col["_group"] = group  # Track which group it came from
            all_existing_columns.append(col)

    # Create a mapping of (expr) -> existing column for quick lookup
    existing_column_map = {}
    for col in all_existing_columns:
        expr = col.get("expr")
        if expr:
            existing_column_map[expr] = col

    # Get the set of columns to enhance for this table, if filtering is enabled
    columns_to_enhance_for_table: set[str] | None = None
    if table_to_columns_to_enhance is not None and logical_table_name is not None:
        columns_to_enhance_for_table = set(table_to_columns_to_enhance.get(logical_table_name, []))

    # Process each column from the LLM model
    for llm_column in llm_columns:
        # Check if we should update this column based on table_to_columns_to_enhance filter
        if columns_to_enhance_for_table is not None:
            # Match by expr (database column name), not logical name
            # because table_to_columns_to_enhance is populated with expr values
            if llm_column.expr not in columns_to_enhance_for_table:
                continue

        expr = llm_column.expr

        # Find the corresponding existing column
        existing_column = existing_column_map.get(expr)

        if not existing_column:
            errors.append(f"Column with expr '{expr}' not found in existing semantic data model")
            continue

        # Update column properties
        if llm_column.name:
            existing_column["name"] = llm_column.name
        if llm_column.description is not None:
            existing_column["description"] = llm_column.description
        if llm_column.synonyms is not None:
            existing_column["synonyms"] = llm_column.synonyms

        # Check if column needs to be moved to a different group based on category
        current_group = existing_column.get("_group")
        target_group = _get_target_group_for_category(llm_column.category)

        if current_group != target_group:
            # Remove from current group
            current_group_columns = existing_table.get(current_group, [])
            current_group_columns.remove(existing_column)

            # Add to target group
            if target_group not in existing_table:
                existing_table[target_group] = []
            existing_table[target_group].append(existing_column)

    # Remove the temporary _group field
    for column in all_existing_columns:
        column.pop("_group", None)

    # Clean up empty groups
    for group in CATEGORY_TO_COLUMN_GROUP.values():
        if group in existing_table and not existing_table[group]:
            del existing_table[group]


def _get_target_group_for_category(category: Category | None) -> str:
    """Get the target group name for a given category."""
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        CATEGORY_TO_COLUMN_GROUP,
    )

    if category is None:
        category = "dimension"
    return CATEGORY_TO_COLUMN_GROUP[category]


def update_tables_metadata_in_semantic_model(
    semantic_model: SemanticDataModel,
    table_metadata: TablesOutputSchema,
    tables_to_enhance: set[str] | None = None,
) -> None:
    """
    Update the table metadata for the provided tables in the semantic data model.

    If a table cannot be found, we skip it and log a warning.

    NOTE: This function matches tables based only on (schema, table) because the LLM
    enhancement process strips database information. For multi-database semantic data
    models where tables from different databases have the same schema.table name,
    this function will match the first table found and may produce incorrect results.

    Args:
        semantic_model: The original semantic model.
        table_metadata: The table metadata schema containing a list of tables to update.
        tables_to_enhance: Optional set of table names to enhance.
    """
    # Get all tables from the semantic model
    all_tables = semantic_model.get("tables") or []

    # Iterate over each table in the enhanced metadata
    for enhanced_table in table_metadata.tables or []:
        # Match on (schema, table) only since LLM doesn't return database info
        matches = []
        for existing_table in all_tables:
            base_table = existing_table.get("base_table", {})
            if (
                base_table.get("schema") == enhanced_table.base_table.schema
                and base_table.get("table") == enhanced_table.base_table.table
            ):
                matches.append(existing_table)

        if not matches:
            logger.warning(
                f"Could not find matching table for {enhanced_table.base_table.schema}."
                f"{enhanced_table.base_table.table} in semantic model"
            )
            continue

        if len(matches) > 1:
            # Multiple tables with same (schema, table) in different databases
            databases = [t.get("base_table", {}).get("database") for t in matches]
            logger.warning(
                f"Found {len(matches)} tables matching {enhanced_table.base_table.schema}."
                f"{enhanced_table.base_table.table} in databases {databases}. "
                f"Using the first match ({databases[0]}). This may produce incorrect results "
                "for multi-database semantic data models."
            )

        existing_table = matches[0]

        # Check if we should update this table based on tables_to_enhance filter
        logical_table_name = existing_table.get("name")
        if tables_to_enhance is not None and logical_table_name not in tables_to_enhance:
            continue

        # Update the table metadata
        if enhanced_table.name:
            existing_table["name"] = enhanced_table.name
        if enhanced_table.description is not None:
            existing_table["description"] = enhanced_table.description
        if enhanced_table.synonyms is not None:
            existing_table["synonyms"] = enhanced_table.synonyms


def update_columns_in_semantic_model(
    semantic_model: SemanticDataModel,
    enhanced_columns: TableToColumnsOutputSchema,
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
) -> None:
    """
    Update columns for the provided tables in the semantic data model.

    If a table or column cannot be found, we skip it and log a warning.

    Args:
        semantic_model: The original semantic model.
        enhanced_columns: A schema containing a dict mapping table names to lists of
            enhanced columns.
        tables_to_enhance: Optional set of table names to enhance.
        table_to_columns_to_enhance: Optional mapping of table names to column names.
    """
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )
    from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
        SemanticDataModelIndex,
    )

    # Create an index of the semantic model for efficient lookup by table name
    index = SemanticDataModelIndex(semantic_model)

    # Convert to LLM format for processing
    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model)

    # Iterate over each table and its enhanced columns
    for table_name, enhanced_column_list in enhanced_columns.table_to_columns.items():
        # Find the table in the model
        value = index.logical_table_name_to_logical_table.get(table_name)
        if not value:
            logger.warning(f"Could not find table {table_name} in semantic model")
            continue

        # Find the corresponding table in the LLM model
        llm_table = None
        for table in model_for_llm.tables or []:
            if table.name == table_name:
                llm_table = table
                break

        if not llm_table or not llm_table.columns:
            logger.warning(f"Could not find table {table_name} in LLM model or table has no columns")
            continue

        # Build a map of expr -> (index, column) for efficient lookup
        column_map: dict[str, tuple[int, ColumnForLLM]] = {
            col.expr: (i, col) for i, col in enumerate(llm_table.columns)
        }

        # Update each enhanced column
        for enhanced_column in enhanced_column_list:
            # Find the column by expr (the canonical identifier that doesn't change)
            column_info = column_map.get(enhanced_column.expr)
            if column_info:
                idx, _ = column_info
                llm_table.columns[idx] = enhanced_column
            else:
                logger.warning(f"Could not find column with expr '{enhanced_column.expr}' in table {table_name}")

    # Apply all changes back to the semantic model
    update_semantic_data_model_with_semantic_data_model_from_llm(
        semantic_model,
        model_for_llm,
        tables_to_enhance,
        table_to_columns_to_enhance,
    )
