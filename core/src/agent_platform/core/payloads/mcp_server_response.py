"""Response payloads for MCP server endpoints."""

from typing import Annotated, Literal

from pydantic import BaseModel, SecretStr
from pydantic.fields import Field

from agent_platform.core.agent_package.metadata.agent_metadata import (
    AgentPackageMetadata,
)
from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource, MCPServerWithOAuthConfig
from agent_platform.core.mcp.mcp_types import MCPVariables
from agent_platform.core.oauth.oauth_models import AuthenticationType

MCPServerType = Literal["generic_mcp", "sema4ai_action_server"]
MCPTransport = Literal["auto", "streamable-http", "sse", "stdio"]


class MCPServerCoreResponse(BaseModel):
    """Response model for MCP server endpoints that includes ID and source."""

    # MCP Server fields
    name: Annotated[str, Field(description="The name of the MCP server.")]

    transport: Annotated[
        MCPTransport, Field(description="Transport protocol to use when connecting to the MCP server.")
    ]

    url: Annotated[str | None, Field(default=None, description="The URL of the MCP server.")]

    headers: Annotated[
        MCPVariables | None,
        Field(default=None, description="Headers used for configuring requests & connections to the MCP server."),
    ]

    command: Annotated[str | None, Field(default=None, description="The command to run the MCP server.")]

    args: Annotated[
        list[str] | None, Field(default=None, description="The arguments to pass to the MCP server command.")
    ]

    env: Annotated[
        MCPVariables | None,
        Field(default=None, description="Environment variables to merge with agent-server's env vars."),
    ]

    cwd: Annotated[str | None, Field(default=None, description="Working directory to run the MCP server command in.")]

    type: Annotated[MCPServerType, Field(default="generic_mcp", description="The type of MCP server.")]

    force_serial_tool_calls: Annotated[
        bool, Field(default=False, description="If true, all tool calls are executed under a lock.")
    ]

    @classmethod
    def core_response_from_mcp_server(
        cls,
        mcp_server: MCPServer,
    ) -> "MCPServerCoreResponse":
        """Create MCPServerCoreResponse from MCP server data."""

        return cls(
            name=mcp_server.name,
            transport=mcp_server.transport,
            url=mcp_server.url,
            headers=mcp_server.headers,
            command=mcp_server.command,
            args=mcp_server.args,
            env=mcp_server.env,
            cwd=mcp_server.cwd,
            type=mcp_server.type,
            force_serial_tool_calls=mcp_server.force_serial_tool_calls,
        )


class MCPServerResponse(MCPServerCoreResponse):
    mcp_server_id: Annotated[str, Field(description="The unique identifier of the MCP server.")]

    source: Annotated[MCPServerSource, Field(description="The source of the MCP server (FILE or API).")]

    mcp_server_metadata: Annotated[
        AgentPackageMetadata | None,
        Field(
            default=None,
            description="""Metadata from agent package inspection for hosted MCP servers.
            Contains action packages, secrets, and other package information.""",
        ),
    ]

    @classmethod
    def from_mcp_server(
        cls,
        mcp_server_id: str,
        source: MCPServerSource,
        mcp_server: MCPServer,
    ) -> "MCPServerResponse":
        """Create MCPServerResponse from MCP server data."""
        metadata = None
        if mcp_server.mcp_server_metadata is not None:
            metadata = AgentPackageMetadata.model_validate(mcp_server.mcp_server_metadata)

        return cls(
            mcp_server_id=mcp_server_id,
            source=source,
            name=mcp_server.name,
            transport=mcp_server.transport,
            url=mcp_server.url,
            headers=mcp_server.headers,
            command=mcp_server.command,
            args=mcp_server.args,
            env=mcp_server.env,
            cwd=mcp_server.cwd,
            type=mcp_server.type,
            force_serial_tool_calls=mcp_server.force_serial_tool_calls,
            mcp_server_metadata=metadata,
        )


class AuthenticationMetadataClientCredentialsResponse(BaseModel):
    """
    Metadata for OAuth2 client credentials authentication.
    """

    client_id: Annotated[
        str, Field(description="The (redacted) client ID for the OAuth2 client credentials authentication.")
    ]
    client_secret: Annotated[
        str, Field(description="The (redacted) client secret for the OAuth2 client credentials authentication.")
    ]
    scope: Annotated[
        str,
        Field(
            description="The (whitespace-separated) list of scopes for the OAuth2 client credentials authentication."
        ),
    ]
    endpoint: Annotated[str, Field(description="The endpoint to use for the OAuth2 client credentials authentication.")]


class MCPServerWithOAuthConfigResponse(MCPServerResponse):
    authentication_type: Annotated[
        AuthenticationType,
        Field(description="The type of authentication to use. "),
    ] = AuthenticationType.NONE

    authentication_metadata: Annotated[
        AuthenticationMetadataClientCredentialsResponse | dict[str, str] | None,
        Field(description="Metadata of the OAuth2 authentication to use."),
    ] = None

    @classmethod
    def _get_secret_string_as_plaintext(cls, string: str | SecretStr) -> str:
        """Get the plaintext string value from a SecretStr or a string."""
        if isinstance(string, SecretStr):
            return string.get_secret_value()
        return string

    @classmethod
    def from_mcp_server_with_oauth_config(
        cls,
        mcp_server_id: str,
        source: MCPServerSource,
        mcp_server: MCPServerWithOAuthConfig,
    ) -> "MCPServerWithOAuthConfigResponse":
        """Create MCPServerWithOAuthConfigResponse from MCP server data."""
        from agent_platform.core.oauth.oauth_models import AuthenticationMetadataClientCredentials

        metadata = None
        if mcp_server.mcp_server_metadata is not None:
            metadata = AgentPackageMetadata.model_validate(mcp_server.mcp_server_metadata)

        authentication_type = AuthenticationType.NONE
        authentication_metadata = None

        if mcp_server.oauth_config is not None:
            authentication_type = mcp_server.oauth_config.authentication_type
            found_authentication_metadata = mcp_server.oauth_config.authentication_metadata
            if found_authentication_metadata is not None:
                if isinstance(found_authentication_metadata, AuthenticationMetadataClientCredentials):
                    authentication_metadata = AuthenticationMetadataClientCredentialsResponse(
                        client_id=cls._get_secret_string_as_plaintext(found_authentication_metadata.client_id),
                        client_secret=cls._get_secret_string_as_plaintext(found_authentication_metadata.client_secret),
                        scope=found_authentication_metadata.scope,
                        endpoint=found_authentication_metadata.endpoint,
                    )
                elif isinstance(found_authentication_metadata, dict):
                    # Not an expected format: return the plaintext values
                    authentication_metadata = {}
                    for key, value in found_authentication_metadata.items():
                        authentication_metadata[key] = cls._get_secret_string_as_plaintext(value)
                else:
                    authentication_metadata = None

        return cls(
            mcp_server_id=mcp_server_id,
            source=source,
            name=mcp_server.name,
            transport=mcp_server.transport,
            url=mcp_server.url,
            headers=mcp_server.headers,
            command=mcp_server.command,
            args=mcp_server.args,
            env=mcp_server.env,
            cwd=mcp_server.cwd,
            type=mcp_server.type,
            force_serial_tool_calls=mcp_server.force_serial_tool_calls,
            authentication_type=authentication_type,
            authentication_metadata=authentication_metadata,
            mcp_server_metadata=metadata,
        )
