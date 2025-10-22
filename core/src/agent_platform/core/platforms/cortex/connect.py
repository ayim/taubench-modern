import threading
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SPCSConnnectionConfig(Configuration):
    """Configuration for a Snowflake connection in SPCS."""

    # We can never have the SEMA4AI_AGENT_SERVER_ variants... because it's defined
    # by the container. Not going to remove today
    host: str = field(
        default="https://snowflake.com",
        metadata=FieldMetadata(
            description="The host to use.",
            env_vars=["SEMA4AI_AGENT_SERVER_SNOWFLAKE_HOST", "SNOWFLAKE_HOST"],
        ),
    )
    account: str | None = field(
        default=None,
        metadata=FieldMetadata(
            description="The Snowflake account to use.",
            env_vars=["SEMA4AI_AGENT_SERVER_SNOWFLAKE_ACCOUNT", "SNOWFLAKE_ACCOUNT"],
        ),
    )
    role: str | None = field(
        default=None,
        metadata=FieldMetadata(
            description="The role to use.",
            env_vars=["SEMA4AI_AGENT_SERVER_SNOWFLAKE_ROLE", "SNOWFLAKE_ROLE"],
        ),
    )
    warehouse: str | None = field(
        default=None,
        metadata=FieldMetadata(
            description="The warehouse to use.",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_SNOWFLAKE_WAREHOUSE",
                "SNOWFLAKE_WAREHOUSE",
            ],
        ),
    )
    database: str | None = field(
        default=None,
        metadata=FieldMetadata(
            description="The database to use.",
            env_vars=["SEMA4AI_AGENT_SERVER_SNOWFLAKE_DATABASE", "SNOWFLAKE_DATABASE"],
        ),
    )
    schema: str | None = field(
        default=None,
        metadata=FieldMetadata(
            description="The schema to use.",
            env_vars=["SEMA4AI_AGENT_SERVER_SNOWFLAKE_SCHEMA", "SNOWFLAKE_SCHEMA"],
        ),
    )
    port: int = field(
        default=443,
        metadata=FieldMetadata(
            description="The port to use.",
            env_vars=["SEMA4AI_AGENT_SERVER_SNOWFLAKE_PORT", "SNOWFLAKE_PORT"],
        ),
    )


class SnowflakeConfigurationError(Exception):
    """Raised when there are configuration-related issues with Snowflake connection."""

    pass


class SnowflakeAuthenticationError(Exception):
    """Raised when there are authentication-related issues with Snowflake connection."""

    pass


def _get_dict_value(source: dict, key: str, default_value):
    return source.get(key) or default_value


def _get_mandatory_dict_value(source: dict, key: str):
    value = _get_dict_value(source, key, None)
    if value is None:
        raise SnowflakeConfigurationError(f'Required configuration attribute "{key}" not found')
    return value


def _parse_snowflake_oauth_connection_details(
    linking_details: dict,
    role: str | None = None,
    warehouse: str | None = None,
    database: str | None = None,
    schema: str | None = None,
) -> dict:
    token_path = _get_mandatory_dict_value(linking_details, "tokenPath")
    try:
        token = Path(token_path).read_text().strip()
    except Exception as e:
        raise SnowflakeConfigurationError(
            f'Failed to read OAuth token from file "{token_path!s}": {e!s}'
        ) from e
    authenticator = _get_mandatory_dict_value(linking_details, "authenticator")
    if authenticator != "OAUTH":
        raise SnowflakeConfigurationError(
            f'Unsupported authenticator "{authenticator}" for OAuth based configuration'
        )
    config = {
        "authenticator": authenticator,
        "account": _get_mandatory_dict_value(linking_details, "account"),
        "role": role or _get_mandatory_dict_value(linking_details, "role"),
        "warehouse": warehouse or _get_dict_value(linking_details, "warehouse", None),
        "database": database,
        "schema": schema,
        "client_session_keep_alive": True,
        "token": token,
    }
    return config


def _parse_snowflake_private_key_connection_details(
    linking_details: dict,
    role: str | None = None,
    warehouse: str | None = None,
    database: str | None = None,
    schema: str | None = None,
) -> dict:
    authenticator = _get_dict_value(linking_details, "authenticator", "SNOWFLAKE_JWT")
    if authenticator != "SNOWFLAKE_JWT":
        raise SnowflakeConfigurationError(
            f'Unsupported authenticator "{authenticator}" for private key based configuration'
        )
    config = {
        "authenticator": authenticator,
        "account": _get_mandatory_dict_value(linking_details, "account"),
        "user": _get_mandatory_dict_value(linking_details, "user"),
        "private_key_file": _get_mandatory_dict_value(linking_details, "privateKeyPath"),
        "role": role or _get_dict_value(linking_details, "role", None),
        "warehouse": warehouse or _get_dict_value(linking_details, "warehouse", None),
        "database": database,
        "schema": schema,
        "client_session_keep_alive": True,
    }
    private_key_file_pwd = _get_dict_value(linking_details, "privateKeyPassphrase", None)
    if private_key_file_pwd is not None:
        config["private_key_file_pwd"] = private_key_file_pwd
    return config


