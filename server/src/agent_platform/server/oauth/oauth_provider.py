from __future__ import annotations

import webbrowser
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, override
from urllib.parse import urlparse

import anyio
import httpx
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)
from pydantic import AnyHttpUrl
from structlog.stdlib import get_logger

from agent_platform.server.storage.base import BaseStorage

__all__ = ["OAuth"]

logger = get_logger(__name__)


class ClientNotFoundError(Exception):
    """Raised when OAuth client credentials are not found on the server."""


@dataclass
class OAuthCallbackResult:
    """Container for OAuth callback results, used with anyio.Event for async coordination."""

    code: str | None = None
    state: str | None = None
    error: Exception | None = None


async def check_if_auth_required(mcp_url: str, httpx_kwargs: dict[str, Any] | None = None) -> bool:
    """
    Check if the MCP endpoint requires authentication by making a test request.

    Returns:
        True if auth appears to be required, False otherwise
    """
    async with httpx.AsyncClient(**(httpx_kwargs or {})) as client:
        try:
            # Try a simple request to the endpoint
            response = await client.get(mcp_url, timeout=5.0)

            # If we get 401/403, auth is likely required
            if response.status_code in (401, 403):
                return True

            # Check for WWW-Authenticate header
            if "WWW-Authenticate" in response.headers:
                return True

            # If we get a successful response, auth may not be required
            return False

        except httpx.RequestError:
            # If we can't connect, assume auth might be required
            return True


class TokenStorageAdapter(TokenStorage):
    def __init__(self, storage: BaseStorage, user_id: str, mcp_url: str):
        self._storage = storage
        self._user_id = user_id
        self._mcp_url = mcp_url
        self._callback_id: str = ""

    async def clear(self) -> None:
        await self._storage.delete_mcp_oauth_token(user_id=self._user_id, mcp_url=self._mcp_url)
        await self._storage.delete_mcp_oauth_client_info(user_id=self._user_id, mcp_url=self._mcp_url)

    @override
    async def get_tokens(self) -> OAuthToken | None:
        return await self._storage.get_mcp_oauth_token(user_id=self._user_id, mcp_url=self._mcp_url, decrypt=True)

    @override
    async def set_tokens(self, tokens: OAuthToken) -> None:
        await self._storage.set_mcp_oauth_token(user_id=self._user_id, mcp_url=self._mcp_url, token=tokens)

    @override
    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return await self._storage.get_mcp_oauth_client_info(user_id=self._user_id, mcp_url=self._mcp_url, decrypt=True)

    @override
    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        await self._storage.set_mcp_oauth_client_info(
            user_id=self._user_id, mcp_url=self._mcp_url, client_info=client_info
        )

    async def get_callback_result(self) -> OAuthCallbackResult | None:
        return await self._storage.get_mcp_oauth_callback_result(callback_id=self._callback_id)

    def set_callback_id(self, callback_id: str) -> None:
        self._callback_id = callback_id


