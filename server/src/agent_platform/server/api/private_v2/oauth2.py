from __future__ import annotations

import os
from http import HTTPStatus

import httpx
from agent_platform.orchestrator.bootstrap_base import is_debugger_active
from fastapi import APIRouter, Query, Request
from pydantic import AnyHttpUrl, BaseModel
from starlette.responses import HTMLResponse, RedirectResponse, Response
from structlog import get_logger

from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)

OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID = 5 * 60.0  # 5 minute

# Override with environment variable if set, otherwise use default
if os.getenv("SEMA4AI_OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID"):
    try:
        OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID = float(
            os.environ["SEMA4AI_OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID"]
        )
    except Exception as e:
        logger.error(
            f"Failed to parse SEMA4AI_OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID as a float: {e}"
        )

if is_debugger_active():  # No interaction timeouts when debugging.
    OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT = None

else:
    OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT = 3 * 60.0  # 3 minutes

    # Override with environment variable if set, otherwise use default
    if os.getenv("SEMA4AI_OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT"):
        try:
            OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT = float(
                os.environ["SEMA4AI_OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT"]
            )
        except Exception as e:
            logger.error(
                f"Failed to parse SEMA4AI_OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT "
                f"as a float: {e}"
            )


class OAuth2LoginRequest(BaseModel):
    """Request to start OAuth2 login flow."""

    mcp_server_url: str


class OAuth2LoginResponse(BaseModel):
    """Response from OAuth2 login endpoint."""

    message: str


class OAuth2StatusResponse(BaseModel):
    """Response from OAuth2 status endpoint."""

    authenticated: bool
    has_refresh_token: bool
    token_expires_in: int | None = None


@router.get("/login")
async def oauth2_login(
    mcp_server_url: str,
    user: AuthedUser,
    storage: StorageDependency,
    request: Request,
) -> Response:
    """
    Start OAuth2 login flow for an MCP server from a web browser.

    Returns a redirect to the authorization URL. The OAuth flow continues
    in the background and waits for the callback.

    A client can poll for the status of the OAuth2 flow by calling the /oauth2/status API.
    """
    import time

    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.server.oauth.oauth_provider import OAuth, TokenStorageAdapter
    from agent_platform.server.shutdown_manager import ShutdownManager

    # Create token storage adapter
    token_storage_adapter = TokenStorageAdapter(
        storage=storage, user_id=user.user_id, mcp_url=mcp_server_url
    )

    # Get base redirect URI from request
    base_url_str = str(request.base_url).rstrip("/")
    base_redirect_uri = AnyHttpUrl(f"{base_url_str}/api/v2/oauth2/callback")

    # Create OAuth instance with web_mode=True for web browser flow
    oauth = OAuth(
        mcp_url=mcp_server_url,
        token_storage_adapter=token_storage_adapter,
        base_redirect_uri=base_redirect_uri,
        web_mode=True,
    )

    try:
        # Initialize OAuth (loads existing tokens/client info if available)
        await oauth._initialize()

        # Check if we already have valid tokens
        if oauth.context.current_tokens:
            # Check if token is still valid (not expired)
            if (
                oauth.context.current_tokens.expires_in is None
                or oauth.context.current_tokens.expires_in > OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID
            ):
                no_expires_in = oauth.context.current_tokens.expires_in is None
                return HTMLResponse(
                    content=f"""
                    <html>
                    <body>
                    <h1>OAuth tokens are still valid
                    {" (no expires_in)" if no_expires_in else ""}.</h1>
                    <p>You can close this window.</p>
                    </body>
                    </html>
                    """,
                    status_code=HTTPStatus.OK,
                )

        # Web browser flow: start OAuth flow as background task and return redirect
        async def run_oauth_flow() -> None:
            """Run OAuth flow in background, waiting for callback."""

            try:
                async with httpx.AsyncClient(follow_redirects=True, auth=oauth) as client:
                    await client.get(
                        mcp_server_url, timeout=OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT
                    )
                    logger.info("OAuth2 flow completed successfully in background")
            except Exception as e:
                logger.error(f"OAuth2 background flow failed: {e}", exc_info=True)

        # Start the OAuth flow as a background task
        ShutdownManager.register_drainable_background_worker(
            f"OAuth2Flow-${mcp_server_url}-{time.monotonic()}", run_oauth_flow
        )

        # Wait for the authorization URL to be available
        try:
            authorization_url = await oauth.get_authorization_url(
                timeout=OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT
            )
            # Return redirect response to the client (who should've opened this URL in a
            # web browser window)
            return RedirectResponse(url=authorization_url)
        except TimeoutError as e:
            logger.exception(f"Failed to get authorization URL: {e}")
            raise PlatformHTTPError(
                error_code=ErrorCode.PRECONDITION_FAILED,
                message="Failed to get authorization URL. Please try again.",
            ) from e
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.exception(f"OAuth2 login failed: {e}")
        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message=f"OAuth2 login failed: {e}",
        ) from e


