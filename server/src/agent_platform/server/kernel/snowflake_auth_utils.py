"""Utilities for Snowflake authentication with linked configurations.

This module handles reading and processing Snowflake authentication files
from ~/.sema4ai/sf-auth.json and supports multiple authentication methods.
"""

from __future__ import annotations

import asyncio
import typing
from typing import Any

from structlog import get_logger

if typing.TYPE_CHECKING:
    from agent_platform.core.payloads.data_connection import (
        SnowflakeLinkedConfiguration,
    )

logger = get_logger(__name__)


class SnowflakeAuthError(Exception):
    """Error raised when Snowflake authentication fails."""


def _load_private_key_from_file(private_key_path: str, private_key_passphrase: str | None) -> bytes:
    """Load and serialize a private key from a file.

    Args:
        private_key_path: Path to the private key file
        private_key_passphrase: Optional passphrase for encrypted keys

    Returns:
        Private key bytes in DER format (PKCS8)

    Raises:
        ValueError: If the file cannot be read or key format is invalid
    """
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    try:
        with open(private_key_path, "rb") as key_file:
            private_key_data = key_file.read()
    except FileNotFoundError as e:
        raise ValueError(f"Private key file not found: {private_key_path}") from e
    except PermissionError as e:
        raise ValueError(f"Permission denied reading private key file: {private_key_path}") from e
    except OSError as e:
        raise ValueError(f"Error reading private key file {private_key_path}: {e}") from e

    # Load the private key, optionally with a passphrase
    passphrase = private_key_passphrase.encode() if private_key_passphrase else None
    try:
        private_key = serialization.load_pem_private_key(
            private_key_data,
            password=passphrase,
            backend=default_backend(),
        )
    except ValueError as e:
        raise ValueError(f"Invalid private key format or incorrect passphrase: {e}") from e

    # Serialize to DER format (bytes) as expected by Snowflake connector
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


