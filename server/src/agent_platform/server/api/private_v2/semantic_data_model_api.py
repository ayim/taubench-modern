"""API endpoints for semantic data models."""

from __future__ import annotations

import typing
from typing import TypedDict

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.data_frames.semantic_data_model_types import (
    SemanticDataModel,
    ValidationMessage,
    ValidationMessageKind,
    ValidationMessageLevel,
    VerifiedQuery,
    VerifiedQueryNameError,
    VerifiedQueryNLQError,
    VerifiedQueryParameterError,
    VerifiedQuerySQLError,
    VerifiedQueryValidationContext,
)
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads import (
    GenerateSemanticDataModelPayload,
    GenerateSemanticDataModelResponse,
    ImportSemanticDataModel,
    ImportSemanticDataModelPayload,
    SemanticDataModelWithAssociations,
    SetSemanticDataModelPayload,
)
from agent_platform.core.payloads.semantic_data_model_payloads import (
    ValidateSemanticDataModelPayload,
    ValidateSemanticDataModelResult,
    ValidateSemanticDataModelResultItem,
    VerifyVerifiedQueryPayload,
    VerifyVerifiedQueryResponse,
    _ValidateSemanticDataModelResultsSummary,
)
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser
from sema4ai.common.text import slugify

if typing.TYPE_CHECKING:
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelCollector,
    )
    from agent_platform.server.storage.base import BaseStorage

router = APIRouter(default_response_class=JSONResponse)
logger: BoundLogger = get_logger(__name__)


async def _replace_data_connection_id_with_name(
    semantic_model: SemanticDataModel,
    storage: StorageDependency,
    connection_cache: dict[str, str] | None = None,
) -> tuple[SemanticDataModel, dict[str, str]]:
    """Replace data_connection_id with data_connection_name in semantic model for export.

    Args:
        semantic_model: The semantic data model
        storage: The storage instance
        connection_cache: Optional cache of data_connection_id -> name mappings

    Returns:
        Tuple of (modified semantic model, connection_cache)
    """
    if connection_cache is None:
        connection_cache = {}

    # Convert to dict for manipulation, then back to SemanticDataModel
    # model_dump() already performs a deep copy, so no need for additional copy.deepcopy()
    modified_dict = semantic_model.model_dump(exclude_none=False)

    if "tables" in modified_dict:
        for table in modified_dict["tables"]:
            if "base_table" in table and isinstance(table["base_table"], dict):
                base_table = table["base_table"]

                if base_table.get("data_connection_id"):
                    dc_id = base_table["data_connection_id"]

                    # Check cache first
                    if dc_id not in connection_cache:
                        try:
                            # Fetch data connection to get name
                            dc = await storage.get_data_connection(dc_id)
                            connection_cache[dc_id] = dc.name
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch data connection for export: {e}",
                                data_connection_id=dc_id,
                                error=str(e),
                            )
                            # Keep the ID if we can't fetch the name
                            connection_cache[dc_id] = dc_id

                    # Replace ID with name
                    if dc_id in connection_cache:
                        base_table["data_connection_name"] = connection_cache[dc_id]
                        del base_table["data_connection_id"]

    # Convert back to SemanticDataModel (TypedDict is just a type annotation)
    modified_model = SemanticDataModel.model_validate(modified_dict)
    return modified_model, connection_cache


async def _replace_data_connection_name_with_id(
    semantic_model: SemanticDataModel, storage: StorageDependency
) -> tuple[SemanticDataModel, dict[str, str], list[str]]:
    """Replace data_connection_name with data_connection_id and validate connections.

    Accepts both data_connection_name and data_connection_id:
    - If data_connection_id is provided, validates it exists
    - If data_connection_name is provided (and no ID), resolves it to ID
    - If both are provided, uses data_connection_id and removes name

    Args:
        semantic_model: The semantic data model with data_connection_name or data_connection_id
        storage: The storage instance

    Returns:
        Tuple of (modified semantic model, resolved_connections dict,
        unresolved_connections list)
    """
    # Convert to dict for manipulation, then back to SemanticDataModel
    # model_dump() already performs a deep copy, so no need for additional copy.deepcopy()
    modified_dict = semantic_model.model_dump(exclude_none=False)
    resolved_connections: dict[str, str] = {}
    unresolved_connections: list[str] = []

    if "tables" in modified_dict:
        for table in modified_dict["tables"]:
            if "base_table" in table and isinstance(table["base_table"], dict):
                base_table = table["base_table"]

                # Case 1: data_connection_id is provided - validate it exists
                if "data_connection_id" in base_table:
                    dc_id = base_table["data_connection_id"]

                    # Check if the ID is empty/None
                    if not dc_id:
                        unresolved_connections.append("<empty data_connection_id>")
                        table_name = table.get("name", "unknown")
                        logger.error(f"Empty data_connection_id found in table {table_name}")
                        continue

                    try:
                        # Validate the connection exists
                        dc = await storage.get_data_connection(dc_id)
                        # Remove data_connection_name if present (ID takes precedence)
                        if "data_connection_name" in base_table:
                            del base_table["data_connection_name"]
                        logger.info(f"Validated data connection ID: {dc_id}")
                    except Exception as e:
                        unresolved_connections.append(str(dc_id))
                        logger.error(f"Data connection ID not found: {dc_id} - {e}")

                # Case 2: Only data_connection_name is present - resolve to ID
                elif "data_connection_name" in base_table:
                    dc_name = base_table["data_connection_name"]

                    # Check if the name is empty/None
                    if not dc_name:
                        unresolved_connections.append("<empty data_connection_name>")
                        table_name = table.get("name", "unknown")
                        logger.error(f"Empty data_connection_name found in table {table_name}")
                        continue

                    # Check if already resolved
                    if dc_name in resolved_connections:
                        base_table["data_connection_id"] = resolved_connections[dc_name]
                        del base_table["data_connection_name"]
                    else:
                        try:
                            # Resolve name to ID (case-insensitive)
                            dc = await storage.get_data_connection_by_name(dc_name)
                            if dc:
                                resolved_connections[dc_name] = dc.id
                                base_table["data_connection_id"] = dc.id
                                del base_table["data_connection_name"]
                                logger.info(f"Resolved data connection name to ID: {dc_name} -> {dc.id}")
                            else:
                                unresolved_connections.append(dc_name)
                                logger.warning(f"Data connection not found during import: {dc_name}")
                        except Exception as e:
                            unresolved_connections.append(dc_name)
                            logger.error(f"Error resolving data connection name '{dc_name}': {e}")

                # Case 3: Neither data_connection_id nor data_connection_name is present
                # Consider it a data frame reference (but it still must have a table name)
                elif "file_reference" not in base_table and not table.get("name"):
                    table_name = table.get("name", "unknown")
                    unresolved_connections.append(f"<missing table name in base_table: {base_table}>")
                    logger.error(f"Missing table name in base_table: {base_table}")

    # Convert back to SemanticDataModel (TypedDict is just a type annotation)
    modified_model = SemanticDataModel.model_validate(modified_dict)
    return modified_model, resolved_connections, unresolved_connections


