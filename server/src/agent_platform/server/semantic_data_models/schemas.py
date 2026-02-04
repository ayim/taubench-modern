"""Schema validation utilities for semantic data models."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_platform.core.semantic_data_model import SemanticDataModel
    from agent_platform.server.storage import BaseStorage


async def _validate_unique_schema_names(
    sdm: SemanticDataModel,
    storage: BaseStorage,
    exclude_sdm_id: str | None = None,
) -> None:
    """Validate that schema names don't conflict with schemas in other SDMs.

    Streams SDMs one at a time to avoid loading all into memory.

    Args:
        sdm: The semantic data model being validated.
        storage: The storage instance.
        exclude_sdm_id: Optional SDM ID to exclude (for updates to existing SDM).

    Raises:
        ValueError: If any schema name conflicts with an existing schema.
    """
    from agent_platform.core.semantic_data_model.schemas import normalize_schema_name

    if not sdm.schemas:
        return

    # Build set of normalized names we're checking
    new_schema_names = {normalize_schema_name(s.name) for s in sdm.schemas}

    # Stream through SDMs and check each one
    async for sdm_id, schemas in storage.iter_sdm_schemas():
        # Skip the current SDM (for update case)
        if exclude_sdm_id is not None and sdm_id == exclude_sdm_id:
            continue

        for schema in schemas or []:
            normalized_name = normalize_schema_name(schema.name)
            if normalized_name in new_schema_names:
                # Find the original name for the error message
                original_name = next(s.name for s in sdm.schemas if normalize_schema_name(s.name) == normalized_name)
                raise ValueError(
                    f"Schema name '{original_name}' is already used by another semantic data model. "
                    "Schema names must be unique across all semantic data models."
                )


async def validate_sdm(
    sdm: SemanticDataModel,
    storage: BaseStorage,
) -> None:
    """Validate a semantic data model (server-side validations).

    Performs validations that require database access.

    Args:
        sdm: The semantic data model to validate.
        storage: The storage instance.

    Raises:
        ValueError: If validation fails.
    """
    await _validate_unique_schema_names(sdm, storage, sdm.id if sdm.id else None)
