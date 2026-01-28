from __future__ import annotations

from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.server.api.dependencies import StorageDependency

logger = get_logger(__name__)


def find_matching_sdm(
    new_sdm: SemanticDataModel,
    existing_sdms: list[dict],
) -> str | None:
    """
    Find existing SDM that matches the new SDM being imported.

    Matching criteria:
    1. Same name (case-insensitive)
    2. Same content (after normalizing both)

    Args:
        new_sdm: New Semantic Data Model from package
        existing_sdms: List of existing SDMs in format [{sdm_id: sdm_content}, ...]

    Returns:
        existing SDM ID if match found, None otherwise
    """
    new_name = (new_sdm.name or "").lower()
    # Exclude metadata from comparison (it's provenance/inspection data, not semantic structure)
    new_normalized_str = new_sdm.to_comparable_json(exclude_metadata=True)

    for existing_sdm_entry in existing_sdms:
        # existing_sdm_entry format: {sdm_id: sdm_content}
        for sdm_id, existing_sdm_dict in existing_sdm_entry.items():
            # Convert to SemanticDataModel if needed
            if isinstance(existing_sdm_dict, dict):
                existing_sdm_typed = SemanticDataModel.model_validate(existing_sdm_dict)
            else:
                existing_sdm_typed = existing_sdm_dict

            existing_name = (existing_sdm_typed.name or "").lower()

            # Check name match
            if new_name == existing_name:
                # Exclude metadata from comparison (it's provenance/inspection data, not semantic structure)
                existing_normalized_str = existing_sdm_typed.to_comparable_json(exclude_metadata=True)

                # Check content match (compare JSON strings for consistency)
                if new_normalized_str == existing_normalized_str:
                    logger.info(
                        f"Found matching SDM: {sdm_id} for '{new_name}'",
                        sdm_id=sdm_id,
                        sdm_name=new_name,
                    )
                    return sdm_id  # Perfect match - reuse this SDM

    return None  # No match found - need to create new


async def resolve_data_connection_names(
    sdm: SemanticDataModel,
    storage: StorageDependency,
) -> SemanticDataModel:
    """
    Resolve data_connection_name to data_connection_id in SDM.

    If data_connection_name is present but data_connection_id is not,
    attempts to find the connection by name (case-insensitive).

    Args:
        sdm: Semantic Data Model to resolve
        storage: Storage dependency

    Returns:
        Updated SDM with data_connection_id resolved (if found)
    """

    # Convert to dict for manipulation, then back to SemanticDataModel
    # model_dump() already performs a deep copy, so no need for additional copy.deepcopy()
    sdm_dict = sdm.model_dump(exclude_none=False)

    for table in sdm_dict.get("tables", []):
        base_table = table.get("base_table", {})

        # If name is present but ID is not
        if "data_connection_name" in base_table and not base_table.get("data_connection_id"):
            name = base_table["data_connection_name"]

            # Try to find connection by name
            connection = await storage.get_data_connection_by_name(name)

            if connection:
                base_table["data_connection_id"] = connection.id
                logger.info(
                    f"Resolved data connection '{name}' → {connection.id}",
                    connection_name=name,
                    connection_id=connection.id,
                )
            else:
                logger.warning(
                    f"Data connection '{name}' not found. SDM will need manual configuration.",
                    connection_name=name,
                )

    # Convert back to SemanticDataModel (TypedDict is just a type annotation)
    return SemanticDataModel.model_validate(sdm_dict)