class _SetSemanticDataModeFileReference(TypedDict):
    thread_id: str
    file_ref: str


class _SetSemanticDataModelResult(TypedDict):
    semantic_data_model_id: str
    data_connection_ids: list[str]
    file_references: list[_SetSemanticDataModeFileReference]


@router.put("/{semantic_data_model_id}")
async def set_semantic_data_model(
    semantic_data_model_id: str,
    payload: SetSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> _SetSemanticDataModelResult:
    """Set a semantic data mode.
    Returns the ID of the semantic data model (the same one passed in) as well as the
    data connection IDs and file references that were used to set the semantic data model."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )
    from agent_platform.server.semantic_data_models import (
        validate_semantic_data_model_name_is_unique,
    )

    # Convert file_references from list of dicts to list of tuples
    semantic_data_model = SemanticDataModel.model_validate(payload.semantic_model)

    try:
        references = validate_semantic_model_payload_and_extract_references(semantic_data_model)
        if references.errors:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="The semantic data model is invalid: \n" + "\n".join(references.errors),
            )

        # Validate name uniqueness (exclude current model for updates)
        model_name = semantic_data_model.name
        if model_name:
            await validate_semantic_data_model_name_is_unique(
                model_name, exclude_model_id=semantic_data_model_id, storage=storage
            )

        # Convert file_references from list of dicts to list of tuples
        file_references = [(ref.thread_id, ref.file_ref) for ref in references.file_references]

        # Set the semantic data model
        model_id: str = await storage.set_semantic_data_model(
            semantic_data_model_id=semantic_data_model_id,
            semantic_model=payload.semantic_model,
            data_connection_ids=list(references.data_connection_ids),
            file_references=file_references,
        )

        # Return the ID of the semantic data model (same one passed in)
        assert model_id == semantic_data_model_id
        return _SetSemanticDataModelResult(
            semantic_data_model_id=model_id,
            data_connection_ids=list(references.data_connection_ids),
            file_references=list(
                {"thread_id": ref.thread_id, "file_ref": ref.file_ref} for ref in references.file_references
            ),
        )
    except PlatformHTTPError as e:
        raise e
    except ValueError as e:
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message=str(e)) from e
    except Exception as e:
        logger.error("Error setting semantic data model", error=str(e))
        raise PlatformHTTPError(error_code=ErrorCode.UNEXPECTED, message="Error setting semantic data model") from e


@router.post("/")
async def create_semantic_data_model(
    payload: SetSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> _SetSemanticDataModelResult:
    """Create a new semantic data model.
    Returns the ID of the created semantic data model as well as the
    data connection IDs and file references that were used to create the semantic data model."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )
    from agent_platform.server.semantic_data_models import (
        validate_semantic_data_model_name_is_unique,
    )

    # Convert file_references from list of dicts to list of tuples
    semantic_data_model = SemanticDataModel.model_validate(payload.semantic_model)

    try:
        references = validate_semantic_model_payload_and_extract_references(semantic_data_model)
        if references.errors:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="The semantic data model is invalid: \n" + "\n".join(references.errors),
            )

        # Validate name uniqueness
        model_name = semantic_data_model.name
        if model_name:
            await validate_semantic_data_model_name_is_unique(model_name, storage=storage)

        # Convert file_references from list of dicts to list of tuples
        file_references = [(ref.thread_id, ref.file_ref) for ref in references.file_references]

        # Create the semantic data model (ID will be generated)
        model_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=semantic_data_model,
            data_connection_ids=list(references.data_connection_ids),
            file_references=file_references,
        )

        # Return the ID of the created semantic data model
        return _SetSemanticDataModelResult(
            semantic_data_model_id=model_id,
            data_connection_ids=list(references.data_connection_ids),
            file_references=list(
                {"thread_id": ref.thread_id, "file_ref": ref.file_ref} for ref in references.file_references
            ),
        )
    except PlatformHTTPError as e:
        raise e
    except Exception as e:
        logger.error("Error creating semantic data model", error=str(e))
        raise PlatformHTTPError(error_code=ErrorCode.UNEXPECTED, message="Error creating semantic data model") from e


