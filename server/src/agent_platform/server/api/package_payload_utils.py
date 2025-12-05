from structlog import get_logger

from agent_platform.server.api.dependencies import StorageDependency

logger = get_logger(__name__)


def _strip_environment_specific_fields(sdm: dict) -> dict:
    """
    Remove environment-specific fields from SDM before storing.

    Environment-specific fields that are stripped:
    - data_connection_id in base_table (environment-specific UUID)
    - data_connection_name in base_table (resolved to ID during import)
    - file references (thread_id, file_ref) (environment-specific)

    Preserved fields (portable across environments):
    - database and schema in base_table (part of the SDM definition)
    - table name (part of the SDM definition)
    """
    import copy

    sdm_clean = copy.deepcopy(sdm)

    # Remove only environment-specific IDs and names (keep database/schema)
    for table in sdm_clean.get("tables", []):
        if "base_table" in table:
            table["base_table"].pop("data_connection_id", None)
            table["base_table"].pop("data_connection_name", None)
            # Note: database and schema are NOT stripped - they are part of the SDM definition

        # Remove file references
        if "file" in table:
            table.pop("file", None)

    return sdm_clean


def _normalize_sdm_for_comparison(sdm: dict) -> str:
    """
    Normalize SDM for comparison by converting to sorted JSON string.

    This ensures consistent comparison regardless of dict ordering.
    """
    import json

    # Strip environment fields first
    normalized = _strip_environment_specific_fields(sdm)

    # Convert to sorted JSON string for consistent comparison
    return json.dumps(normalized, sort_keys=True)


def find_matching_sdm(
    new_sdm: dict,
    existing_sdms: list[dict],
) -> str | None:
    """
    Find existing SDM that matches the new SDM being imported.

    Matching criteria:
    1. Same name (case-insensitive)
    2. Same content (after normalizing both)

    Args:
        new_sdm: New SDM content from package
        existing_sdms: List of existing SDMs in format [{sdm_id: sdm_content}, ...]

    Returns:
        existing SDM ID if match found, None otherwise
    """
    new_name = new_sdm.get("name", "").lower()
    new_normalized = _normalize_sdm_for_comparison(new_sdm)

    for existing_sdm_entry in existing_sdms:
        # existing_sdm_entry format: {sdm_id: sdm_content}
        for sdm_id, existing_sdm in existing_sdm_entry.items():
            existing_name = existing_sdm.get("name", "").lower()

            # Check name match
            if new_name == existing_name:
                existing_normalized = _normalize_sdm_for_comparison(existing_sdm)

                # Check content match
                if new_normalized == existing_normalized:
                    logger.info(
                        f"Found matching SDM: {sdm_id} for '{new_name}'",
                        sdm_id=sdm_id,
                        sdm_name=new_name,
                    )
                    return sdm_id  # Perfect match - reuse this SDM

    return None  # No match found - need to create new


async def resolve_data_connection_names(
    sdm_content: dict,
    storage: StorageDependency,
) -> dict:
    """
    Resolve data_connection_name to data_connection_id in SDM.

    If data_connection_name is present but data_connection_id is not,
    attempts to find the connection by name (case-insensitive).

    Args:
        sdm_content: SDM content from package
        storage: Storage dependency

    Returns:
        Updated SDM content with data_connection_id resolved (if found)
    """
    import copy

    sdm = copy.deepcopy(sdm_content)

    for table in sdm.get("tables", []):
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

    return sdm