@router.post("/local_login", response_model=OAuth2LoginResponse)
async def oauth2_local_login(
    payload: OAuth2LoginRequest,
    user: AuthedUser,
    storage: StorageDependency,
    request: Request,
) -> OAuth2LoginResponse:
    """
    Start OAuth2 login flow for an MCP server from local/API clients.

    Opens a browser window for user authorization and waits for the callback.
    This is intended for local development and will automatically open a browser window
    in the same machine the server is running.

    Returns a message indicating the OAuth2 flow has completed successfully or
    a message with a non 200 status code if the flow fails (e.g.: timed out, etc.).
    """
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.server.oauth.oauth_provider import OAuth, TokenStorageAdapter

    # Create token storage adapter
    token_storage_adapter = TokenStorageAdapter(
        storage=storage, user_id=user.user_id, mcp_url=payload.mcp_server_url
    )

    # Get base redirect URI from request
    base_url_str = str(request.base_url).rstrip("/")
    base_redirect_uri = AnyHttpUrl(f"{base_url_str}/api/v2/oauth2/callback")

    # Create OAuth instance with web_mode=False for local flow (uses webbrowser.open)
    oauth = OAuth(
        mcp_url=payload.mcp_server_url,
        token_storage_adapter=token_storage_adapter,
        base_redirect_uri=base_redirect_uri,
        web_mode=False,
    )

    try:
        # Initialize OAuth (loads existing tokens/client info if available)
        await oauth._initialize()

        # Check if we already have valid tokens
        if oauth.context.current_tokens:
            # Check if token is still valid (not expired)
            if (
                oauth.context.current_tokens.expires_in is None
                or oauth.context.current_tokens.expires_in > OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID
            ):
                return OAuth2LoginResponse(
                    message="OAuth2 authentication tokens are still valid.",
                )

        # Local/API flow: uses webbrowser.open to open a browser window and blocks
        # until the OAuth flow completes.
        async with httpx.AsyncClient(follow_redirects=True, auth=oauth) as client:
            try:
                await client.get(
                    payload.mcp_server_url, timeout=OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT
                )
                # If we get here, the OAuth flow completed successfully
                return OAuth2LoginResponse(
                    message="OAuth2 authentication completed successfully",
                )
            except httpx.TimeoutException as e:
                raise PlatformHTTPError(
                    error_code=ErrorCode.PRECONDITION_FAILED,
                    message="OAuth2 flow timed out. Please try again.",
                ) from e
            except Exception as e:
                logger.exception(f"OAuth2 login request failed: {e}")
                raise PlatformHTTPError(
                    error_code=ErrorCode.INTERNAL_ERROR,
                    message=f"OAuth2 login failed: {e}",
                ) from e
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.exception(f"OAuth2 login failed: {e}")
        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message=f"OAuth2 login failed: {e}",
        ) from e


@router.post("/logout")
async def oauth2_logout(
    mcp_server_url: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> dict[str, str]:
    """Logout from OAuth2 (delete tokens)."""
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    try:
        # Delete tokens and client info
        await storage.delete_mcp_oauth_token(user_id=user.user_id, mcp_url=mcp_server_url)
        await storage.delete_mcp_oauth_client_info(user_id=user.user_id, mcp_url=mcp_server_url)
        return {"message": "OAuth2 tokens deleted successfully"}
    except Exception as e:
        logger.exception(f"OAuth2 logout failed: {e}")
        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message=f"OAuth2 logout failed: {e}",
        ) from e


