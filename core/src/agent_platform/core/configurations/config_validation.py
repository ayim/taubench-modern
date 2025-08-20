"""Configuration validation utilities.

This module provides validation for configuration types without circular dependencies.
"""

from enum import StrEnum


class ConfigType(StrEnum):
    MAX_WORK_ITEM_PAYLOAD_SIZE = "MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB"
    MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE = "MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB"
    MAX_AGENTS = "MAX_AGENTS"
    MAX_PARALLEL_WORK_ITEMS = "MAX_PARALLEL_WORK_ITEMS_IN_PROCESS"
    MAX_MCP_SERVERS = "MAX_MCP_SERVERS_IN_AGENT"
    AGENT_THREAD_RETENTION_PERIOD = "AGENT_THREAD_RETENTION_PERIOD"


def validate_config_type(config_type: str) -> None:
    """Validate that a config_type is one of the allowed values.

    Args:
        config_type: The configuration type to validate

    Raises:
        ValueError: If the config_type is not valid
    """

    try:
        ConfigType(config_type)
    except ValueError:
        raise ValueError(
            f"Invalid config_type: {config_type}. "
            f"Must be one of: {sorted(str(item) for item in ConfigType)}"
        ) from None
    # if config_type not in ALL_CONFIG_TYPES:


def validate_config_value(config_type: ConfigType | str, value: str) -> int:
    """Validate and convert a config value.

    Args:
        config_type: The configuration type to validate against
        value: The string value to validate and convert

    Returns:
        int: The validated integer value

    Raises:
        ValueError: If the value is invalid
    """
    # First validate the config type exists
    validate_config_type(config_type)

    try:
        int_value = int(value)
    except ValueError as e:
        raise ValueError(
            f"Invalid value '{value}' for {config_type}: must be a valid integer"
        ) from e

    # All config types should be non-negative.
    # Later, when there is an usecase, we can use the config_type
    # and do match case to validate the value.
    if int_value < 0:
        raise ValueError(
            f"Invalid value {int_value} for {config_type}: must be >= 0 (non-negative)"
        )

    return int_value
