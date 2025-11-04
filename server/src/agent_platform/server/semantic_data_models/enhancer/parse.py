"""Functions to assist in parsing LLM responses for the Semantic Data Model Enhancer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agent_platform.server.semantic_data_models.enhancer.type_defs import (
    ColumnForLLM,
    LLMOutputSchemas,
)

if TYPE_CHECKING:
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.server.semantic_data_models.enhancer.prompts import EnhancementMode
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        Category,
        SemanticDataModelForLLM,
        TablesOutputSchema,
        TableToColumnsOutputSchema,
    )


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def extract_response_text(response: ResponseMessage) -> str:
    """Extract response text from the response."""
    from agent_platform.core.responses.content import ResponseTextContent
    from agent_platform.server.semantic_data_models.enhancer.errors import EmptyResponseError

    if not response.content:
        raise EmptyResponseError(
            "Your response had no content. Please provide a complete semantic data model "
            "enhancement with the proper format as specified in the instructions.",
            response_message=response,
        )

    text_content = [c.text for c in response.content if isinstance(c, ResponseTextContent)]
    if not text_content:
        raise EmptyResponseError(
            "Your response had no text content. Please provide a complete semantic data "
            "model enhancement in text format with the proper XML tags and JSON structure.",
            response_message=response,
        )

    response_text = text_content[-1]

    if not response_text or not response_text.strip():
        raise EmptyResponseError(
            "Your response was empty. Please provide a complete semantic data model "
            "in the expected format with proper XML tags and JSON content.",
            response_message=response,
        )

    return response_text


def extract_json_from_response_text(response_text: str, mode: EnhancementMode = "full") -> str:
    """Extract the json from the appropriate <xml_tag>...</xml_tag> block."""
    from agent_platform.server.semantic_data_models.enhancer.errors import MissingXMLTagError

    xml_tag = {
        "full": "semantic-data-model",
        "tables": "table",
        "columns": "column",
    }[mode]
    i = response_text.find(f"<{xml_tag}>")
    j = response_text.rfind(f"</{xml_tag}>")
    if i == -1 or j == -1:
        # We couldn't find the <xml_tag>...</xml_tag> block.
        missing_parts = []
        if i == -1:
            missing_parts.append(f"opening tag <{xml_tag}>")
        if j == -1:
            missing_parts.append(f"closing tag </{xml_tag}>")

        improvement_msg = (
            f"Your response is missing the {' and '.join(missing_parts)}. "
            f"Please wrap your JSON response with <{xml_tag}> and </{xml_tag}> tags. "
            "The format should be:\n"
            f"<{xml_tag}>\n"
            "{\n"
            '  "your": "json",\n'
            '  "content": "here"\n'
            "}\n"
            f"</{xml_tag}>"
        )
        logger.warning(
            f"Couldn't find the <{xml_tag}>...</{xml_tag}> block"
            f" in the response text: {response_text}"
        )
        raise MissingXMLTagError(improvement_msg)
    response_text = response_text[i + len(f"<{xml_tag}>") : j]
    response_text = response_text.strip()
    return response_text


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
        EmptyResponseError: If response has no content
        MissingXMLTagError: If XML tags are missing
        InvalidJSONError: If JSON parsing fails
        SchemaValidationError: If schema validation fails
    """
    import json

    from agent_platform.server.semantic_data_models.enhancer.errors import (
        InvalidJSONError,
        MissingXMLTagError,
        SchemaValidationError,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        SemanticDataModelForLLM,
        TablesOutputSchema,
        TableToColumnsOutputSchema,
    )

    response_text = extract_response_text(response)

    # Extract content from XML tags
    try:
        extracted_json = extract_json_from_response_text(response_text, mode=mode)
    except MissingXMLTagError as e:
        # Re-raise with response context
        raise MissingXMLTagError(e.improvement_request, response_message=response) from e

    # Parse JSON
    try:
        enhanced_model_dict = json.loads(extracted_json)
    except json.JSONDecodeError as e:
        error_location = f"at line {e.lineno} column {e.colno}" if hasattr(e, "lineno") else ""
        improvement_msg = (
            f"Your JSON response has a syntax error {error_location}: {e.msg}. "
            "Please fix the JSON syntax and ensure all braces, brackets, and quotes are "
            "properly closed. Pay special attention to trailing commas and quote escaping."
        )
        logger.error(f"JSON parse error: {e}\nResponse from LLM: {extracted_json}")
        raise InvalidJSONError(improvement_msg, response_message=response) from e

    # Validate against schema based on mode
    try:
        if mode == "full":
            parsed_result = SemanticDataModelForLLM.model_validate(enhanced_model_dict)
        elif mode == "tables":
            parsed_result = TablesOutputSchema.model_validate(enhanced_model_dict)
        elif mode == "columns":
            parsed_result = TableToColumnsOutputSchema.model_validate(enhanced_model_dict)
        else:
            raise ValueError(f"Unknown mode: {mode}")
    except Exception as e:
        improvement_msg = (
            f"Your response doesn't match the expected schema. Error: {e}. "
            "Please review the output schema format carefully and ensure all required fields "
            "are present with the correct types and structure."
        )
        logger.error(f"Schema validation error: {e}\nFound response: {enhanced_model_dict}")
        raise SchemaValidationError(improvement_msg, response_message=response) from e

    return parsed_result


def update_semantic_data_model_with_semantic_data_model_from_llm(  # noqa: PLR0912, C901
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
                f"Table with schema '{schema}' and table '{table_name}' "
                "not found in existing semantic data model"
            )
            continue

        # Check if we should update this table based on tables_to_enhance filter
        logical_table_name = existing_table.get("name")
        # Process table if it's in tables_to_enhance OR has columns in table_to_columns_to_enhance
        should_process_table = (
            tables_to_enhance is None
            or logical_table_name in tables_to_enhance
            or (
                table_to_columns_to_enhance is not None
                and logical_table_name in table_to_columns_to_enhance
            )
        )
        if not should_process_table:
            continue

        # Determine if we should update table metadata
        # If the table is only specified in table_to_columns_to_enhance (not in tables_to_enhance),
        # we should only update columns, not the table's metadata
        should_update_table_metadata = (
            tables_to_enhance is None or logical_table_name in tables_to_enhance
        )

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


def _update_table_columns(  # noqa: C901, PLR0912
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
            logger.warning(
                f"Could not find table {table_name} in LLM model or table has no columns"
            )
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
                logger.warning(
                    f"Could not find column with expr '{enhanced_column.expr}' "
                    f"in table {table_name}"
                )

    # Apply all changes back to the semantic model
    update_semantic_data_model_with_semantic_data_model_from_llm(
        semantic_model,
        model_for_llm,
        tables_to_enhance,
        table_to_columns_to_enhance,
    )
