import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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

    # Preset fields
    authenticator: Literal["OAUTH"] = field(default="OAUTH", init=False)
    protocol: Literal["https"] = field(default="https", init=False)
    client_session_keep_alive: bool = field(default=True, init=False)


@dataclass
class LinkingDetails:
    account: str
    user: str
    role: str
    application_url: str
    private_key_path: str
    private_key_passphrase: str | None = None

    def model_dump(self) -> dict:
        return {
            "account": self.account,
            "user": self.user,
            "role": self.role,
            "application_url": self.application_url,
        }


@dataclass
class AuthDetails:
    authenticator: Literal["ID_TOKEN", "OAUTH", "SNOWFLAKE_JWT"] = "SNOWFLAKE_JWT"
    token: str | None = None

    def model_dump(self) -> dict:
        return {
            "authenticator": self.authenticator,
            "token": self.token,
        }


@dataclass
class SnowflakeAuth:
    linking_details: LinkingDetails = field()
    version: str = field(default="1.0.0")
    auth_details: AuthDetails = field(default_factory=AuthDetails)

    @classmethod
    def from_dict(cls, data: dict) -> "SnowflakeAuth":
        if (
            "linkingDetails" not in data
            or data["linkingDetails"] is None
            or not isinstance(data["linkingDetails"], dict)
        ):
            logger.error(f"Invalid linkingDetails: {json.dumps(data, indent=2)}")
            raise ValueError("linkingDetails is required to be present and a dict")

        authenticator = data["linkingDetails"].get("authenticator", "SNOWFLAKE_JWT")
        if authenticator not in ["ID_TOKEN", "OAUTH", "SNOWFLAKE_JWT"]:
            logger.error(f"Invalid authenticator: {authenticator}")
            raise ValueError(f"Invalid authenticator: {authenticator}")

        # Remove the authenticator from the linkingDetails dict
        if "authenticator" in data["linkingDetails"]:
            del data["linkingDetails"]["authenticator"]

        linking_details = LinkingDetails(
            account=data["linkingDetails"]["account"],
            user=data["linkingDetails"]["user"],
            role=data["linkingDetails"]["role"],
            application_url=data["linkingDetails"]["applicationUrl"],
            private_key_path=data["linkingDetails"]["privateKeyPath"],
            private_key_passphrase=(
                data["linkingDetails"]["privateKeyPassphrase"]
                if "privateKeyPassphrase" in data["linkingDetails"]
                else None
            ),
        )

        ld_as_dict = linking_details.model_dump()
        if ld_as_dict.get("private_key_passphrase"):
            ld_as_dict["private_key_passphrase"] = "REDACTED"
        ld_as_json = json.dumps(ld_as_dict, indent=2)
        logger.info(f"Parsed SnowflakeAuth LinkingDetails: {ld_as_json}")

        auth_details = AuthDetails(
            authenticator=authenticator,
            token=(
                data["authDetails"]["token"] if "token" in data.get("authDetails", {}) else None
            ),
        )

        ad_as_dict = auth_details.model_dump()
        if (
            "token" in ad_as_dict
            # Careful, still want to know in log if it's empty or none
            and ad_as_dict["token"] is not None
            and ad_as_dict["token"] != ""
        ):
            ad_as_dict["token"] = "REDACTED"
        ad_as_json = json.dumps(ad_as_dict, indent=2)
        logger.info(f"Parsed SnowflakeAuth AuthDetails: {ad_as_json}")

        return cls(
            version=data["version"] if "version" in data else "1.0.0",
            linking_details=linking_details,
            auth_details=auth_details,
        )


class SnowflakeAuthenticationError(Exception):
    """Raised when there are authentication-related issues with Snowflake connection."""

    pass


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
        auth_data = json.loads(
            # DO NOT TOUCH THIS PATH. It's not configurable, it's a contract
            # between us, Studio, space-client, ACE, etc. And it's baked into
            # each of those as Path.home() / ".sema4ai" / "sf-auth.json". If it
            # ever _were_ to change, it'd be a big discussion.
            (Path.home() / ".sema4ai" / "sf-auth.json").read_text()
        )
        logger.info("Parsing local auth file")
        sf_auth = SnowflakeAuth.from_dict(auth_data)
    except Exception as e:
        logger.error(
            f"Failed to read authentication config: {e!s}",
        )
        raise SnowflakeAuthenticationError(
            f"Failed to read authentication config: {e!s}",
        ) from e

    config = {
        "account": account or sf_auth.linking_details.account,
        "user": username or sf_auth.linking_details.user,
        "role": role or sf_auth.linking_details.role,
        "authenticator": sf_auth.auth_details.authenticator,
        "warehouse": warehouse,
        "database": database,
        "schema": schema,
        "client_session_keep_alive": True,
    }

    if sf_auth.auth_details.authenticator == "SNOWFLAKE_JWT":
        logger.info("SNOWFLAKE_JWT mode set")
        config["private_key_file"] = sf_auth.linking_details.private_key_path
        if (
            sf_auth.linking_details.private_key_passphrase is not None
            and sf_auth.linking_details.private_key_passphrase != ""
        ):
            logger.info("Setting private key file passphrase")
            config["private_key_file_pwd"] = sf_auth.linking_details.private_key_passphrase
    else:
        logger.error(
            f"Unsupported authenticator: {sf_auth.auth_details.authenticator}",
        )
        raise SnowflakeAuthenticationError(
            f"Unsupported authenticator: {sf_auth.auth_details.authenticator}",
        )

    logger.info("Successfully built connection config")
    return config