@router.get("/{semantic_data_model_id}")
async def get_semantic_data_model(
    semantic_data_model_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> dict:
    """Get a semantic data model by ID."""
    try:
        # Storage returns dict, return as-is
        return await storage.get_semantic_data_model(semantic_data_model_id)
    except PlatformHTTPError as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting semantic data model: {e}")
        raise PlatformHTTPError(error_code=ErrorCode.UNEXPECTED, message="Error getting semantic data model") from e


@router.delete("/{semantic_data_model_id}")
async def delete_semantic_data_model(
    semantic_data_model_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> None:
    """Delete a semantic data model by ID."""
    try:
        await storage.delete_semantic_data_model(semantic_data_model_id)
    except PlatformHTTPError as e:
        raise e
    except Exception as e:
        logger.error("Error deleting semantic data model", error=str(e))
        raise PlatformHTTPError(error_code=ErrorCode.UNEXPECTED, message="Error deleting semantic data model") from e


@router.post("/generate")
async def generate_semantic_data_model(
    payload: GenerateSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> GenerateSemanticDataModelResponse:
    """Generate a semantic data model from data connections and files."""
    from agent_platform.server.kernel.semantic_data_model_generator import (
        SemanticDataModelGenerator,
    )
    from agent_platform.server.semantic_data_models.enhancer.enhancer import (
        SemanticDataModelEnhancer,
        reset_logical_names_to_physical_for_data_connections,
    )
    from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
        KeyForBaseTable,
        KeyForDimension,
        ValueForBaseTable,
        ValueForDimension,
    )

    try:
        generator = SemanticDataModelGenerator(storage=storage)
        semantic_model = await generator.generate_semantic_data_model(
            name=payload.name,
            description=payload.description,
            data_connections_info=payload.data_connections_info,
            files_info=payload.files_info,
        )

        enhance_model: bool = True
        missing_keys: list[KeyForDimension | KeyForBaseTable] = []
        # Store the existing model's name and description to preserve after enhancement
        existing_model_name: str | None = None
        existing_model_description: str | None = None
        # For new models: preserve user-provided description (let LLM enhance name)
        preserve_description: str | None = payload.description if payload.description else None

        if payload.existing_semantic_data_model:
            from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
                SemanticDataModelIndex,
                copy_synonyms_and_descriptions_from_existing_semantic_model,
            )

            if isinstance(payload.existing_semantic_data_model, str):
                existing_sdm_data = await storage.get_semantic_data_model(payload.existing_semantic_data_model)
                existing_semantic_model = SemanticDataModel.model_validate(existing_sdm_data)
            elif isinstance(payload.existing_semantic_data_model, dict):
                # Convert dict to SemanticDataModel if needed (for type checking)
                existing_semantic_model = SemanticDataModel.model_validate(payload.existing_semantic_data_model)
            else:
                existing_semantic_model = payload.existing_semantic_data_model

            # Store the existing model's name and description to preserve after enhancement
            existing_model_name = existing_semantic_model.name
            existing_model_description = existing_semantic_model.description

            # When regenerating an existing semantic model, preserve its name and description
            # because we're updating the existing model, not creating a new one
            # Convert to dict for manipulation, then back to SemanticDataModel
            semantic_model_dict = SemanticDataModel.model_validate(semantic_model).model_dump(exclude_none=False)
            semantic_model_dict["name"] = existing_model_name or semantic_model.name
            if existing_model_description:
                # For regeneration, use existing model's description
                preserve_description = existing_model_description
                semantic_model_dict["description"] = existing_model_description
            semantic_model = SemanticDataModel.model_validate(semantic_model_dict)

            # Now, we need to copy from the existing semantic model to the new semantic model
            # the synonyms and descriptions that are not present in the new semantic model.
            # Note that it's important to match the models based on the base_table information
            # (because the logical table name may have changed).
            new_index = SemanticDataModelIndex(semantic_model)
            existing_index = SemanticDataModelIndex(existing_semantic_model)
            missing_keys = copy_synonyms_and_descriptions_from_existing_semantic_model(
                index_from=existing_index, index_to=new_index
            )
            if not missing_keys:
                # We're good to go, nothing seems to have changed (probably just
                # removed columns or tables).
                logger.info("No missing keys, no enhancement needed")
                enhance_model = False

        if enhance_model:
            if payload.agent_id:
                enhancer = SemanticDataModelEnhancer(
                    user=user,
                    storage=storage,
                    agent_id=payload.agent_id,
                )
                if missing_keys:
                    # Calculate the tables/dimensions that need to be enhanced
                    tables_to_enhance: set[str] = set()
                    table_to_columns_to_enhance: dict[str, list[str]] = {}
                    for key in missing_keys:
                        if isinstance(key, KeyForDimension):
                            value: ValueForDimension = new_index.dimension_key_to_dimension[key]
                            table_name = value.logical_table.get("name")
                            if table_name:
                                # Use expr (database column name) instead of name (logical name)
                                # because LLM can change the logical name during enhancement
                                column_expr = value.dimension.get("expr")
                                if column_expr:
                                    table_to_columns_to_enhance.setdefault(table_name, []).append(column_expr)
                        elif isinstance(key, KeyForBaseTable):
                            value_for_base_table: ValueForBaseTable = new_index.base_table_to_logical_table[key]
                            table_name = value_for_base_table.table.get("name")
                            if table_name:
                                tables_to_enhance.add(table_name)
                        else:
                            logger.critical(f"Unknown key type: {key}")

                    logger.info(
                        f"Partial enhancement: {len(missing_keys)} missing keys - "
                        f"Tables: {tables_to_enhance}, Columns: {table_to_columns_to_enhance}"
                    )

                    if tables_to_enhance or table_to_columns_to_enhance:
                        await enhancer.enhance_semantic_data_model(
                            semantic_model,
                            tables_to_enhance=tables_to_enhance,
                            table_to_columns_to_enhance=table_to_columns_to_enhance,
                        )
                else:  # no missing keys means we have to enhance the full model.
                    await enhancer.enhance_semantic_data_model(semantic_model)

                # Post-process: For data connection-backed tables, reset logical names
                # to match physical names (database naming convention takes precedence)
                reset_logical_names_to_physical_for_data_connections(semantic_model)

                # After enhancement, restore the existing model's name and description
                # The enhancer may have modified these, but we want to preserve the original
                # when regenerating an existing model
                semantic_model_dict = SemanticDataModel.model_validate(semantic_model).model_dump(exclude_none=False)
                if existing_model_name is not None:
                    semantic_model_dict["name"] = existing_model_name
                else:
                    # If there's no existing model name, ensure the enhanced name is unique
                    # The enhancer might have generated a name that already exists
                    from agent_platform.server.semantic_data_models import (
                        make_semantic_data_model_name_unique,
                    )

                    enhanced_name = semantic_model_dict.get("name")
                    if enhanced_name:
                        semantic_model_dict["name"] = await make_semantic_data_model_name_unique(
                            enhanced_name, storage=storage
                        )
                # Restore description (either user-provided for new models or from existing model)
                if preserve_description is not None:
                    semantic_model_dict["description"] = preserve_description
                semantic_model = SemanticDataModel.model_validate(semantic_model_dict)
            else:
                logger.critical(
                    "No agent ID provided when generating semantic data model, "
                    "LLM improvement is not possible! This will become an error in the future."
                )

        logger.info(
            "Successfully generated semantic data model",
            model_name=payload.name,
            user_id=user.user_id,
        )

        return GenerateSemanticDataModelResponse(semantic_model=semantic_model)
    except Exception as e:
        logger.error("Error generating semantic data model", error=str(e))
        raise PlatformHTTPError(error_code=ErrorCode.UNEXPECTED, message="Error generating semantic data model") from e


@router.get("/", response_model=list[SemanticDataModelWithAssociations])
async def list_semantic_data_models(
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str | None = None,
    thread_id: str | None = None,
) -> list[SemanticDataModelWithAssociations]:
    """List semantic data models with optional filtering by agent_id or thread_id."""
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    try:
        semantic_data_models_info = await storage.list_semantic_data_models(agent_id=agent_id, thread_id=thread_id)

        # Convert the results to SemanticDataModelWithAssociations objects
        semantic_data_models_with_associations = []
        semantic_data_model_info: BaseStorage.SemanticDataModelInfo
        # Convert file references to FileReference objects
        from agent_platform.core.payloads import EmptyFileReference, FileReference

        for semantic_data_model_info in semantic_data_models_info:
            # Note: lots of 'str' to convert UUIDs to strings

            semantic_data_model_id = str(semantic_data_model_info["semantic_data_model_id"])
            semantic_data_model = SemanticDataModel.model_validate(semantic_data_model_info["semantic_data_model"])

            references = validate_semantic_model_payload_and_extract_references(semantic_data_model)
            file_references = [
                FileReference(
                    thread_id=str(ref.thread_id),
                    file_ref=ref.file_ref,
                    sheet_name=ref.sheet_name,
                )
                for ref in references.file_references
            ]

            empty_file_references = [
                EmptyFileReference(
                    logical_table_name=ref.logical_table_name,
                    sheet_name=ref.sheet_name,
                    base_table_table=ref.base_table_table,
                )
                for ref in references.tables_with_unresolved_file_references
            ]

            semantic_data_models_with_associations.append(
                SemanticDataModelWithAssociations(
                    semantic_data_model_id=semantic_data_model_id,
                    semantic_data_model=semantic_data_model,
                    agent_ids=list(str(agent_id) for agent_id in semantic_data_model_info["agent_ids"]),
                    thread_ids=list(str(thread_id) for thread_id in semantic_data_model_info["thread_ids"]),
                    data_connection_ids=list(
                        str(data_connection_id) for data_connection_id in references.data_connection_ids
                    ),
                    file_references=file_references,
                    errors_in_semantic_data_model=references.errors,
                    empty_file_references=empty_file_references,
                )
            )

        return semantic_data_models_with_associations
    except Exception as e:
        logger.error(f"Error listing semantic data models: {e}")
        raise PlatformHTTPError(error_code=ErrorCode.UNEXPECTED, message="Error listing semantic data models") from e


class ExportSemanticDataModelResponse(TypedDict):
    """Response for exporting a semantic data model."""

    content: str
    filename: str
    format: str


@router.get("/{semantic_data_model_id}/export")
async def export_semantic_data_model(
    semantic_data_model_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> ExportSemanticDataModelResponse:
    """Export a semantic data model as YAML.

    This endpoint returns a JSON response containing the semantic data model as a YAML string
    with data_connection_name instead of data_connection_id, making it portable across
    environments.

    The YAML content can be saved to a file or passed directly to the /import endpoint
    (which accepts both YAML strings and JSON objects).

    Returns:
        JSON response with:
        - content: The YAML-formatted semantic data model with data_connection_name
        - filename: Suggested filename for saving (e.g., "model-name.yaml")
        - format: The format of the content ("yaml")
    """
    try:
        # Get the semantic data model
        semantic_model = await storage.get_semantic_data_model(semantic_data_model_id)

        # Replace data_connection_id with data_connection_name
        portable_model, _ = await _replace_data_connection_id_with_name(
            SemanticDataModel.model_validate(semantic_model), storage
        )

        # Convert to dict for YAML serialization (model_dump handles datetime conversion)
        portable_model_dict = portable_model.model_dump(exclude_none=False)

        # Convert to YAML
        yaml_content = yaml.dump(
            portable_model_dict,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        logger.info(f"Exported semantic data model {semantic_data_model_id} for user {user.user_id}")

        # Return JSON response with YAML content as string
        # Use the model name for the filename if available, slugify for safety
        base_name = portable_model.name if portable_model.name else semantic_data_model_id
        filename = f"{slugify(base_name)}.yaml"

        return ExportSemanticDataModelResponse(
            content=yaml_content,
            filename=filename,
            format="yaml",
        )

    except ValueError as e:
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message=str(e)) from e
    except Exception as e:
        logger.error(f"Error exporting semantic data model {semantic_data_model_id}: {e}")
        raise PlatformHTTPError(error_code=ErrorCode.UNEXPECTED, message="Error exporting semantic data model") from e


@router.post("/import")
async def import_semantic_data_model(
    payload: ImportSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> ImportSemanticDataModel:
    """Import a semantic data model from a portable format (JSON or YAML).

    This endpoint accepts a semantic data model and creates/reuses an SDM in the target environment.

    The semantic_model can be provided as either:
    - JSON object (dict) in the request body
    - YAML string that will be parsed automatically

    **Data Connection Handling:**
    The endpoint accepts BOTH data_connection_name and data_connection_id:
    - If `data_connection_id` is provided: Validates the connection exists
    - If `data_connection_name` is provided: Resolves name to ID (case-insensitive)
    - If both are provided: Uses `data_connection_id` (ID takes precedence)

    **Using with /export endpoint:**
    ```json
    {
      "semantic_model": "<export_response.content>",
      "agent_id": "optional"
    }
    ```
    Export provides `data_connection_name` for portability. The UI can:
    1. Let users map connection names to specific connection IDs
    2. Replace connection names with IDs before import
    3. Let import resolve names automatically (if names match)

    Parameters:
    - semantic_model: The SDM with data_connection_name or data_connection_id (dict or YAML string)
    - agent_id (optional): Enables deduplication check for this agent
    - thread_id (optional): Enables file reference resolution via SemanticDataModelCollector

    Prerequisites:
    - All data connections referenced in the SDM must exist in the target environment
    - If any connections cannot be resolved/validated, the import fails with detailed error

    Returns:
    - semantic_data_model_id: ID of the newly created or reused SDM
    - resolved_data_connections: Map of connection names to their resolved IDs
    - unresolved_data_connections: Empty list (will fail before this if any are unresolved)
    - is_duplicate: True if an existing SDM was reused
    - warnings: Any non-fatal issues encountered during import
    """
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )
    from agent_platform.server.semantic_data_models import (
        make_semantic_data_model_name_unique,
    )

    # Parse YAML string if provided
    # FastAPI doesn't call custom model_validate for dataclasses, so we handle it here
    semantic_model_data = payload.semantic_model
    if isinstance(semantic_model_data, str):
        try:
            semantic_model_data = yaml.safe_load(semantic_model_data)
        except yaml.YAMLError as e:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"Invalid YAML in semantic_model: {e}",
            ) from e

    # At this point, semantic_model should be a dict - cast to SemanticDataModel for type safety
    semantic_model = SemanticDataModel.model_validate(semantic_model_data)

    # Replace data_connection_name with data_connection_id
    (
        resolved_model,
        resolved_connections,
        unresolved_connections,
    ) = await _replace_data_connection_name_with_id(semantic_model, storage)

    # Fail immediately if any connections couldn't be resolved
    # This must happen BEFORE deduplication check to ensure we don't reuse an existing SDM
    # when the new import has unresolved connections
    if unresolved_connections:
        # Get list of available connections to help user
        available_connections = []
        try:
            # Query for some connection names to show in error
            all_connections = await storage.get_data_connections()
            available_connections = [dc.name for dc in all_connections[:10]]  # Show first 10
        except Exception:
            logger.exception("Error getting data connections")

        error_msg = (
            f"Cannot import SDM: {len(unresolved_connections)} data connection(s) not found:\n"
            f"  - {', '.join(unresolved_connections)}\n\n"
            "Please create these data connections in the target environment "
            "before importing.\n"
        )
        if available_connections:
            error_msg += f"Available connections: {', '.join(available_connections)}"

        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=error_msg,
        )

    # Validate the resolved semantic model (cast to SemanticDataModel for validation)
    # This must also happen BEFORE deduplication to ensure the imported SDM is valid
    references = validate_semantic_model_payload_and_extract_references(resolved_model)
    if references.errors:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="The semantic data model is invalid: \n" + "\n".join(references.errors),
        )

    # Prepare warnings (will be empty unless other issues arise)
    warnings = []

    # Auto-rename if name conflicts with existing SDM
    model_name = resolved_model.name
    if model_name:
        unique_name = await make_semantic_data_model_name_unique(model_name, storage=storage)
        if unique_name != model_name:
            resolved_model_dict = resolved_model.model_dump(exclude_none=False)
            resolved_model_dict["name"] = unique_name
            resolved_model = SemanticDataModel.model_validate(resolved_model_dict)

    # Convert file_references from list of dicts to list of tuples
    file_references = [(ref.thread_id, ref.file_ref) for ref in references.file_references]

    # Create the semantic data model (ID will be generated)
    model_id = await storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=resolved_model,
        data_connection_ids=list(references.data_connection_ids),
        file_references=file_references,
    )

    logger.info(
        f"Created new semantic data model {model_id} for user {user.user_id} (resolved: {len(resolved_connections)})"
    )

    # Link the SDM to the agent if agent_id is provided
    if payload.agent_id:
        # Get existing SDM IDs for this agent
        existing_sdms = await storage.get_agent_semantic_data_models(payload.agent_id)
        existing_sdm_ids = []
        for sdm_dict in existing_sdms:
            # Each dict has format {sdm_id: model}
            existing_sdm_ids.extend(sdm_dict.keys())

        # Add the new SDM to the agent's list
        updated_sdm_ids = [*existing_sdm_ids, model_id]
        await storage.set_agent_semantic_data_models(payload.agent_id, updated_sdm_ids)

        logger.info(f"Linked semantic data model {model_id} to agent {payload.agent_id}")

    return ImportSemanticDataModel(
        semantic_data_model_id=model_id,
        resolved_data_connections=resolved_connections,
        is_duplicate=False,
        warnings=warnings,
    )


