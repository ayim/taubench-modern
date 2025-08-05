"""Configuration validation utilities.

This module provides validation for configuration types without circular dependencies.
"""

from typing import Literal

# Storage key constants - single source of truth
STORAGE_KEY_MAX_WORK_ITEM_PAYLOAD_SIZE = "MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB"
STORAGE_KEY_MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE = "MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB"
STORAGE_KEY_MAX_AGENTS = "MAX_AGENTS"
STORAGE_KEY_MAX_PARALLEL_WORK_ITEMS = "MAX_PARALLEL_WORK_ITEMS_IN_PROCESS"
STORAGE_KEY_MAX_MCP_SERVERS = "MAX_MCP_SERVERS_IN_AGENT"

# Generate validation types from constants to avoid duplication
_ALL_STORAGE_KEYS = [
    STORAGE_KEY_MAX_WORK_ITEM_PAYLOAD_SIZE,
    STORAGE_KEY_MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE,
    STORAGE_KEY_MAX_AGENTS,
    STORAGE_KEY_MAX_PARALLEL_WORK_ITEMS,
    STORAGE_KEY_MAX_MCP_SERVERS,
]

# Type alias for strictly typed config types
ConfigType = Literal[
    "MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB",
    "MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB",
    "MAX_AGENTS",
    "MAX_PARALLEL_WORK_ITEMS_IN_PROCESS",
    "MAX_MCP_SERVERS_IN_AGENT",
]

# All valid storage keys for validation (generated from constants)
ALL_CONFIG_TYPES: frozenset[str] = frozenset(_ALL_STORAGE_KEYS)


def validate_config_type(config_type: str) -> None:
    """Validate that a config_type is one of the allowed values.

    Args:
        config_type: The configuration type to validate

    Raises:
        ValueError: If the config_type is not valid
    """
    if config_type not in ALL_CONFIG_TYPES:
        raise ValueError(
            f"Invalid config_type: {config_type}. Must be one of: {sorted(ALL_CONFIG_TYPES)}"
        )
