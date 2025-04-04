# TODO: this is a copy of https://github.com/Sema4AI/cookbook/blob/feature/snowflake-actions/actions/snowflake-actions/utils.py
# Someday we should use this as a shared dependency. (Not today, no time.)

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SPCS_TOKEN_FILE_PATH = Path("/snowflake/session/token")
LOCAL_AUTH_FILE_PATH = Path.home() / ".sema4ai" / "sf-auth.json"


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
    if SPCS_TOKEN_FILE_PATH.exists():
        token = SPCS_TOKEN_FILE_PATH.read_text().strip()

        host = os.getenv("SNOWFLAKE_HOST")
        account = os.getenv("SNOWFLAKE_ACCOUNT")

        if not host or not account:
            raise SnowflakeAuthenticationError(
                "Required environment variables SNOWFLAKE_HOST and "
                "SNOWFLAKE_ACCOUNT must be set",
            )

        return {
            "host": host,
            "account": account,
            "authenticator": "OAUTH",
            "token": token,
            "role": role or os.getenv("SNOWFLAKE_ROLE"),
            "warehouse": warehouse or os.getenv("SNOWFLAKE_WAREHOUSE"),
            "database": database or os.getenv("SNOWFLAKE_DATABASE"),
            "schema": schema or os.getenv("SNOWFLAKE_SCHEMA"),
            "client_session_keep_alive": True,
            "port": os.getenv("SNOWFLAKE_PORT"),
            "protocol": "https",
        }

    # Fall back to local config-based authentication
    if LOCAL_AUTH_FILE_PATH.exists():
        try:
            auth_data = json.loads(LOCAL_AUTH_FILE_PATH.read_text())
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