async def _collect_single_sdm(
    payload: ValidateSemanticDataModelPayload,
    storage: StorageDependency,
    collector: SemanticDataModelCollector | None,
) -> list[tuple[str | None, SemanticDataModel]]:
    if payload.semantic_data_model:
        sdm_id = None
        # Convert dict to SemanticDataModel if needed (for type checking)
        if isinstance(payload.semantic_data_model, dict):
            sdm_to_validate = SemanticDataModel.model_validate(payload.semantic_data_model)
        else:
            sdm_to_validate = payload.semantic_data_model

    elif payload.semantic_data_model_id:
        try:
            sdm_data = await storage.get_semantic_data_model(payload.semantic_data_model_id)
            sdm_to_validate = SemanticDataModel.model_validate(sdm_data)
            sdm_id = payload.semantic_data_model_id
        except ValueError as e:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=str(e),
            ) from e

    if collector:
        sdm_to_validate, _ = await collector.resolve_file_references_for_semantic_data_model(storage, sdm_to_validate)

    # Check if SDM has tables (not empty)
    if not sdm_to_validate.tables:
        return []

    return [(sdm_id, sdm_to_validate)]


async def _collect_list_of_sdms(
    sdm_dicts: list[dict],
    storage: StorageDependency,
    collector: SemanticDataModelCollector | None,
) -> list[tuple[str | None, SemanticDataModel]]:
    # Storage returns list[dict] where each dict is {sdm_id: sdm}
    sdms_to_validate: list[tuple[str | None, SemanticDataModel]] = []
    for sdm_dict in sdm_dicts:
        for sdm_id, semantic_data_model in sdm_dict.items():
            sdm = SemanticDataModel.model_validate(semantic_data_model)
            if collector:
                sdm, _ = await collector.resolve_file_references_for_semantic_data_model(storage, sdm)
            sdms_to_validate.append((sdm_id, sdm))

    return sdms_to_validate


