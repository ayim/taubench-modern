from typing import Any, Literal

from pydantic import BaseModel
from pydantic.types import SecretStr

from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig
from agent_platform.core.mcp.mcp_types import MCPVariables
from agent_platform.core.oauth.oauth_models import AuthenticationType, OAuthConfig

Transport = Literal["auto", "streamable-http", "sse", "stdio"]
MCPServerType = Literal["generic_mcp", "sema4ai_action_server"]


class MCPServerCreateAuthenticationMetadataClientCredentials(BaseModel):
    client_id: SecretStr
    client_secret: SecretStr
    scope: str  # whitespace separated list of scopes (as the oauth2 spec says)
    endpoint: str


class MCPServerCreateOAuthConfig(BaseModel):
    authentication_type: AuthenticationType
    authentication_metadata: MCPServerCreateAuthenticationMetadataClientCredentials | dict[str, Any] | None = None

    def to_oauth_config(self) -> OAuthConfig:
        from agent_platform.core.oauth.oauth_models import AuthenticationMetadataClientCredentials

        authentication_metadata: AuthenticationMetadataClientCredentials | None | dict[str, Any] = None

        if isinstance(self.authentication_metadata, MCPServerCreateAuthenticationMetadataClientCredentials):
            authentication_metadata = AuthenticationMetadataClientCredentials(
                client_id=self.authentication_metadata.client_id,
                client_secret=self.authentication_metadata.client_secret,
                scope=self.authentication_metadata.scope.strip(),
                endpoint=self.authentication_metadata.endpoint,
            )
        elif isinstance(self.authentication_metadata, dict):
            authentication_metadata = self.authentication_metadata
        elif self.authentication_metadata is None:
            authentication_metadata = None
        else:
            raise ValueError(f"Invalid authentication metadata type: {type(self.authentication_metadata)}")

        return OAuthConfig(
            authentication_type=self.authentication_type,
            authentication_metadata=authentication_metadata,
        )


class MCPServerCreate(BaseModel):
    name: str
    transport: Transport = "auto"
    url: str | None = None
    headers: MCPVariables | None = None
    command: str | None = None
    args: list[str] | None = None
    env: MCPVariables | None = None
    cwd: str | None = None
    force_serial_tool_calls: bool = False
    type: MCPServerType = "generic_mcp"
    mcp_server_metadata: dict[str, Any] | None = None
    oauth_config: MCPServerCreateOAuthConfig | None = None

    def model_dump_cleartext(self) -> dict:
        """Dump the model to a dict, converting all SecretStr values to plain strings."""
        from typing import cast

        def convert_secret_str_to_str(obj: Any) -> Any:
            """Recursively convert SecretStr instances to str."""
            if isinstance(obj, SecretStr):
                return obj.get_secret_value()
            elif isinstance(obj, dict):
                return {key: convert_secret_str_to_str(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_secret_str_to_str(item) for item in obj]
            elif isinstance(obj, BaseModel):
                # Handle nested Pydantic models
                return convert_secret_str_to_str(obj.model_dump())
            else:
                return obj

        dumped = self.model_dump()
        return cast(dict, convert_secret_str_to_str(dumped))

    def to_mcp_server(self) -> MCPServerWithOAuthConfig:
        return MCPServerWithOAuthConfig(
            name=self.name,
            transport=self.transport,
            url=self.url,
            headers=self.headers,
            command=self.command,
            args=self.args,
            env=self.env,
            cwd=self.cwd,
            force_serial_tool_calls=self.force_serial_tool_calls,
            type=self.type,
            mcp_server_metadata=self.mcp_server_metadata,
            oauth_config=self.oauth_config.to_oauth_config() if self.oauth_config else None,
        )


class MCPServerUpdateAuthMetadataClientCredentials(BaseModel):
    # All fields are required (the credentials must be passed as a whole object)
    client_id: SecretStr
    client_secret: SecretStr
    scope: str  # whitespace separated list of scopes (as the oauth2 spec says)
    endpoint: str


class MCPServerUpdateAuthConfig(BaseModel):
    authentication_type: AuthenticationType | None = None
    authentication_metadata: MCPServerUpdateAuthMetadataClientCredentials | None = None


class MCPServerUpdate(BaseModel):
    # Same fields as MCPServerCreate, but all fields are optional (but when given, they'll be set, even if null).
    name: str | None = None
    transport: Transport | None = None
    url: str | None = None
    headers: MCPVariables | None = None
    command: str | None = None
    args: list[str] | None = None
    env: MCPVariables | None = None
    cwd: str | None = None
    force_serial_tool_calls: bool | None = None
    type: MCPServerType | None = None
    mcp_server_metadata: dict[str, Any] | None = None
    oauth_config: MCPServerUpdateAuthConfig | None = None