def get_snowflake_connection_details_from_file(
    config_file_path: Path,
    role: str | None = None,
    warehouse: str | None = None,
    database: str | None = None,
    schema: str | None = None,
) -> dict:
    if not config_file_path.exists():
        raise SnowflakeConfigurationError(f"Configuration file {config_file_path} not found")

    try:
        import json

        config_json = json.loads(config_file_path.read_text())
    except Exception as e:
        raise SnowflakeConfigurationError(
            f"Failed to read authentication config as JSON from {config_file_path!s}: {e!s}"
        ) from e

    # Default to SNOWFLAKE_PRIVATE_KEY as old SPACE/Studio did not specify the "type" at all
    auth_type = _get_dict_value(config_json, "type", "SNOWFLAKE_PRIVATE_KEY")
    linking_details = _get_mandatory_dict_value(config_json, "linkingDetails")

    if auth_type in ("SNOWFLAKE_OAUTH_PARTNER", "SNOWFLAKE_OAUTH_CUSTOM"):
        return _parse_snowflake_oauth_connection_details(
            linking_details, role, warehouse, database, schema
        )
    if auth_type == "SNOWFLAKE_PRIVATE_KEY":
        return _parse_snowflake_private_key_connection_details(
            linking_details, role, warehouse, database, schema
        )

    raise SnowflakeConfigurationError(f'Configuration type "{auth_type}" not supported')


_snowpark_create_lock = threading.Lock()


def safe_get_or_create_session(session_builder):
    """
    Takes a Snowpark SessionBuilder, returns the session inside
    our own lock so that only one thread at a time can call builder.getOrCreate().
    """
    logger.info("Getting or creating Snowpark session, entering lock")
    with _snowpark_create_lock:
        logger.info("Creating Snowpark session")
        return session_builder.getOrCreate()


def get_connection_details(  # noqa: PLR0913
    role: str | None = None,
    warehouse: str | None = None,
    database: str | None = None,
    schema: str | None = None,
    username: str | None = None,
    password: str | None = None,
    account: str | None = None,
) -> dict:
    """
    Get Snowflake connection details based on the environment.

    This function first checks if running in SPCS by looking for the token file.
    If found, it uses SPCS authentication, otherwise falls back to local
    config-based authentication.

    Args:
        role: Snowflake role to use. Falls back to env var
        warehouse: Snowflake warehouse to use. Falls back to env var
        database: Snowflake database to use. Falls back to env var
        schema: Snowflake schema to use. Falls back to env var

    Returns:
        dict: Connection info for Snowflake containing environment-specific fields:
            For SPCS:
                - host: from SNOWFLAKE_HOST env var
                - account: from SNOWFLAKE_ACCOUNT env var
                - authenticator: "OAUTH"
                - token: from SPCS token file
                - role, warehouse, database, schema: from args or env vars
                - client_session_keep_alive: True
                - port: from SNOWFLAKE_PORT env var
                - protocol: "https"
            For local machine:
                - account: from config
                - user: from config
                - role: from args or config
                - authenticator: from config (ID_TOKEN, OAUTH, or SNOWFLAKE_JWT)
                - warehouse, database, schema: from args
                - client_session_keep_alive: True
            Plus authentication-specific fields:
                - For ID_TOKEN: session_token and auth_class
                - For OAUTH: token
                - For SNOWFLAKE_JWT: private_key and private_key_password

    Raises:
        SnowflakeAuthenticationError: If required credentials are missing or invalid
    """
    has_user_password = username is not None and password is not None
    has_account = account is not None
    logger.info("Checking for user/password auth")
    if has_user_password and has_account:
        logger.info("User/password auth found")
        return {
            "account": account,
            "user": username,
            "password": password,
            "role": role,
        }

    logger.info("Checking for SPCS environment")
    # Check for SPCS environment first
    token_file_path = Path("/snowflake/session/token")
    if token_file_path.exists():
        logger.info("We're running in SPCS")
        if not SPCSConnnectionConfig.host or not SPCSConnnectionConfig.account:
            logger.error(
                "Required environment variables SNOWFLAKE_HOST and SNOWFLAKE_ACCOUNT must be set",
            )
            raise SnowflakeAuthenticationError(
                "Required environment variables SNOWFLAKE_HOST and SNOWFLAKE_ACCOUNT must be set",
            )

        return {
            "host": SPCSConnnectionConfig.host,
            "account": SPCSConnnectionConfig.account,
            "authenticator": "OAUTH",
            "token": token_file_path.read_text(),
            "role": role or SPCSConnnectionConfig.role,
            "warehouse": warehouse or SPCSConnnectionConfig.warehouse,
            "database": database or SPCSConnnectionConfig.database,
            "schema": schema or SPCSConnnectionConfig.schema,
            "client_session_keep_alive": True,
            "port": SPCSConnnectionConfig.port,
            "protocol": "https",
        }

    # Fall back to local config-based authentication
    try:
        logger.info("Reading local auth file")
        # DO NOT TOUCH THIS PATH. It's not configurable, it's a contract
        # between us, Studio, space-client, ACE, etc. And it's baked into
        # each of those as Path.home() / ".sema4ai" / "sf-auth.json". If it
        # ever _were_ to change, it'd be a big discussion.
        config_file_path = Path.home() / ".sema4ai" / "sf-auth.json"
        return get_snowflake_connection_details_from_file(
            config_file_path, role, warehouse, database, schema
        )
    except Exception as e:
        logger.error(
            f"Failed to read authentication config: {e!s}",
        )
        raise SnowflakeAuthenticationError(
            f"Failed to read authentication config: {e!s}",
        ) from e