class OAuth(OAuthClientProvider):
    """
    OAuth client provider for MCP servers with browser-based authentication.

    This class provides OAuth authentication for FastMCP clients by opening
    a browser for user authorization and running a local callback server.
    """

    def __init__(
        self,
        mcp_url: str,
        token_storage_adapter: TokenStorageAdapter,
        base_redirect_uri: AnyHttpUrl,
        *,
        scopes: str | list[str] | None = None,
        additional_client_metadata: dict[str, Any] | None = None,
        web_mode: bool = False,
    ):
        """
        Initialize OAuth client provider for an MCP server.

        Args:
            mcp_url: Full URL to the MCP endpoint (e.g. "http://host/mcp/sse/")
            scopes: OAuth scopes to request. Can be a space-separated string or a list of strings.
            TokenStorageAdapter: The redirect URI to use for the OAuth flow (to be
                concatenated with the callback path)
            token_storage_adapter: A TokenStorageAdapter-compatible token store
            additional_client_metadata: Extra fields for OAuthClientMetadata
            web_mode: If True, redirect_handler stores the authorization URL
                instead of opening browser
        """
        import uuid

        client_name: str = "Sema4.ai MCP Client"
        parsed_url = urlparse(mcp_url)
        server_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Setup OAuth client
        self.httpx_client_factory = httpx.AsyncClient

        scopes_str: str
        if isinstance(scopes, list):
            scopes_str = " ".join(scopes)
        elif scopes is not None:
            scopes_str = str(scopes)
        else:
            scopes_str = ""

        self._callback_id = str(uuid.uuid4())
        redirect_uri = f"{base_redirect_uri}/{self._callback_id}"
        self.token_storage_adapter = token_storage_adapter
        self.token_storage_adapter.set_callback_id(callback_id=self._callback_id)

        client_metadata = OAuthClientMetadata(
            client_name=client_name,
            redirect_uris=[AnyHttpUrl(redirect_uri)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            # token_endpoint_auth_method="client_secret_post",
            scope=scopes_str,
            **(additional_client_metadata or {}),
        )

        # Store server_base_url for use in callback_handler
        self.server_base_url = server_base_url

        # Web mode: store authorization URL instead of opening browser
        self._web_mode = web_mode
        self._authorization_url: str | None = None
        self._authorization_url_event = anyio.Event()

        # Initialize parent class
        super().__init__(
            server_url=server_base_url,
            client_metadata=client_metadata,
            storage=self.token_storage_adapter,
            redirect_handler=self.redirect_handler,
            callback_handler=self.callback_handler,
        )

    async def _initialize(self) -> None:
        """Load stored tokens and client info, properly setting token expiry."""
        # Call parent's _initialize to load tokens and client info
        await super()._initialize()

        # If tokens were loaded and have expires_in, update the context's token_expiry_time
        if self.context.current_tokens and self.context.current_tokens.expires_in:
            self.context.update_token_expiry(self.context.current_tokens)

    async def redirect_handler(self, authorization_url: str) -> None:
        """Open browser for authorization, with pre-flight check for invalid client."""
        # Pre-flight check to detect invalid client_id before opening browser
        async with self.httpx_client_factory() as client:
            response = await client.get(authorization_url, follow_redirects=False)

            # Check for client not found error (400 typically means bad client_id)
            bad_client_id = 400
            if response.status_code == bad_client_id:
                raise ClientNotFoundError("OAuth client not found - cached credentials may be stale")

            # OAuth typically returns redirects, but some providers return 200 with HTML login pages
            if response.status_code not in (200, 302, 303, 307, 308):
                raise RuntimeError(f"Unexpected authorization response: {response.status_code}")

        logger.info(f"OAuth authorization URL: {authorization_url}")

        if self._web_mode:
            # Store the authorization URL for web browser flow
            self._authorization_url = authorization_url
            self._authorization_url_event.set()
        else:
            # Open browser for local flow
            webbrowser.open(authorization_url)

    async def get_authorization_url(self, timeout: float | None) -> str:
        """
        Get the authorization URL when in web mode.

        This method waits for the redirect_handler to be called and returns the authorization URL.

        Args:
            timeout: Maximum time to wait for the authorization URL in seconds

        Returns:
            The authorization URL

        Raises:
            TimeoutError: If the authorization URL is not available within the timeout
        """
        if not self._web_mode:
            raise RuntimeError("get_authorization_url can only be called in web_mode")

        try:
            with anyio.fail_after(timeout):
                await self._authorization_url_event.wait()
                if self._authorization_url is None:
                    raise RuntimeError("Authorization URL was not set")
                return self._authorization_url
        except TimeoutError as e:
            raise TimeoutError(f"Authorization URL not available within {timeout} seconds") from e

    async def callback_handler(self) -> tuple[str, str | None]:
        """Handle OAuth callback and return (auth_code, state)."""
        # Create result container and event to capture the OAuth response
        result = OAuthCallbackResult()

        # Run server until response is received with timeout logic
        logger.info("Waiting for OAuth callback (polling database for result)")

        timeout = 300.0  # 5 minute timeout
        try:
            with anyio.fail_after(timeout):
                while True:
                    result = await self.token_storage_adapter.get_callback_result()
                    if result is None:
                        await anyio.sleep(0.1)
                    else:
                        break

                if result.error:
                    raise result.error
                return result.code, result.state  # type: ignore
        except TimeoutError as e:
            raise TimeoutError(f"OAuth callback timed out after {timeout} seconds") from e

        raise RuntimeError("OAuth callback handler could not be started")

    async def async_auth_flow(self, request: httpx.Request) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """HTTPX auth flow with automatic retry on stale cached credentials.

        If the OAuth flow fails due to invalid/stale client credentials,
        clears the cache and retries once with fresh registration.
        """
        try:
            # First attempt with potentially cached credentials
            gen = super().async_auth_flow(request)
            response = None
            while True:
                try:
                    # First iteration sends None, subsequent iterations send response
                    yielded_request = await gen.asend(response)  # type: ignore
                    response = yield yielded_request
                except StopAsyncIteration:
                    break

        except ClientNotFoundError:
            logger.debug("OAuth client not found on server, clearing cache and retrying...")
            # Clear cached state and retry once
            self._initialized = False
            await self.token_storage_adapter.clear()

            # Retry with fresh registration
            gen = super().async_auth_flow(request)
            response = None
            while True:
                try:
                    yielded_request = await gen.asend(response)  # type: ignore
                    response = yield yielded_request
                except StopAsyncIteration:
                    break
