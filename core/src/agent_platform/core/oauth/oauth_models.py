import logging
import typing
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field
from pydantic.types import SecretStr

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode

if typing.TYPE_CHECKING:
    from mcp.shared.auth import OAuthToken

logger = logging.getLogger(__name__)


class AuthenticationType(str, Enum):
    """
    Type of authentication to use for the MCP server.
    """

    NONE = "none"  # No authentication is required
    OAUTH2_CLIENT_CREDENTIALS = "oauth2-client-credentials"  # OAuth2 client credentials authentication
    OAUTH2_AUTHORIZATION_CODE = "oauth2-authorization-code"  # OAuth2 authorization code flow authentication


class AuthenticationMetadataClientCredentials(BaseModel):
    """
    Metadata for OAuth2 client credentials authentication.
    """

    client_id: Annotated[
        SecretStr, Field(description="The client ID for the OAuth2 client credentials authentication.")
    ]
    client_secret: Annotated[
        SecretStr, Field(description="The client secret for the OAuth2 client credentials authentication.")
    ]
    scope: Annotated[
        str,
        Field(
            description="The (whitespace-separated) list of scopes for the OAuth2 client credentials authentication."
        ),
    ]
    endpoint: Annotated[str, Field(description="The endpoint to use for the OAuth2 client credentials authentication.")]

    def model_dump_cleartext(self) -> dict[str, Any]:
        """Dump the OAuth2 client credentials authentication metadata to a dictionary with all the information available
        in cleartext (careful: this should never be used to pass settings back in any API calls)."""
        return {
            "client_id": self.client_id.get_secret_value(),
            "client_secret": self.client_secret.get_secret_value(),
            "scope": self.scope,
            "endpoint": self.endpoint,
        }


class OAuth2Error(PlatformHTTPError):
    """Error raised when an OAuth2 operation cannot be completed."""

    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.BAD_REQUEST):
        super().__init__(error_code=error_code, message=message)


class OAuthConfig(BaseModel):
    authentication_type: Annotated[
        AuthenticationType,
        Field(description="The type of authentication to use. "),
    ] = AuthenticationType.NONE

    authentication_metadata: Annotated[
        AuthenticationMetadataClientCredentials | dict[str, Any] | None,
        Field(description="Metadata of the OAuth2 authentication to use."),
    ] = None

    def __post_init__(self):
        if self.authentication_metadata and isinstance(self.authentication_metadata, dict):
            try:
                self.authentication_metadata = AuthenticationMetadataClientCredentials.model_validate(
                    self.authentication_metadata
                )
            except Exception:
                # Keep as a dict, but log it as the configuration is actually invalid...
                if self.authentication_type == AuthenticationType.OAUTH2_CLIENT_CREDENTIALS:
                    logger.critical("Invalid authentication metadata for OAuth2 client credentials authentication.")

    def model_dump_cleartext(self) -> dict[str, Any]:
        """Dump the OAuth2 configuration to a dictionary with all the information available
        in cleartext (careful: this should never be used to pass settings back in any API calls)."""
        if isinstance(self.authentication_metadata, dict):
            authentication_metadata = self.authentication_metadata
        else:
            authentication_metadata = (
                self.authentication_metadata.model_dump_cleartext() if self.authentication_metadata else None
            )

        return {
            "authentication_type": self.authentication_type.value,
            "authentication_metadata": authentication_metadata,
        }


async def get_client_credentials_oauth_token(oauth_config: OAuthConfig, mcp_server_url: str | None) -> "OAuthToken":
    """Get an OAuth2 token for client credentials authentication.

    Fails with an OAuth2Error if the authentication metadata is invalid or the OAuth2 provider returns an error.

    Args:
        oauth_config: The OAuth2 configuration to use.
        mcp_server_url: The URL of the MCP server to authenticate with (optional, used for error messages).
    """
    import textwrap

    import httpx
    from mcp.shared.auth import OAuthToken
    from pydantic.type_adapter import TypeAdapter

    authentication_metadata = oauth_config.authentication_metadata
    if not authentication_metadata:
        raise OAuth2Error(
            textwrap.dedent(
                f"""Configuration error: No authentication metadata (unable to do client credentials oauth2 flow even
            though it's set for the MCP server at {mcp_server_url!r}).
            """,
            )
        )

    if isinstance(authentication_metadata, dict):
        try:
            authentication_metadata = TypeAdapter(AuthenticationMetadataClientCredentials).validate_python(
                authentication_metadata
            )
        except Exception as e:
            raise OAuth2Error(
                textwrap.dedent(
                    f"""Configuration error: Invalid authentication metadata
                (unable to do client credentials oauth2 flow even though it's set
                for the MCP server at {mcp_server_url!r}).
                Error: {e}.
                """,
                )
            ) from e

    if not isinstance(authentication_metadata, AuthenticationMetadataClientCredentials):
        raise OAuth2Error(
            textwrap.dedent(
                f"""
                Configuration error: Authentication metadata is not an instance of
                AuthenticationMetadataClientCredentials
                (unable to do client credentials oauth2 flow even though it's set
                for the MCP server at {mcp_server_url!r}).
                """
            )
        )

    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            authentication_metadata.endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": authentication_metadata.client_id.get_secret_value(),
                "client_secret": authentication_metadata.client_secret.get_secret_value(),
                "scope": authentication_metadata.scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code != 200:
            raise OAuth2Error(
                textwrap.dedent(f"""
                    Failed to get an OAuth2 token from the OAuth2 provider at
                    {authentication_metadata.endpoint!r}.
                    Status code: {response.status_code} (expected 200).
                    Response: {response.text!r}.
                    """)
            )
        try:
            found = response.json()
        except Exception as e:
            raise OAuth2Error(
                textwrap.dedent(f"""
                    Failed to parse the response as json from the OAuth2 provider at
                    {authentication_metadata.endpoint!r}: {response.text!r}.
                    """)
            ) from e

    if "access_token" not in found:
        raise OAuth2Error(
            textwrap.dedent(f"""
                No access_token in the response from the OAuth2 provider at
                {authentication_metadata.endpoint!r}.
                Found keys: {list(found.keys())}.
                """)
        )
    try:
        return OAuthToken.model_validate(found)
    except Exception as e:
        raise OAuth2Error(
            textwrap.dedent(f"""
                The OAuth token returned from the OAuth2 provider at:
                {authentication_metadata.endpoint!r}
                is not valid. Error: {e}
                """)
        ) from e