async def _collect_agent_sdms(
    agent_id: str,
    storage: StorageDependency,
    collector: SemanticDataModelCollector | None,
) -> list[tuple[str | None, SemanticDataModel]]:
    agent_sdms = await storage.get_agent_semantic_data_models(agent_id)
    return await _collect_list_of_sdms(agent_sdms, storage, collector)


async def _collect_thread_sdms(
    thread_id: str,
    storage: StorageDependency,
    collector: SemanticDataModelCollector,
) -> list[tuple[str | None, SemanticDataModel]]:
    thread_sdms = await storage.get_thread_semantic_data_models(thread_id)
    return await _collect_list_of_sdms(thread_sdms, storage, collector)


async def _validate_single_sdm(
    sdm_id: str | None,
    sdm: SemanticDataModel,
    thread_id: str | None,
    storage: StorageDependency,
    user: AuthedUser,
) -> ValidateSemanticDataModelResultItem:
    """Validate a single SDM and return result item.

    Args:
        sdm_id: The SDM ID (None for inline SDMs)
        sdm: The semantic data model to validate
        thread_id: Optional thread ID for file reference resolution
        storage: Storage instance
        user: Authenticated user

    Returns:
        Validation result item with SDM, errors, and warnings
    """
    from agent_platform.core.data_frames.semantic_data_model_types import (
        ValidationMessage,
    )
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    try:
        # First, run structural validation and extract references
        references = validate_semantic_model_payload_and_extract_references(sdm)
        if references.errors:
            # If we have reference errors, we should have an SDM with errors
            assert references.semantic_data_model_with_errors is not None

            # Structural validation failed - return early with errors
            return ValidateSemanticDataModelResultItem(
                semantic_data_model_id=sdm_id,
                semantic_data_model=references.semantic_data_model_with_errors,
                errors=references._structured_errors,
                warnings=[],
            )

        # Then run contextual validation
        validator = SemanticDataModelValidator(
            semantic_data_model=sdm,
            references=references,
            thread_id=thread_id,
            storage=storage,
            user=user,
        )

        result = await validator.validate()

        return ValidateSemanticDataModelResultItem(
            semantic_data_model_id=sdm_id,
            semantic_data_model=result.semantic_data_model_with_errors(),
            errors=result.errors,
            warnings=result.warnings,
        )
    except Exception as e:
        # Handle validation failures gracefully
        logger.exception(f"Error validating SDM {sdm_id}: {e}")
        return ValidateSemanticDataModelResultItem(
            semantic_data_model_id=sdm_id,
            semantic_data_model=sdm,
            errors=[
                ValidationMessage(
                    message=str(e),
                    level=ValidationMessageLevel.ERROR,
                    kind=ValidationMessageKind.VALIDATION_EXECUTION_ERROR,
                )
            ],
            warnings=[],
        )


