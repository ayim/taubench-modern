import contextvars
import logging
from typing import Annotated, assert_never

from fastapi import HTTPException, Request
from mcp.server import FastMCP
from pydantic import Field
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from starlette.middleware.base import RequestResponseEndpoint as StarletteRequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

import agent_platform.server.api.private_v2.agents as agents_api
import agent_platform.server.api.private_v2.runs as runs_api
import agent_platform.server.api.private_v2.threads as threads_api
from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.messages import ThreadAgentMessage, ThreadUserMessage
from agent_platform.core.thread.thread import Thread
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.auth.handlers import get_auth_handler
from agent_platform.server.storage import StorageService

logger = logging.getLogger(__name__)


# Context variable to store the authenticated user for the current request
# This allows accessing the user throughout the request lifecycle without passing it explicitly
_mcp_authenticated_user = contextvars.ContextVar("mcp_authenticated_user")


class MCPAuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts the authenticated user from the request
    and stores it in a context variable.

    This middleware is responsible for:
    1. Extracting the authenticated user from the request
    using the agent server's authentication system
    2. Storing the user in a context variable for use by MCP tools and resources
    3. Enabling proper authentication and authorization for MCP endpoints
    """

    def __init__(
        self,
        app: ASGIApp,
        dispatch: DispatchFunction | None = None,
    ):
        super().__init__(app, dispatch)
        self._auth_handler = get_auth_handler(StorageService.get_instance())

    async def dispatch(self, request: Request, call_next: StarletteRequestResponseEndpoint) -> Response:
        # Exceptions from sub-apps are not raised properly.
        # https://github.com/fastapi/fastapi/discussions/9098

        try:
            user = await self._auth_handler.handle(request)
            _mcp_authenticated_user.set(user)
            return await call_next(request)
        except Exception as e:
            return self._handle_exception(e)

    @staticmethod
    def _handle_exception(exc: Exception) -> Response:
        match exc:
            case HTTPException():
                return Response(status_code=exc.status_code, content=exc.detail)
            case Exception():
                logger.exception("MCP request failed", exc_info=exc)
                return Response(status_code=500, content="Internal server error")
            case _:
                assert_never(exc)


def get_mcp_user():
    """Retrieve the authenticated user from the current request context.

    This function provides access to the authenticated user that was stored
    by the MCPAuthenticationMiddleware.

    Returns:
        The authenticated User object for the current request
    """

    if user := _mcp_authenticated_user.get():
        return user

    raise HTTPException(status_code=401, detail="Not authenticated")


mcp = FastMCP("Agent Server MCP")


@mcp.tool(
    "list_agents",
    description="List all agents hosted on the server.",
)
async def list_agents() -> list[AgentCompat]:
    storage = StorageService.get_instance()
    mcp_user = get_mcp_user()
    return await agents_api.list_agents(mcp_user, storage)


@mcp.tool(
    "chat_with_agent",
    description=(
        "Chat with an agent on thread (conversation) by providing a thread "
        "name and a message. If the existing_thread_id is not provided, "
        "a new thread will be created. If you need to continue a conversation "
        "with an agent, you can provide the existing_thread_id of the thread "
        "you wish to continue chatting on."
    ),
)
async def chat_with_agent(
    agent_id: Annotated[
        str,
        Field(description="The UUID of the agent to chat with, this must be provided."),
    ],
    thread_name: Annotated[
        str,
        Field(description="The name of the thread to chat on, this must be provided."),
    ],
    message: Annotated[
        str,
        Field(description="The message to send to the agent, this must be provided."),
    ],
    existing_thread_id: Annotated[
        str | None,
        Field(
            description=(
                "The UUID of the thread to continue chatting on, only provide this "
                "if you wish to continue a conversation with an agent."
            ),
        ),
    ],
) -> list[ThreadAgentMessage]:
    storage = StorageService.get_instance()
    mcp_user = get_mcp_user()
    initiate_payload = InitiateStreamPayload(
        agent_id=agent_id,
        thread_id=existing_thread_id,
        name=thread_name,
        messages=[
            ThreadUserMessage(
                content=[ThreadTextContent(text=message)],
            )
        ],
    )
    return await runs_api.sync_run(
        agent_id,
        initiate_payload,
        mcp_user,
        storage,
        Request(scope={"type": "http", "method": "POST"}),
    )


@mcp.tool(
    "list_threads_for_agent",
    description="List all threads for an agent.",
)
async def list_threads_for_agent(
    agent_id: Annotated[
        str,
        Field(
            description="The UUID of the agent to list threads for, this must be provided.",
        ),
    ],
) -> list[Thread]:
    storage = StorageService.get_instance()
    mcp_user = get_mcp_user()
    return await threads_api.list_threads(
        mcp_user,
        storage,
        agent_id=agent_id,
        limit=50,
    )


@mcp.resource("agents://{agent_name}")
async def agents_resource(agent_name: str) -> AgentCompat:
    storage = StorageService.get_instance()
    mcp_user = get_mcp_user()
    return await agents_api.get_agent_by_name(mcp_user, agent_name, storage)