async def _read_auth_file(auth_file_path: typing.Any) -> dict[str, typing.Any]:
    """Read and parse Snowflake auth file asynchronously.

    Args:
        auth_file_path: Path to the auth file

    Returns:
        Parsed auth data as dictionary

    Raises:
        SnowflakeAuthError: If file cannot be read or parsed
    """
    import json

    def _read_and_parse():
        try:
            with open(auth_file_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError as e:
            raise SnowflakeAuthError(
                f"Snowflake authentication file not found. Expected file at: {auth_file_path}"
            ) from e
        except PermissionError as e:
            raise SnowflakeAuthError(
                f"Permission denied reading Snowflake authentication file at: {auth_file_path}"
            ) from e
        except json.JSONDecodeError as e:
            raise SnowflakeAuthError(
                "Failed to parse Snowflake authentication file at "
                f"{auth_file_path}. Invalid JSON format: {e}"
            ) from e
        except OSError as e:
            raise SnowflakeAuthError(
                f"Failed to read Snowflake authentication file at {auth_file_path}: {e}"
            ) from e
        except Exception as e:
            raise SnowflakeAuthError(
                f"Unexpected error reading Snowflake authentication file at {auth_file_path}: {e}"
            ) from e

    return await asyncio.to_thread(_read_and_parse)


async def _read_token_file(token_path: str) -> str:
    """Read OAuth token file asynchronously.

    Args:
        token_path: Path to the token file

    Returns:
        Token string

    Raises:
        SnowflakeAuthError: If file cannot be read
    """

    def _read_token():
        try:
            with open(token_path, encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError as e:
            raise SnowflakeAuthError(
                f"OAuth token file not found at: {token_path}. "
                "Please re-authenticate with Snowflake."
            ) from e
        except PermissionError as e:
            raise SnowflakeAuthError(
                f"Permission denied reading OAuth token file at: {token_path}"
            ) from e
        except OSError as e:
            raise SnowflakeAuthError(f"Failed to read OAuth token file at {token_path}: {e}") from e
        except Exception as e:
            raise SnowflakeAuthError(
                f"Unexpected error reading OAuth token from {token_path}: {e}"
            ) from e

    return await asyncio.to_thread(_read_token)


async def get_snowflake_connection_params(
    config: SnowflakeLinkedConfiguration,
) -> dict[str, Any]:
    """Get Snowflake connection parameters from linked configuration.

    Reads authentication details from ~/.sema4ai/sf-auth.json and returns
    the parameters needed to create an ibis Snowflake connection.

    Args:
        config: Linked Snowflake configuration with warehouse/database/schema

    Returns:
        Dictionary of connection parameters for ibis.snowflake.connect()

    Raises:
        SnowflakeAuthError: If auth file is missing or authentication fails
    """
    from pathlib import Path

    # Use platform-specific path separators
    auth_file_path = Path.home() / ".sema4ai" / "sf-auth.json"

    # Read and parse auth file asynchronously
    auth_data = await _read_auth_file(auth_file_path)

    # Extract linking details with forward compatibility
    # (ignore extra fields that may be added in future)
    linking_details = auth_data.get("linkingDetails")
    if not linking_details or not isinstance(linking_details, dict):
        raise SnowflakeAuthError(
            "Invalid Snowflake authentication file format: "
            "'linkingDetails' field is missing or invalid. "
            f"Please check the file at: {auth_file_path}"
        )

    authenticator = linking_details.get("authenticator")
    if not authenticator:
        raise SnowflakeAuthError(
            "No authenticator found in Snowflake authentication file. "
            f"Please check the file at: {auth_file_path}"
        )

    # Common connection parameters
    connection_params = {
        "warehouse": config.warehouse,
        "database": config.database,
        "schema": config.schema,
        "session_parameters": {
            "PYTHON_CONNECTOR_QUERY_RESULT_FORMAT": "JSON",
            "PYTHON_CONNECTOR_USE_NANOARROW": False,
        },
        "use_pandas": False,
    }

    # Add role if present (optional field)
    role = linking_details.get("role")
    if role:
        connection_params["role"] = role

    # Handle different authentication types
    if authenticator == "OAUTH":
        logger.info("Preparing Snowflake connection params with OAuth authenticator")
        # OAuth authentication
        account = linking_details.get("account")
        token_path = linking_details.get("tokenPath")

        if not account:
            raise SnowflakeAuthError(
                "Account not found in Snowflake authentication file for OAuth."
            )

        if not token_path:
            raise SnowflakeAuthError(
                "Token path not found in Snowflake authentication file for OAuth."
            )

        # Read the OAuth token asynchronously
        token = await _read_token_file(token_path)

        connection_params.update(
            {
                "account": account,
                "authenticator": "oauth",
                "token": token,
            }
        )

    elif authenticator == "SNOWFLAKE_JWT":
        logger.info("Preparing Snowflake connection params with JWT authenticator")
        # JWT (private key) authentication
        user = linking_details.get("user")
        account = linking_details.get("account")
        private_key_path = linking_details.get("privateKeyPath")
        private_key_passphrase = linking_details.get("privateKeyPassphrase")

        if not user or not account:
            raise SnowflakeAuthError(
                "User or account not found in Snowflake authentication file for JWT."
            )

        if not private_key_path:
            raise SnowflakeAuthError(
                "Private key path not found in Snowflake authentication file for JWT."
            )

        # Load the private key asynchronously
        private_key_bytes = await asyncio.to_thread(
            _load_private_key_from_file,
            private_key_path,
            private_key_passphrase,
        )

        connection_params.update(
            {
                "account": account,
                "user": user,
                "private_key": private_key_bytes,
            }
        )

    else:
        raise SnowflakeAuthError(
            f"Unsupported authenticator type: {authenticator}. "
            "Supported types are: OAUTH, SNOWFLAKE_JWT"
        )

    return connection_params