@router.post("/validate")
async def validate_semantic_data_model(
    payload: ValidateSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> ValidateSemanticDataModelResult:
    """Validate one or more semantic data models.

    **Selector fields** (exactly one required):
    - `semantic_data_model`, `semantic_data_model_id`, `agent_id`, OR `thread_id` alone

    **Context field** (optional):
    - `thread_id` can be provided alongside selectors for file reference resolution

    This endpoint supports multiple validation modes:

    1. **Single inline SDM validation**:
       - Provide `semantic_data_model` (dict)
       - Optionally add `thread_id` for file resolution
       - Without `thread_id`: file references will be warnings

    2. **Single stored SDM validation**:
       - Provide `semantic_data_model_id`
       - Optionally add `thread_id` for file resolution
       - Without `thread_id`: file references will be warnings

    3. **Agent SDMs validation**:
       - Provide `agent_id` to validate all SDMs associated with that agent
       - Optionally add `thread_id` for file resolution
       - Without `thread_id`: file references will be warnings
       - If `thread_id` is provided, it must belong to the agent

    4. **Thread SDMs validation**:
       - Provide `thread_id` alone
       - Validates all SDMs stored in the thread
       - File references can be resolved using the thread context
       - Note: Does NOT validate agent SDMs, only thread SDMs

    Returns:
        ValidateSemanticDataModelResult: Contains a list of validation results,
        one per SDM validated, with errors and warnings for each.
    """
    import asyncio

    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelCollector,
    )

    # Get and validate access to agent and thread, if provided
    agent = None
    thread = None
    if payload.agent_id:
        agent = await storage.get_agent(user.user_id, payload.agent_id)
    if payload.thread_id:
        thread = await storage.get_thread(user.user_id, payload.thread_id)

    # Validate that if both agent_id and thread_id are provided, they are associated
    if thread and agent and thread.agent_id != agent.agent_id:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=f"Thread {thread.thread_id} does not belong to agent {agent.agent_id}.",
        )

    # Create a collector that can be used when collecting SDMs from various sources
    collector: SemanticDataModelCollector | None = None
    if thread is not None:
        collector = SemanticDataModelCollector(
            agent_id=thread.agent_id,
            thread_id=thread.thread_id,
            user=user,
            state=None,  # No state available in this context
        )

    # Collect SDMs to validate from various sources into a list of tuples where the first
    # element is the SDM ID (if any) and the second element is the SDM
    if payload.semantic_data_model or payload.semantic_data_model_id:
        sdms_to_validate = await _collect_single_sdm(payload, storage, collector)

    # Agent SDMs validation
    elif agent:
        sdms_to_validate = await _collect_agent_sdms(agent.agent_id, storage, collector)

    # Thread SDMs validation
    elif thread:
        assert collector is not None  # checked above
        sdms_to_validate = await _collect_thread_sdms(thread.thread_id, storage, collector)

    # Deduplicate SDMs that have the same ID (removes any SDM with a duplicate non-None ID)
    seen_ids = set()
    deduped_sdms = []
    for sdm_id, sdm in sdms_to_validate:
        if sdm_id is None:
            deduped_sdms.append((sdm_id, sdm))
        elif sdm_id not in seen_ids:
            deduped_sdms.append((sdm_id, sdm))
            seen_ids.add(sdm_id)
    sdms_to_validate = deduped_sdms

    # Validate each collected SDM in parallel
    results = await asyncio.gather(
        *[
            _validate_single_sdm(
                sdm_id,
                sdm,
                thread.thread_id if thread else None,
                storage,
                user,
            )
            for sdm_id, sdm in sdms_to_validate
        ]
    )

    # Compute summary statistics
    summary = _ValidateSemanticDataModelResultsSummary(
        total_sdms=len(results),
        total_errors=sum(len(result.errors) for result in results),
        total_warnings=sum(len(result.warnings) for result in results),
        sdms_with_errors=sum(1 for result in results if result.errors),
        sdms_with_warnings=sum(1 for result in results if result.warnings),
    )
    # Return results with summary statistics
    return ValidateSemanticDataModelResult(
        results=results,
        summary=summary,
    )


