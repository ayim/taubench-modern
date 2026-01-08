"""ToolDefinition: represents the definition of a tool."""

import typing
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Literal

from structlog import get_logger

if typing.TYPE_CHECKING:
    from agent_platform.core.data_server.data_server import DataServerDetails
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.mcp.mcp_server import MCPServer
    from agent_platform.core.oauth.oauth_models import OAuthConfig
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)

ToolCategory = Literal[
    "unknown",
    "internal-tool",
    "action-tool",
    "mcp-tool",
    "client-exec-tool",
    "client-info-tool",
]


@dataclass(frozen=True)
class ToolCallContext:
    """
    Note: usage is expected to be:

    tool_call_context = ToolCallContext.from_kernel(kernel)

    # call the `with_<method_name>` methods as needed.

    tool_call_context = tool_call_context.with_mcp_server_info(mcp_server)
    tool_call_context = await tool_call_context.with_oauth_token(url, storage, oauth_config, use_caches=True)
    tool_call_context = tool_call_context.with_tool_call_id(tool_call_id)

    # Then build for the action server the body and headers.
    body, top_level_headers = tool_call_context.build_body_and_headers_for_action_server(args, additional_headers)

    # Or build for the MCP server the headers.
    headers = tool_call_context.build_headers_for_mcp_server()
    """

    # All below set with the `from_kernel` method (preferred method to create the ToolCallContext)
    user_id: str = field(metadata={"description": "The ID of the user that invoked the tool"})
    agent_id: str | None = field(metadata={"description": "The ID of the agent that invoked the tool"})
    tenant_id: str | None = field(metadata={"description": "The ID of the tenant that invoked the tool"})
    thread_id: str | None = field(metadata={"description": "The ID of the thread that invoked the tool"})

    # Set with the `from_kernel` method (preferred method to create the ToolCallContext)
    data_server_details: "DataServerDetails | None" = field(
        metadata={"description": "The data server details for the tool call"}, default=None
    )

    # Set with the `with_tool_call_id` method.
    tool_call_id: str | None = field(
        metadata={"description": "The ID of the tool call that invoked the tool"}, default=None
    )

    # Set with the `with_oauth_token` method.
    authorization_token: str | None = field(
        metadata={"description": "The authorization token for the tool call"}, default=None
    )

    # Set with the `with_mcp_server_info` method.
    regular_headers: dict[str, str] = field(
        metadata={"description": "The headers for the tool call"}, default_factory=dict
    )
    # Set with the `with_mcp_server_info` method.
    secrets: dict[str, str] = field(
        metadata={"description": "The secrets (only for Sema4AI Action Servers) for the tool call"},
        default_factory=dict,
    )
    # Set with the `with_mcp_server_info` method.
    mcp_server_kind: Literal["unset", "generic_mcp", "sema4ai_action_server"] = field(
        metadata={"description": "The kind of MCP server for the tool call"}, default="unset"
    )

    def _copy_with(self, **kwargs: Any) -> "ToolCallContext":
        return self.__class__(
            agent_id=kwargs.get("agent_id", self.agent_id),
            user_id=kwargs.get("user_id", self.user_id),
            tenant_id=kwargs.get("tenant_id", self.tenant_id),
            thread_id=kwargs.get("thread_id", self.thread_id),
            tool_call_id=kwargs.get("tool_call_id", self.tool_call_id),
            authorization_token=kwargs.get("authorization_token", self.authorization_token),
            data_server_details=kwargs.get("data_server_details", self.data_server_details),
            regular_headers=kwargs.get("regular_headers", self.regular_headers),
            secrets=kwargs.get("secrets", self.secrets),
            mcp_server_kind=kwargs.get("mcp_server_kind", self.mcp_server_kind),
        )

    @classmethod
    async def from_kernel(cls, kernel: "Kernel") -> "ToolCallContext":
        from agent_platform.core.data_server.data_server import DataServerDetails
        from agent_platform.server.storage.errors import IntegrationNotFoundError

        # Get data server details for MCP context
        data_server_details = None
        try:
            # Use new integration table instead of old dids_connection_details table
            data_server_integration = await kernel.storage.get_integration_by_kind("data_server")
        except (IntegrationNotFoundError, ValueError) as e:
            # Log but continue without data context - this allows MCP servers to work
            # even when data server details are unavailable
            logger.info(f"Could not retrieve data server details for MCP context: {e}")
        else:
            try:
                settings_dict = data_server_integration.settings.model_dump()
                data_server_details = DataServerDetails.model_validate(settings_dict)
            except Exception as e:
                # Don't raise error here (proceed without data server information).
                logger.exception(f"Error validating data server details: {e}")

        return cls(
            agent_id=kernel.agent.agent_id,
            user_id=kernel.user.user_id or kernel.user.cr_system_id or kernel.user.sub,
            tenant_id=kernel.user.cr_tenant_id,
            thread_id=kernel.thread.thread_id,
            data_server_details=data_server_details,
        )

    def _build_data_context_header(self) -> dict[str, str]:
        """
        Creates the encrypted x-data-context header value based on data server credentials.
        """
        from agent_platform.core.data_server.data_server import DataServerEndpointKind

        if not self.data_server_details:
            return {}

        if (
            not self.data_server_details.username
            or not self.data_server_details.password_str
            or not self.data_server_details.data_server_endpoints
        ):
            return {}

        data_context = {"data-server": {}}

        for endpoint in self.data_server_details.data_server_endpoints:
            if endpoint.kind == DataServerEndpointKind.HTTP:
                data_context["data-server"]["http"] = {
                    "url": f"http://{endpoint.full_address}",
                    "user": self.data_server_details.username,
                    "password": self.data_server_details.password_str,
                }
            elif endpoint.kind == DataServerEndpointKind.MYSQL:
                data_context["data-server"]["mysql"] = {
                    "host": endpoint.host,
                    "port": endpoint.port,
                    "user": self.data_server_details.username,
                    "password": self.data_server_details.password_str,
                }

        if data_context["data-server"]:
            return {"X-Data-Context": self._build_data_envelope(data_context)}
        return {}

    def _build_action_context_header(self) -> dict[str, str]:
        """
        Add X-Action-Context header with the secrets if not already present.
        Ref: https://github.com/Sema4AI/actions/blob/master/action_server/docs/guides/07-secrets.md#passing-secrets-as-environment-variables-or-headers
        """
        if self.regular_headers:
            # Check if X-Action-Context header already exists (case-insensitive)
            for header_name in self.regular_headers:
                if header_name.lower() == "x-action-context":
                    # Header already exists, don't create a new one
                    return {}

        # If we have secrets, create the X-Action-Context header
        if self.secrets:
            action_context = {"secrets": self.secrets}

            return {"X-Action-Context": self._build_data_envelope(action_context)}
        return {}

    def with_mcp_server_info(self, mcp_server: "MCPServer") -> "ToolCallContext":
        from agent_platform.core.mcp.mcp_types import MCPVariableTypeOAuth2Secret, MCPVariableTypeSecret

        if self.mcp_server_kind != "unset":
            raise RuntimeError("mcp_server_kind is already set. `with_mcp_server_info` can only be called once.")

        if not mcp_server.headers:
            return self

        if mcp_server.type == "sema4ai_action_server":
            # Separate secrets from regular headers
            secrets: dict[str, str] = {}
            regular_headers = {}
            for header_name, header_value in mcp_server.headers.items():
                if isinstance(header_value, MCPVariableTypeSecret | MCPVariableTypeOAuth2Secret):
                    secrets[header_name] = header_value.value or ""

                elif isinstance(header_value, str):
                    regular_headers[header_name] = header_value

                else:
                    regular_headers[header_name] = header_value.value or ""

            return self._copy_with(
                regular_headers=regular_headers, secrets=secrets, mcp_server_kind="sema4ai_action_server"
            )

        else:
            # Generic MCP Servers get all headers, including secrets
            regular_headers: dict[str, str] = {
                key: value if isinstance(value, str) else (value.value or "")
                for key, value in mcp_server.headers.items()
            }
            return self._copy_with(regular_headers=regular_headers, mcp_server_kind="generic_mcp")

    async def with_oauth_token(
        self, url: str, storage: "BaseStorage", oauth_config: "OAuthConfig", use_caches: bool = True
    ) -> "ToolCallContext":
        from agent_platform.core.oauth.oauth_models import (
            AuthenticationMetadataClientCredentials,
            AuthenticationType,
            get_client_credentials_oauth_token,
        )

        if use_caches:
            token = await storage.get_mcp_oauth_token(self.user_id, url, decrypt=True)
            if token is not None and token.access_token:
                return self._copy_with(authorization_token=f"Bearer {token.access_token}")

        if self.authorization_token is None:
            # No token, maybe it must still be added?
            if oauth_config and oauth_config.authentication_type == AuthenticationType.OAUTH2_CLIENT_CREDENTIALS:
                # Do client credentials authentication (could fail if the authentication metadata is invalid)
                token = await get_client_credentials_oauth_token(oauth_config, url)
                ret = self._copy_with(authorization_token=f"Bearer {token.access_token}")

                authentication_metadata = oauth_config.authentication_metadata
                assert isinstance(authentication_metadata, AuthenticationMetadataClientCredentials), (
                    "Authentication metadata must be an instance of AuthenticationMetadataClientCredentials"
                )

                await storage.set_mcp_oauth_token(self.user_id, url, token)
                return ret

        return self

    def _build_data_envelope(self, data: dict[str, Any]) -> str:
        import base64
        import json

        # Ideally we'd encrypt the data here and then based on what the action server
        # is configured to accept (i.e.: based on the ACTION_SERVER_DECRYPT_KEYS passed
        # to the Action Server). Right now this isn't supported in the deployment process.
        # https://linear.app/sema4ai/issue/CLOUD-5633/enable-the-action-server-encryption
        # is tracking this.
        return base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")

    def _build_action_invocation_context_header(self) -> dict[str, str]:
        import uuid

        context = {}
        if self.agent_id:
            context["agent_id"] = self.agent_id
        if self.user_id:
            context["invoked_on_behalf_of_user_id"] = self.user_id
        if self.thread_id:
            context["thread_id"] = self.thread_id
        # Note: the tenant id should not be passed on to the Action Server anymore.
        # if self.tenant_id:
        #     context["tenant_id"] = self.tenant_id
        context["action_invocation_id"] = self.tool_call_id or str(uuid.uuid4())

        return {"x-action-invocation-context": self._build_data_envelope(context)}

    def with_tool_call_id(self, tool_call_id: str) -> "ToolCallContext":
        return self._copy_with(tool_call_id=tool_call_id)

    def build_body_and_headers_for_action_server(
        self, args: dict[str, Any], additional_headers: dict[str, str]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """
        Builds the body and headers for the action server (public API).

        Note: in the Action Server we can actually pass headers in the body
        to overcome size limitations of headers, so, we return the headers
        that must be top-level separately and put other headers into the body.

        Args:
            args: The arguments to the tool call.
            additional_headers: Additional headers to add to the request.

        Returns:
            A tuple containing the body and headers for the action server.
        """
        # When x-action-invocation-context is top-level the others may be passed in the body.
        top_level_headers = self._build_action_invocation_context_header()

        headers = {}
        headers.update(additional_headers)  # Additional headers computed by the caller are added here
        headers.update(self._build_action_context_header())  # Secrets are added here (in x-action-context header)
        headers.update(self._build_data_context_header())  # Data context is added here (in x-data-context header)
        headers.update(self.regular_headers)  # Regular headers the user specified are added here
        if self.authorization_token:
            headers["Authorization"] = self.authorization_token  # Authorization token is added here

        return {**headers, "body": args}, top_level_headers

    def build_headers_for_mcp_server(self) -> dict[str, str]:
        """
        Builds the headers for the MCP server (public API).

        Returns:
            A dictionary containing the headers for the MCP server.
        """
        headers = {}
        if self.mcp_server_kind == "sema4ai_action_server":
            # These are just expected for Sema4.ai Action Servers.
            headers.update(self._build_action_invocation_context_header())
            headers.update(self._build_action_context_header())
            headers.update(self._build_data_context_header())

        headers.update(self.regular_headers)
        if self.authorization_token:
            headers["Authorization"] = self.authorization_token
        return headers


@dataclass(frozen=True)
class ToolDefinition:
    """Represents the definition of a tool."""

    name: str = field(metadata={"description": "The name of the tool"})
    """The name of the tool"""

    description: str = field(metadata={"description": "The description of the tool"})
    """The description of the tool"""

    input_schema: dict[str, Any] = field(
        metadata={"description": "The schema of the tool input"},
    )
    """The schema of the tool input"""

    category: ToolCategory = field(
        metadata={"description": "The category of the tool"},
        default="unknown",
    )
    """The category of the tool"""

    function: Callable[..., Any] = field(
        default=lambda *a, **k: None,
        metadata={"description": "The function that implements the tool"},
    )
    """The function that implements the tool"""

    def model_dump(self) -> dict:
        """Dump the ToolDefinition as a dictionary."""
        # Leave out the function/tool_call_context_at_definition_time as it's not serializable
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "category": self.category,
        }

    @classmethod
    def from_callable(
        cls,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *,
        name: str | None = None,
        description: str | None = None,
        strict: bool = True,
        category: ToolCategory = "internal-tool",
    ) -> "ToolDefinition":
        """Creates a ToolDefinition from an async Python function.

        This method inspects the provided async function and generates a
        ToolDefinition with appropriate name, description, and input schema
        based on the function's signature and metadata.

        Arguments:
            func: An async callable that implements the tool functionality.
            name: Optional name override. If None, uses function's __name__.
            description: Optional description override. If None, uses func's docstring.
            strict: Whether to set 'strict' in the schema for OpenAI function calling.

        Returns:
            ToolDefinition: A fully populated ToolDefinition instance.

        Raises:
            ValueError: If the function is not async, uses *args/**kwargs, or
                has missing required metadata.
        """
        from inspect import getdoc, iscoroutinefunction, signature

        from agent_platform.core.tools.tool_utils import build_param_schema

        # 1. Ensure the function is async
        if not iscoroutinefunction(func):
            raise ValueError(f"Function '{func.__name__}' must be async.")

        # 2. Determine name and description
        tool_name = name or func.__name__
        doc = description or (getdoc(func) or "").strip() or f"{tool_name} function."

        # 3. Build the JSON schema for parameters
        signature = signature(func)

        properties: dict[str, Any] = {}
        required_fields: list[str] = []

        # param.annotation may be a string if `from __future__ import annotations` is used
        # So, get the type hints from the function
        type_hints = typing.get_type_hints(func, include_extras=True)

        for param_name, param in signature.parameters.items():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                # Raise on *args/**kwargs for schema generation
                raise ValueError(f"Unsupported parameter kind: {param.kind}")

            # Required if no default given
            is_required = param.default is param.empty

            # Build the param schema
            # We'll rely on `build_param_schema` to introspect type hints & metadata
            param_schema = build_param_schema(
                param_name,
                type_hints[param_name] if param.annotation is not param.empty else Any,
                allow_omitted_description=False,
            )
            properties[param_name] = param_schema
            # NOTE: in strict mode, all params must be required
            if is_required or strict:
                required_fields.append(param_name)

        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required_fields,
        }

        if strict:
            # Some folks embed "strict": True, others do not.
            # This is an optional field you might add for usage with certain LLM APIs.
            input_schema["strict"] = True
            # Strict also means no additional properties
            input_schema["additionalProperties"] = False

        return cls(
            name=tool_name,
            description=doc,
            input_schema=input_schema,
            function=func,
            category=category,
        )

    @classmethod
    def model_validate(cls, data: dict) -> "ToolDefinition":
        """Validate and convert a dictionary into a ToolDefinition instance."""
        return cls(
            name=data["name"],
            description=data["description"],
            input_schema=data["input_schema"],
            function=data.get("function", lambda *a, **k: None),
            category=data.get("category", "unknown"),
        )
