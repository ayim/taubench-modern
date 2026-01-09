import typing
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from structlog.stdlib import get_logger

from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.core.mcp.mcp_client import MCPClient
from agent_platform.core.mcp.mcp_types import MCPVariables, deserialize_mcp_variables, serialize_mcp_variables
from agent_platform.core.oauth.oauth_models import OAuthConfig
from agent_platform.core.tools.tool_definition import ToolDefinition

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)


class MCPServerSource(str, Enum):
    FILE = "FILE"
    API = "API"


@dataclass(frozen=True)
class MCPServerWithMetadata:
    """MCP server with its source and deployment information."""

    server: "MCPServerWithOAuthConfig"
    """The MCP server configuration with OAuth information."""

    source: MCPServerSource
    """The source of the MCP server (FILE or API)."""

    deployment_id: str | None = None
    """The MCP runtime deployment ID, if hosted."""


Transport = Literal["auto", "streamable-http", "sse", "stdio"]


@dataclass(frozen=True)
class MCPServer:
    """Model Context Protocol (MCP) server definition."""

    name: str = field(metadata={"description": "The name of the MCP server."})
    """The name of the MCP server."""

    transport: Transport = field(
        default="auto",
        metadata={
            "description": "Transport protocol to use when connecting to the MCP server. "
            "Auto defaults to streamable-http unless sse is in the url; if there is no url, "
            "defaults to stdio."
        },
    )
    """Transport protocol to use when connecting to the MCP server.
    Auto defaults to streamable-http unless sse is in the url; if there is no url,
    defaults to stdio."""

    # Remote transports
    url: str | None = field(
        default=None,
        metadata={
            "description": "The URL of the MCP server. This should point directly to the transport endpoint to use."
        },
    )
    """The URL of the MCP server."""

    headers: MCPVariables | None = field(
        default=None,
        metadata={"description": "Headers used for configuring requests & connections to the MCP server."},
    )
    """Headers used for configuring requests & connections to the MCP server."""

    # Stdio transports
    command: str | None = field(
        default=None,
        metadata={
            "description": "The command to run the MCP server. "
            "If not provided, the MCP server will be assumed to be running "
            "on the local machine."
        },
    )
    """The command to run the MCP server. If not provided, the MCP server will
    be assumed to be running on the local machine."""

    args: list[str] | None = field(
        default=None, metadata={"description": "The arguments to pass to the MCP server command."}
    )
    """The arguments to pass to the MCP server command."""

    env: MCPVariables | None = field(
        default=None,
        metadata={
            "description": "Environment variables to merge with agent-server's env vars for the MCP server command."
        },
    )
    """Environment variables to merge with agent-server's env vars for the MCP server command."""

    cwd: str | None = field(
        default=None,
        metadata={
            "description": "The working directory to run the MCP server command in.",
        },
    )
    """The working directory to run the MCP server command in."""

    force_serial_tool_calls: bool = field(
        default=False,
        metadata={
            "description": "If True, all tool calls are executed under a lock "
            "to support servers that cannot interleave multiple requests."
        },
    )
    """If True, all tool calls are executed under a lock to support servers
    that cannot interleave multiple requests."""

    type: Literal["generic_mcp", "sema4ai_action_server"] = field(
        default="generic_mcp",
        metadata={
            "description": "The type of MCP server. If 'sema4ai_action_server', "
            "X-Action-Context headers will be added for secret handling."
        },
    )
    """The type of MCP server. If 'sema4ai_action_server', X-Action-Context
    headers will be added for secret handling."""

    mcp_server_metadata: dict[str, Any] | None = field(
        default=None,
        metadata={
            "description": "Metadata of this MCP server. For `sema4ai_action_server` MCP types, "
            "we store the metadata of the action-server "
            "(action packages, secrets, whitelist, icons...)"
        },
    )
    """Metadata from agent package inspection for MCP server of type `sema4ai_action_server`.
    Structure matches AgentPackageMetadata.model_dump() output."""

    def _validate_url_command(self) -> None:
        """Validate url and command configuration."""
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        if not self.url and not self.command:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message="Either url or command must be provided",
            )
        if self.url and self.command:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message="Provide *either* url=* or command=*, but not both",
            )

    def _resolve_transport(self) -> Transport:
        """Resolve transport type based on url/command."""
        if self.transport != "auto":
            return self.transport
        if self.url and "/sse" in self.url.lower():
            return "sse"
        if self.url:
            return "streamable-http"
        if self.command:
            return "stdio"
        return self.transport

    def _validate_transport(self) -> None:
        """Validate transport matches url/command."""
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        if self.url and self.transport not in ["sse", "streamable-http"]:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message="'url' transport requires transport=sse or transport=streamable-http",
            )
        if self.command and self.transport != "stdio":
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message="'command' transport requires transport=stdio",
            )

    def __post_init__(self):
        # Skip url/command validation for sema4ai_action_server type
        if self.type == "sema4ai_action_server" and not self.url and not self.command:
            if self.transport == "auto":
                object.__setattr__(self, "transport", "streamable-http")
            return

        self._validate_url_command()
        resolved_transport = self._resolve_transport()
        if resolved_transport != self.transport:
            object.__setattr__(self, "transport", resolved_transport)
        self._validate_transport()

    @property
    def is_stdio(self) -> bool:
        """Return True if this server uses the stdio transport.

        Historically the decision was based on the internal *kind* attribute,
        but since the transport value is now fully validated during
        ``__post_init__`` we can simply look at the effective ``transport``.
        """
        return self.transport == "stdio"

    @property
    def cache_key(self) -> str:
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        if self.url:
            headers_part = tuple(sorted((self.headers or {}).items()))
            return f"{self.url}|{headers_part}"
        if self.command:
            env_part = tuple(sorted((self.env or {}).items()))
            cwd_part = self.cwd or ""
            args_part = " ".join(self.args or [])
            return f"{self.command}|{args_part}|{cwd_part}|{env_part}"

        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="No cache key for MCP server",
        )

    def copy(self) -> "MCPServer":
        """Returns a deep copy of the MCP server."""
        return MCPServer(
            name=self.name,
            url=self.url,
            headers=self.headers,
            command=self.command,
            args=self.args,
            env=self.env,
            cwd=self.cwd,
            force_serial_tool_calls=self.force_serial_tool_calls,
            transport=self.transport,
            type=self.type,
            mcp_server_metadata=self.mcp_server_metadata,
        )

    def model_dump(self) -> dict:
        """Serializes the MCP server to a dictionary.
        Useful for JSON serialization."""
        return {
            "name": self.name,
            "transport": self.transport,
            # based on transport - url + headers
            "url": self.url or None,
            "headers": serialize_mcp_variables(self.headers) or None,
            # based on transport - command + args + env + cwd
            "command": self.command or None,
            "args": self.args or None,
            "env": serialize_mcp_variables(self.env) or None,
            "cwd": self.cwd or None,
            # generic
            "force_serial_tool_calls": self.force_serial_tool_calls,
            "type": self.type,
            # hosted MCP metadata
            "mcp_server_metadata": self.mcp_server_metadata,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "MCPServer":
        """Deserializes the MCP server from a dictionary.
        Useful for JSON deserialization."""
        data = data.copy()
        if "headers" in data:
            data["headers"] = deserialize_mcp_variables(data["headers"])
        if "env" in data:
            data["env"] = deserialize_mcp_variables(data["env"])

        return cls(**data)


@dataclass(frozen=True)
class MCPServerWithOAuthConfig(MCPServer):
    """MCP server + OAuth configuration."""

    oauth_config: OAuthConfig | None = field(
        default=None,
        metadata={"description": "OAuth configuration for the MCP server."},
    )

    async def to_tool_definitions(
        self,
        # Additional headers to be added to the request at
        # tool definition time
        user_id: str,
        storage: "BaseStorage",
        *,
        additional_headers: dict | None = None,
        data_server_details: DataServerDetails | None = None,
        mcp_sema4ai_action_invocation_context: dict[str, str] | None = None,
        use_caches: bool = True,
    ) -> list[ToolDefinition]:
        """Converts the MCP server to a list of tool definitions.

        Note: the oauth_config is taken from the class instance.
        """
        from agent_platform.core.oauth.oauth_models import (
            AuthenticationMetadataClientCredentials,
            AuthenticationType,
            get_client_credentials_oauth_token,
        )

        if not additional_headers:
            additional_headers = {}

        url = self.url
        token = None
        if url is not None:
            if use_caches:
                token = await storage.get_mcp_oauth_token(user_id, url, decrypt=True)
                if token is not None and token.access_token:
                    additional_headers["Authorization"] = f"Bearer {token.access_token}"

            if "Authorization" not in additional_headers:
                # No token, maybe it must still be added?
                if (
                    self.oauth_config
                    and self.oauth_config.authentication_type == AuthenticationType.OAUTH2_CLIENT_CREDENTIALS
                ):
                    # Do client credentials authentication (could fail if the authentication metadata is invalid)
                    token = await get_client_credentials_oauth_token(self.oauth_config, self.url)
                    additional_headers["Authorization"] = f"Bearer {token.access_token}"

                    authentication_metadata = self.oauth_config.authentication_metadata
                    assert isinstance(authentication_metadata, AuthenticationMetadataClientCredentials), (
                        "Authentication metadata must be an instance of AuthenticationMetadataClientCredentials"
                    )

                    await storage.set_mcp_oauth_token(user_id, url, token)

        async with MCPClient(
            self,
            additional_headers=additional_headers,
            data_server_details=data_server_details,
            mcp_sema4ai_action_invocation_context=mcp_sema4ai_action_invocation_context,
        ) as client:
            tools = await client.list_tools()
        return tools

    def model_dump(self) -> dict:
        """Serializes the MCP server to a dictionary.

        Raises an error to prevent exposing OAuth configuration in API responses.
        """
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="MCPServerWithOAuthConfig.model_dump() is not allowed. "
            "Use MCPServer.model_dump() instead to avoid exposing OAuth configuration.",
        )

    @property
    def cache_key(self) -> str:
        """Cache key that includes OAuth information when URL is available."""
        if self.url:
            headers_part = tuple(sorted((self.headers or {}).items()))
            # Include oauth config in cache key when available
            oauth_part = None
            if self.oauth_config:
                # Include authentication type and a hash of metadata for cache key
                import hashlib
                import json

                auth_type = self.oauth_config.authentication_type.value
                if self.oauth_config.authentication_metadata:
                    # Create a stable hash of the metadata
                    metadata_dict = self.oauth_config.model_dump_cleartext()["authentication_metadata"]
                    if isinstance(metadata_dict, dict):
                        # Sort keys for consistent hashing
                        metadata_str = json.dumps(metadata_dict, sort_keys=True)
                        metadata_hash = hashlib.sha256(metadata_str.encode()).hexdigest()[:16]
                        oauth_part = f"{auth_type}:{metadata_hash}"
                    else:
                        oauth_part = auth_type
                else:
                    oauth_part = auth_type

            if oauth_part:
                return f"{self.url}|{headers_part}|oauth:{oauth_part}"
            return f"{self.url}|{headers_part}"
        if self.command:
            env_part = tuple(sorted((self.env or {}).items()))
            cwd_part = self.cwd or ""
            args_part = " ".join(self.args or [])
            return f"{self.command}|{args_part}|{cwd_part}|{env_part}"
        raise ValueError("No cache key for MCP server")

    @classmethod
    def model_validate(cls, data: dict) -> "MCPServerWithOAuthConfig":
        """Deserializes the MCP server with OAuth config from a dictionary.
        Useful for JSON deserialization."""
        data = data.copy()

        # Extract oauth_config if present
        oauth_config = None
        if "oauth_config" in data:
            oauth_config_data = data.pop("oauth_config")
            if oauth_config_data is not None:
                oauth_config = OAuthConfig.model_validate(oauth_config_data)

        # Handle MCPServer fields
        if "headers" in data:
            data["headers"] = deserialize_mcp_variables(data["headers"])
        if "env" in data:
            data["env"] = deserialize_mcp_variables(data["env"])

        return cls(**data, oauth_config=oauth_config)