async def prepare_verified_query_validation_context(
    semantic_data_model: SemanticDataModel,
    storage: BaseStorage,
    original_name: str | None = None,
) -> VerifiedQueryValidationContext:
    """Prepare validation context for verified query validation.

    Extracts and prepares all necessary data from the semantic data model
    for use in verified query validation.

    Args:
        semantic_data_model: The semantic data model to extract data from
        storage: Storage instance to fetch data connections
        original_name: Original query name (when editing, to exclude from uniqueness check)

    Returns:
        VerifiedQueryValidationContext with all prepared validation data
    """
    from agent_platform.core.data_frames.semantic_data_model_types import (
        LogicalTable,
        VerifiedQueryValidationContext,
    )

    # 1. Determine dialect from first available data connection or file reference
    dialect = None
    tables = semantic_data_model.tables or []
    if tables:
        for table in tables:
            base_table = table.get("base_table")
            if base_table:
                data_connection_id = base_table.get("data_connection_id")
                if data_connection_id:
                    try:
                        data_connection = await storage.get_data_connection(data_connection_id)
                        if data_connection:
                            dialect = data_connection.engine
                            break
                    except Exception:
                        # If we can't get the connection, continue to next table
                        continue
                elif "file_reference" in base_table:
                    # File-based tables use DuckDB
                    dialect = "duckdb"
                    break

    # 2. Build table name mappings
    logical_tables = semantic_data_model.tables or []
    available_table_name_to_table: dict[str, LogicalTable] = {
        table.get("name") or "": table for table in logical_tables if table.get("name")
    }
    available_table_names = set(available_table_name_to_table.keys())

    # 3. Extract existing query names (for uniqueness check)
    verified_queries = semantic_data_model.verified_queries or []
    existing_query_names = {q["name"] for q in verified_queries if isinstance(q, dict) and "name" in q}
    # Remove the original name from the set if we're editing
    if original_name:
        existing_query_names.discard(original_name)

    return VerifiedQueryValidationContext(
        dialect=dialect,
        logical_tables=logical_tables,
        available_table_names=available_table_names,
        available_table_name_to_table=available_table_name_to_table,
        existing_query_names=existing_query_names,
        original_name=original_name,
    )


