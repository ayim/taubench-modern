"""
Agent Message Control Protocol (MCP) API implementation.

This module provides an interface for agents to communicate with users through
a standardized protocol. It handles chat sessions, thread management, and message
routing between users and agents in the platform.
"""

import contextvars
import logging
import re
from collections.abc import Generator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from anyio import ClosedResourceError
from mcp import types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from pydantic import BaseModel, ConfigDict, Field
from starlette import types as starlette_types
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from agent_platform.core import User
from agent_platform.core.agent import Agent
from agent_platform.core.payloads import InitiateStreamPayload
from agent_platform.core.thread import ThreadTextContent
from agent_platform.server.api.private_v2.runs import sync_run
from agent_platform.server.auth.handlers import get_auth_handler
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage import StorageService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Context:
    """
    Request context container for storing agent, user, and request information.

    This immutable context is stored in a context variable and accessed during request processing.
    """

    agent: Agent
    user: User
    request: Request


# Context variable to store request context throughout the request lifecycle
_ctx = contextvars.ContextVar[_Context]("agent_mcp.request")


class ChatWithAgentInputSchema(BaseModel):
    """
    Schema for chat input to an agent.

    Defines the structure of messages sent to agents, including the text message,
    optional file attachments, and a thread identifier for conversation continuity.
    """

    message: str
    thread_identifier: Annotated[
        str,
        Field(
            description="A unique human readable identifier for the thread. "
            "Generate one if not present in the current context "
            "and always use it in subsequent calls to this tool. "
            "Also make sure it has an element of uniqueness "
            "like 6 random alphanumeric characters at the end.",
        ),
    ]

    model_config = ConfigDict(str_strip_whitespace=True)


def _get_tool_name(agent: Agent) -> str:
    """
    Generate a standardized tool name for an agent.

    Converts the agent name to lowercase, replaces spaces with underscores, and
    removes any non-alphanumeric characters.

    Args:
        agent: The Agent object containing the agent name to be transformed

    Returns:
        A sanitized tool name string in the format "message_{agent_name}_agent".
    """
    agent_name = agent.name.lower().replace(" ", "_")
    agent_name = re.sub(r"[^a-z0-9_]", "", agent_name)
    if not agent_name.endswith("agent"):
        agent_name = f"{agent_name}_agent"

    return f"message_{agent_name}"


async def chat_with_agent(data: ChatWithAgentInputSchema) -> Generator[str, None, None]:
    """
    Process a chat message sent to an agent and return the agent's response.

    This function:
    1. Retrieves the current request context
    2. Finds or creates a thread for the conversation
    3. Prepares and sends the message to the agent
    4. Returns a generator that yields the agent's response text

    Args:
        data: The validated chat input containing message, files, and thread identifier

    Returns:
        A generator yielding strings of the agent's response
    """

    # Get the current request context
    ctx = _ctx.get()

    # Retrieve all threads for this agent and user
    # TODO: Maybe add BaseStorage.get_thread_by_name() method
    agent_threads = await StorageService.get_instance().list_threads_for_agent(
        ctx.user.user_id, ctx.agent.agent_id
    )

    # Find an existing thread with the given identifier, if any
    thread = next((t for t in agent_threads if t.name == data.thread_identifier), None)

    payload = {
        "agent_id": ctx.agent.agent_id,
        "messages": [
            {
                "role": "user",  # Specify the message is from the user
                "content": [{"kind": "text", "text": data.message}],
            }
        ],
    }

    # Add either thread_id (existing thread) or name (new thread)
    if thread:
        payload["thread_id"] = thread.thread_id
    else:
        payload["name"] = data.thread_identifier

    stream_payload = InitiateStreamPayload.model_validate(payload)

    # Process the message and get the response stream
    run_result = await sync_run(
        agent_id=ctx.agent.agent_id,
        initial_payload=stream_payload,
        user=ctx.user,
        storage=StorageService.get_instance(),
        request=ctx.request,
    )

    # Create a generator to extract text content from the response
    def message_generator():
        nonlocal run_result
        for agent_message in run_result:
            for content in agent_message.content:
                if isinstance(content, ThreadTextContent):
                    yield content.text.strip()

    return message_generator()


# JSON schema for the chat input, used for tool registration
CHAT_WITH_AGENT_SCHEMA = ChatWithAgentInputSchema.model_json_schema()

# Initialize the MCP server
_agent_mcp_server = Server("Agent Chat MCP")


