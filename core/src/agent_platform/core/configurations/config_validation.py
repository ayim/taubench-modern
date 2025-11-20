"""Configuration validation utilities.

This module provides validation for configuration types without circular dependencies.
"""

from enum import StrEnum

from agent_platform.core.errors import ErrorCode, PlatformHTTPError


class ConfigType(StrEnum):
    MAX_WORK_ITEM_PAYLOAD_SIZE = "MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB"
    MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE = "MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB"
    MAX_AGENTS = "MAX_AGENTS"
    MAX_PARALLEL_WORK_ITEMS = "MAX_PARALLEL_WORK_ITEMS_IN_PROCESS"
    MAX_MCP_SERVERS = "MAX_MCP_SERVERS_IN_AGENT"
    AGENT_THREAD_RETENTION_PERIOD = "AGENT_THREAD_RETENTION_PERIOD"
    POSTGRES_POOL_MAX_SIZE = "POSTGRES_POOL_MAX_SIZE"
    MAX_CACHE_SIZE = "MAX_CACHE_SIZE_IN_BYTES"
    WORK_ITEM_TIMEOUT_SECONDS = "WORK_ITEM_TIMEOUT_SECONDS"


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
    # First validate the config type exists and normalize to enum
    validate_config_type(config_type)
    config_type_enum = ConfigType(config_type)

    try:
        int_value = int(value)
    except ValueError as e:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=f"Invalid value '{value}' for {config_type}: must be a valid integer",
        ) from e

    # Common rule: all config values should be non-negative
    if int_value < 0:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=f"Invalid value {int_value} for {config_type}: must be >= 0 (non-negative)",
        )

    # Specific rules
    if config_type_enum is ConfigType.POSTGRES_POOL_MAX_SIZE:
        # Pool size must be at least 1
        if int_value < 1:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"Invalid value {int_value} for {config_type}: must be >= 1",
            )

    return int_value