@router.post("/verify-verified-query")
async def verify_verified_query(
    payload: VerifyVerifiedQueryPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> VerifyVerifiedQueryResponse:
    """Verify a verified query against a semantic data model.

    This endpoint validates a verified query by:
    1. Validating the SQL query syntax
    2. Checking if the SQL query references valid tables from the semantic data model
    3. Validating the NLQ (Natural Language Question) is not empty
    4. Validating the name is valid and unique within the semantic data model

    Returns a new version of the verified query with validation errors set, if any.
    The errors can be in:
    - sql_errors: Errors related to the SQL query
    - nlq_errors: Errors related to the NLQ
    - name_errors: Errors related to the name

    Args:
        payload: Contains the semantic_data_model and verified_query to validate
        user: Authenticated user
        storage: Storage instance

    Returns:
        VerifyVerifiedQueryResponse: Contains the verified query with errors set, if any
    """
    import datetime

    try:
        # Cast semantic data model
        semantic_data_model = SemanticDataModel.model_validate(payload.semantic_data_model)

        # Convert verified_query to dict if it's a Pydantic model
        if isinstance(payload.verified_query, VerifiedQuery):
            verified_query_dict = payload.verified_query.model_dump()
        else:
            verified_query_dict = payload.verified_query

        # Prepare validation context
        original_name = payload.accept_initial_name if payload.accept_initial_name else None
        validation_context = await prepare_verified_query_validation_context(
            semantic_data_model=semantic_data_model,
            storage=storage,
            original_name=original_name,
        )

        # Run Pydantic validation with context - this automatically runs all validators
        # Add default values for verified_at and verified_by if not present
        verified_query_dict.setdefault("verified_at", datetime.datetime.now(datetime.UTC).isoformat())
        verified_query_dict.setdefault("verified_by", user.user_id)

        try:
            validated_query = VerifiedQuery.model_validate(
                verified_query_dict,
                context={"validation_context": validation_context},
            )
        except (
            VerifiedQuerySQLError,
            VerifiedQueryNameError,
            VerifiedQueryNLQError,
            VerifiedQueryParameterError,
        ) as e:
            # Custom validation error - create a partial model to hold the error
            validated_query = VerifiedQuery.model_construct(**verified_query_dict)

            error_msg = ValidationMessage(
                message=e.message,
                kind=e.kind,
                level=e.level,
            )

            # Categorize based on exception type
            if isinstance(e, VerifiedQuerySQLError):
                validated_query.sql_errors = [error_msg]
            elif isinstance(e, VerifiedQueryNameError):
                validated_query.name_errors = [error_msg]
            elif isinstance(e, VerifiedQueryNLQError):
                validated_query.nlq_errors = [error_msg]
            elif isinstance(e, VerifiedQueryParameterError):
                validated_query.parameter_errors = [error_msg]

        except ValidationError as e:
            # Pydantic field validation errors - create a partial model to hold the errors
            from agent_platform.server.data_frames.semantic_data_model_validator import (
                create_partial_verified_query_with_errors,
            )

            validated_query = create_partial_verified_query_with_errors(verified_query_dict, e)

        return VerifyVerifiedQueryResponse(verified_query=validated_query)

    except Exception as e:
        msg = f"Error verifying verified query: {e}"
        logger.exception(msg)
        raise PlatformHTTPError(error_code=ErrorCode.UNEXPECTED, message=msg) from e