@_agent_mcp_server.list_tools()
async def list_tools() -> list[mcp_types.Tool]:
    """
    List available tools for the MCP server.

    This function is called by the MCP framework to discover what tools are available.

    Returns:
        A list of Tool objects that can be called by clients
    """
    return [
        mcp_types.Tool(name=_get_tool_name(_ctx.get().agent), inputSchema=CHAT_WITH_AGENT_SCHEMA),
    ]


@_agent_mcp_server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> Iterable[mcp_types.TextContent | mcp_types.ImageContent | mcp_types.EmbeddedResource]:
    """
    Execute a tool call with the given name and arguments.

    This function is called by the MCP framework when a client requests a tool execution.
    It validates that the requested tool exists, processes the arguments, and returns
    the results of the tool execution.

    Args:
        name: The name of the tool to call
        arguments: Dictionary of arguments for the tool

    Returns:
        An iterable of content objects (text, images, etc.) from the tool execution

    Raises:
        ValueError: If the requested tool name doesn't match any available tools
    """

    # Get the expected tool name for the current agent
    tool_name = _get_tool_name(_ctx.get().agent)

    if name == tool_name:
        # Validate the arguments against the schema
        parsed_arguments = ChatWithAgentInputSchema.model_validate(arguments)
        try:
            # Process the chat message and get the response generator
            messages = await chat_with_agent(parsed_arguments)
        except Exception as e:
            logger.exception("Error running chat_with_agent tool", exc_info=e)
            raise e

        # Convert the text messages to MCP TextContent objects
        return [mcp_types.TextContent(text=text, type="text") for text in messages]

    # If the tool name doesn't match, raise an error
    raise ValueError(f"Unknown tool name: {name}")


class AgentMCPApp:
    """
    ASGI application for handling agent MCP requests.

    This class implements the ASGI interface and handles authentication,
    agent retrieval, and request processing for the MCP protocol.
    """

    def __init__(self, session_manager: StreamableHTTPSessionManager):
        """
        Args:
            session_manager: The HTTP session manager for handling MCP requests
        """
        self._session_manager = session_manager
        self._auth_handler = get_auth_handler(StorageService.get_instance())

    async def __call__(
        self,
        scope: starlette_types.Scope,
        receive: starlette_types.Receive,
        send: starlette_types.Send,
    ):
        """
        ASGI application entry point.

        Processes incoming requests by:
        1. Validating the request is an HTTP request
        2. Authenticating the user
        3. Extracting and validating the agent ID
        4. Setting up the request context
        5. Delegating to the MCP session manager

        Args:
            scope: ASGI connection scope
            receive: ASGI receive channel
            send: ASGI send channel
        """
        # Only handle HTTP requests
        if scope["type"] != "http":
            await Response(status_code=501)(scope, receive, send)
            return

        # Create a Starlette request object
        request = Request(scope, receive, send)

        # Authenticate the user
        if (user := await self._auth_handler.handle(request)) is None:
            raise HTTPException(status_code=403, detail="Unauthorized")

        # Extract and validate the agent ID from the path
        if not (agent_id := request.path_params.get("agent_id")):
            raise HTTPException(status_code=404, detail="Not Found")

        # Retrieve the agent from storage
        agent = await StorageService.get_instance().get_agent(user.user_id, agent_id)

        # Set the request context for this request
        _ctx.set(_Context(agent=agent, user=user, request=request))

        # Delegate to the MCP session manager
        await self._session_manager.handle_request(scope, receive, send)


def build_agent_mcp_app():
    """
    Build and configure the Starlette application for agent MCP.

    This function:
    1. Creates a session manager for the MCP server
    2. Creates an ASGI application for handling requests
    3. Sets up the application lifespan to manage the session manager
    4. Mounts the application at the appropriate path

    Returns:
        A configured Starlette application
    """
    # Create a session manager for the MCP server
    session_manager = StreamableHTTPSessionManager(_agent_mcp_server, stateless=True)
    # Create the ASGI application
    asgi_app = AgentMCPApp(session_manager)

    # Define the application lifespan to manage the session manager
    @asynccontextmanager
    async def _lifespan(_app: Starlette):
        nonlocal session_manager
        try:
            async with session_manager.run():
                yield
        except ClosedResourceError:
            pass

    # Create the Starlette application with the lifespan
    agent_mcp = Starlette(lifespan=_lifespan)

    # Register platform-wide exception handlers so errors like UserAccessDeniedError
    # are mapped to the correct HTTP status codes instead of bubbling up as 500s.
    add_exception_handlers(agent_mcp)
    # Mount the ASGI application at the appropriate path
    agent_mcp.mount("/{agent_id:str}/mcp", asgi_app)

    return agent_mcp
