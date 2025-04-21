# TODO: this is a copy of https://github.com/Sema4AI/cookbook/blob/feature/snowflake-actions/actions/snowflake-actions/utils.py
# Someday we should use this as a shared dependency. (Not today, no time.)

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Literal

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.server.constants import SystemPaths


@dataclass(frozen=True)
class SPCSConnnectionConfig(Configuration):
    """Configuration for a Snowflake connection in SPCS."""

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
    token: str | None = field(
        default=None,
        metadata=FieldMetadata(
            description="The SPCS token to use. If not provided, the token will be "
            "read from the token_file_path.",
        ),
    )
    token_file_path: Path = field(
        default=Path("/snowflake/session/token"),
        metadata=FieldMetadata(
            description="The path to the SPCS token file.",
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

    def __post_init__(self) -> None:
        if self.token is None and self.token_file_path.exists():
            object.__setattr__(
                self,
                "token",
                self.token_file_path.read_text().strip(),
            )


@dataclass(frozen=True)
class SnowflakeAuthConfig(Configuration):
    """Configuration for Snowflake authentication.

    Used to set the server to expect a specific authentication method and
    where to load it from if it's not provided directly.
    """

    depends_on: ClassVar[list[type[Configuration]]] = [
        SystemPaths,
        SPCSConnnectionConfig,
    ]

    mode: Literal["SPCS", "LOCAL", "CREDENTIALS"] = field(
        default="CREDENTIALS",
        metadata=FieldMetadata(
            description="The mode to use for authentication.\n"
            "- SPCS: Expect SPCS configuration to be set or related environment "
            "variables.\n"
            "- LOCAL: Expect a local authentication file at the provided path.\n"
            "- CREDENTIALS: The default fallback mode, this allows for username and "
            "password to be provided directly.",
            env_vars=["SEMA4AI_AGENT_SERVER_SNOWFLAKE_AUTH_MODE"],
        ),
    )
    local_auth_file_path: Path = field(
        default=SystemPaths.data_dir / "sf-auth.json",
        metadata=FieldMetadata(
            description="The path to the local authentication file.",
        ),
    )

    def __post_init__(self) -> None:
        # Try to guess the mode
        if self.mode == "CREDENTIALS":
            if SPCSConnnectionConfig.token is not None:
                object.__setattr__(self, "mode", "SPCS")
            elif self.local_auth_file_path.exists():
                object.__setattr__(self, "mode", "LOCAL")


@dataclass
class LinkingDetails:
    account: str
    user: str
    role: str
    application_url: str
    private_key_path: str
    private_key_passphrase: str | None = None


@dataclass
class AuthDetails:
    authenticator: Literal["ID_TOKEN", "OAUTH", "SNOWFLAKE_JWT"] = "SNOWFLAKE_JWT"
    token: str | None = None


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
            raise ValueError("linkingDetails is required to be present and a dict")

        authenticator = data["linkingDetails"].get("authenticator", "SNOWFLAKE_JWT")
        if authenticator not in ["ID_TOKEN", "OAUTH", "SNOWFLAKE_JWT"]:
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

        auth_details = AuthDetails(
            authenticator=authenticator,
            token=(
                data["authDetails"]["token"]
                if "token" in data.get("authDetails", {})
                else None
            ),
        )

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
    with _snowpark_create_lock:
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
    if has_user_password and has_account:
        return {
            "account": account,
            "user": username,
            "password": password,
            "role": role,
        }

    # Check for SPCS environment first
    if SnowflakeAuthConfig.mode == "SPCS":
        if not SPCSConnnectionConfig.host or not SPCSConnnectionConfig.account:
            raise SnowflakeAuthenticationError(
                "Required environment variables SNOWFLAKE_HOST and "
                "SNOWFLAKE_ACCOUNT must be set",
            )

        return {
            "host": SPCSConnnectionConfig.host,
            "account": SPCSConnnectionConfig.account,
            "authenticator": "OAUTH",
            "token": SPCSConnnectionConfig.token,
            "role": role or SPCSConnnectionConfig.role,
            "warehouse": warehouse or SPCSConnnectionConfig.warehouse,
            "database": database or SPCSConnnectionConfig.database,
            "schema": schema or SPCSConnnectionConfig.schema,
            "client_session_keep_alive": True,
            "port": SPCSConnnectionConfig.port,
            "protocol": "https",
        }

    # Fall back to local config-based authentication
    if SnowflakeAuthConfig.mode == "LOCAL":
        try:
            auth_data = json.loads(SnowflakeAuthConfig.local_auth_file_path.read_text())
            sf_auth = SnowflakeAuth.from_dict(auth_data)
        except Exception as e:
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
            config["private_key_file"] = sf_auth.linking_details.private_key_path
            if (
                sf_auth.linking_details.private_key_passphrase is not None
                and sf_auth.linking_details.private_key_passphrase != ""
            ):
                config["private_key_file_pwd"] = (
                    sf_auth.linking_details.private_key_passphrase
                )
        else:
            raise SnowflakeAuthenticationError(
                f"Unsupported authenticator: {sf_auth.auth_details.authenticator}",
            )

        return config

    # Fall back to username/password auth (provided directly)
    if not has_user_password or not has_account:
        raise SnowflakeAuthenticationError(
            "Not linked to SPCS, and no local account/username/password provided",
        )

    return {
        "account": account,
        "user": username,
        "password": password,
        "role": role,
        "warehouse": warehouse,
        "database": database,
        "schema": schema,
        "client_session_keep_alive": True,
    }
