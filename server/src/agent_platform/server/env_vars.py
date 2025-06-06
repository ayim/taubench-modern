"""All environment variables exposed by the agent server.

This module centralizes all supported environment variables for the agent server.
These do not include environment variables exposed by other packages and
dependencies, even if used by the agent server.

Generally, our environment variables are prefixed with SEMA4AI_AGENT_SERVER_ to
avoid conflicts with other packages and dependencies.

Environment variables are dynamically applied to configuration classes based on
the "env_vars" metadata in each field. This approach allows configuration classes
to specify which environment variables can override each setting.

Example field definition with environment variable overrides:
```python
db_type: Literal["sqlite", "postgres"] = field(
    default="sqlite",
    metadata={
        "description": "The type of database to use.",
        "env_vars": ["SEMA4AI_AGENT_SERVER_DB_TYPE", "DB_TYPE"],
    },
)
```

The precedence order for configuration values is:
1. Command line arguments (highest priority)
2. Environment variables (applied dynamically based on field metadata)
3. Configuration file values
4. Default values (hardcoded in the configuration classes)
"""

import os
import re
import warnings


def _get_env_var_by_regex(regex: str | re.Pattern) -> dict[str, str]:
    """Get all environment variables that match the regex pattern."""
    if isinstance(regex, str):
        regex = re.compile(regex)
    return {k: v for k, v in os.environ.items() if regex.match(k)}


def get_env_var(
    var_names: list[str] | None = None,
    default: str | None = None,
    *,
    regex: str | re.Pattern | None = None,
) -> str | dict[str, str] | None:
    """Get an environment variable with warning for legacy variables.

    You may provide a regex pattern to match multiple environment variables,
    in which case the return is a dictionary of the matched variables.

    Args:
        var_names: List of environment variable names to check in order of preference.
                  The first one is considered the primary variable (no warning).
        default: Default value to return if none of the variables are set.
        regex: Regex pattern to match multiple environment variables, in which case
              the return is a dictionary of the matched variables.
    Returns:
        The value of the first environment variable found, or the default.
        If regex is provided, the return is a dictionary of the matched variables.

    Raises:
        ValueError: If both var_names and regex are provided.
    """
    # Validate inputs
    if var_names is not None and regex is not None:
        raise ValueError("Cannot provide both var_names and regex.")

    # Handle regex pattern case
    if regex is not None:
        return _get_env_var_by_regex(regex)

    # Handle no inputs case
    if var_names is None:
        return default

    var_names = var_names or []
    primary = var_names[0]
    value = os.getenv(primary)
    if value is not None:
        return value

    # Check fallback variables with warnings
    for var_name in var_names[1:]:
        value = os.getenv(var_name)
        if value is not None:
            warnings.warn(
                f"Using deprecated environment variable {var_name}. Please use {primary} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return value

    return default


# Environment variables are defined in Configuration classes throughtout the
# server. These are provided here for use before the configuration system is
# initialized.

# Top level configuration file location
CONFIG_PATH = get_env_var(["SEMA4AI_AGENT_SERVER_CONFIG_PATH"])

# Logging
LOG_LEVEL = get_env_var(["SEMA4AI_AGENT_SERVER_LOG_LEVEL", "LOG_LEVEL"])
