"""All environment variables exposed by the agent server.

This module centralizes all supported environment variables for the agent server.
These do not include environment variables exposed by other packages and
dependencies, even if used by the agent server.

Generally, our environment variables are prefixed with SEMA4AI_AGENT_SERVER_ to
avoid conflicts with other packages and dependencies.
"""

import os
import warnings
from typing import Any


def get_env_var(var_names: list[str], default: Any = None) -> Any:
    """Get an environment variable with warning for legacy variables.

    Args:
        var_names: List of environment variable names to check in order of preference.
                  The first one is considered the primary variable (no warning).
        default: Default value to return if none of the variables are set.

    Returns:
        The value of the first environment variable found, or the default.
    """
    primary = var_names[0]
    value = os.getenv(primary)
    if value is not None:
        return value

    # Check fallback variables with warnings
    for var_name in var_names[1:]:
        value = os.getenv(var_name)
        if value is not None:
            warnings.warn(
                f"Using deprecated environment variable {var_name}. "
                f"Please use {primary} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return value

    return default


# Several environment variables are supported for backwards compatibility, but
# we recommend using the SEMA4AI_AGENT_SERVER_ prefixed variables.

# Top level configuration file location
CONFIG_PATH = get_env_var(["SEMA4AI_AGENT_SERVER_CONFIG_PATH"])

# Logging
LOG_LEVEL = get_env_var(["SEMA4AI_AGENT_SERVER_LOG_LEVEL", "LOG_LEVEL"])
LOG_DIR = get_env_var(
    ["SEMA4AI_AGENT_SERVER_LOG_DIR", "SEMA4AI_STUDIO_LOG", "SEMA4AI_STUDIO_HOME"]
)
LOG_MAX_BACKUP_FILES = get_env_var(
    ["SEMA4AI_AGENT_SERVER_LOG_MAX_BACKUP_FILES", "LOG_MAX_BACKUP_FILES"]
)
LOG_FILE_SIZE = get_env_var(["SEMA4AI_AGENT_SERVER_LOG_FILE_SIZE", "LOG_FILE_SIZE"])

# Data directory
DATA_DIR = get_env_var(
    [
        "SEMA4AI_AGENT_SERVER_DATA_DIR",
        "SEMA4AI_AGENT_SERVER_HOME",
        "S4_AGENT_SERVER_HOME",  # for backwards compatibility with 1.2.5
        "SEMA4AI_STUDIO_HOME",
    ]
)

# Database
DB_TYPE = get_env_var(["SEMA4AI_AGENT_SERVER_DB_TYPE", "DB_TYPE"])

# PostgreSQL Configuration
POSTGRES_HOST = get_env_var(["SEMA4AI_AGENT_SERVER_POSTGRES_HOST", "POSTGRES_HOST"])
POSTGRES_PORT = get_env_var(["SEMA4AI_AGENT_SERVER_POSTGRES_PORT", "POSTGRES_PORT"])
POSTGRES_DB = get_env_var(["SEMA4AI_AGENT_SERVER_POSTGRES_DB", "POSTGRES_DB"])
POSTGRES_USER = get_env_var(["SEMA4AI_AGENT_SERVER_POSTGRES_USER", "POSTGRES_USER"])
POSTGRES_PASSWORD = get_env_var(
    ["SEMA4AI_AGENT_SERVER_POSTGRES_PASSWORD", "POSTGRES_PASSWORD"]
)

# Authentication
AUTH_TYPE = get_env_var(["SEMA4AI_AGENT_SERVER_AUTH_TYPE", "AUTH_TYPE"])

# File Management
FILE_MANAGEMENT_API_URL = get_env_var(
    ["SEMA4AI_AGENT_SERVER_FILE_MANAGEMENT_API_URL", "FILE_MANAGEMENT_API_URL"]
)
FILE_MANAGER_TYPE = get_env_var(["SEMA4AI_AGENT_SERVER_FILE_MANAGER_TYPE"])

# OpenTelemetry
OTEL_COLLECTOR_URL = get_env_var(
    ["SEMA4AI_AGENT_SERVER_OTEL_COLLECTOR_URL", "OTEL_COLLECTOR_URL"]
)