@router.get("/status")
async def oauth2_status(
    user: AuthedUser,
    storage: StorageDependency,
    mcp_server_url: str | None = Query(None, description="Optional MCP server URL to filter by"),
) -> dict[str, OAuth2StatusResponse]:
    """Get OAuth2 authentication status for a user and MCP server.

    If no MCP server ID is provided, will return status for all MCP servers that
    the user has logged in to (otherwise, will return status for the specified MCP server).

    Returns a dictionary of MCP server IDs (when mcp_server_id is provided) or MCP URLs
    (when querying all servers) to OAuth2 status responses.
    """
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.server.storage import MCPServerNotFoundError

    status_responses: dict[str, OAuth2StatusResponse] = {}

    try:
        if mcp_server_url:
            # Get status for a specific MCP server
            token = await storage.get_mcp_oauth_token(
                user_id=user.user_id, mcp_url=mcp_server_url, decrypt=False
            )

            if token is None:
                status_responses[mcp_server_url] = OAuth2StatusResponse(
                    authenticated=False,
                    has_refresh_token=False,
                    token_expires_in=None,
                )
            else:
                status_responses[mcp_server_url] = OAuth2StatusResponse(
                    authenticated=bool(
                        token.access_token
                        and (
                            token.expires_in is None
                            or token.expires_in > OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID
                        )
                    ),
                    has_refresh_token=bool(token.refresh_token),
                    token_expires_in=token.expires_in if token else None,
                )
        else:
            # Get status for all MCP servers that the user has logged in to
            mcp_url_to_token = await storage.get_mcp_server_to_oauth_token(user_id=user.user_id)
            # Map mcp_url back to mcp_server_id for the response
            for mcp_url, token in mcp_url_to_token.items():
                # Find the mcp_server_id for this URL
                # We'll use the URL as the key in the response since we don't have a direct mapping
                # The client should handle this appropriately
                status_responses[mcp_url] = OAuth2StatusResponse(
                    authenticated=bool(
                        token.access_token
                        and (
                            token.expires_in is None
                            or token.expires_in > OAUTH2_MIN_TIME_TO_CONSIDER_TOKEN_VALID
                        )
                    ),
                    has_refresh_token=bool(token.refresh_token),
                    token_expires_in=token.expires_in,
                )

        return status_responses
    except MCPServerNotFoundError as e:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"MCP server not found: {e}",
        ) from e
    except Exception as e:
        logger.exception(f"OAuth2 status check failed: {e}")
        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message=f"Unexpected error occurred while checking OAuth2 status: {e}",
        ) from e


@router.get("/callback/{callback_id}")
async def oauth2_callback(
    callback_id: str,
    storage: StorageDependency,
    code: str | None = Query(None, description="Authorization code from OAuth provider"),
    state: str | None = Query(None, description="State parameter from OAuth provider"),
) -> HTMLResponse:
    """Handle OAuth2 callback from provider."""
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    try:
        # Store the callback result in the database
        await storage.set_mcp_oauth_callback_result(
            callback_id=callback_id, code=code, state=state, error=None
        )
        return HTMLResponse(
            content="""
            <html>
            <body>
            <h1>OAuth2 callback received successfully</h1>
            <p>You can close this window.</p>
            </body>
            </html>
            """,
            status_code=HTTPStatus.OK,
        )
    except Exception as e:
        logger.exception(f"OAuth2 callback failed: {e}")
        # Store error in callback result
        await storage.set_mcp_oauth_callback_result(
            callback_id=callback_id, code=None, state=None, error=e
        )
        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message=f"OAuth2 callback failed: {e}",
        ) from e


@router.post("/refresh")
async def oauth2_refresh(
    mcp_server_url: str,
    user: AuthedUser,
    storage: StorageDependency,
    request: Request,
) -> dict[str, str]:
    """Refresh OAuth2 access token."""
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.server.oauth.oauth_provider import OAuth, TokenStorageAdapter

    # Get existing token
    token = await storage.get_mcp_oauth_token(
        user_id=user.user_id, mcp_url=mcp_server_url, decrypt=False
    )
    if not token:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message="No OAuth token found. Please login first.",
        )

    if not token.refresh_token:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="No refresh token available. Please login again.",
        )

    # Create token storage adapter
    token_storage_adapter = TokenStorageAdapter(
        storage=storage, user_id=user.user_id, mcp_url=mcp_server_url
    )

    # Get base redirect URI from request
    base_url_str = str(request.base_url).rstrip("/")
    base_redirect_uri = AnyHttpUrl(f"{base_url_str}/api/v2/oauth2/callback")

    # Create OAuth instance
    oauth = OAuth(
        mcp_url=mcp_server_url,
        token_storage_adapter=token_storage_adapter,
        base_redirect_uri=base_redirect_uri,
    )

    try:
        # Initialize OAuth (loads existing tokens/client info)
        await oauth._initialize()

        # Trigger token refresh by making a request with the OAuth auth handler
        # The OAuth handler will automatically refresh the token if needed
        async with httpx.AsyncClient(follow_redirects=True, auth=oauth) as client:
            # Make a request to trigger token refresh
            response = await client.get(
                mcp_server_url, timeout=OAUTH2_MIN_TIME_FOR_USER_INTERACTION_TIMEOUT
            )
            response.raise_for_status()

            return {"message": "OAuth2 token refreshed successfully"}
    except Exception as e:
        logger.exception(f"OAuth2 refresh failed: {e}")
        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message=f"OAuth2 refresh failed: {e}",
        ) from e
