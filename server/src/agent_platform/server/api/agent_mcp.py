"""
Agent Message Control Protocol (MCP) API implementation.

This module provides an interface for agents to communicate with users through
a standardized protocol. It handles chat sessions, thread management, and message
routing between users and agents in the platform.
"""

import contextvars
import json
import logging
import re
from collections.abc import Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import cache
from typing import Annotated, Literal
from uuid import UUID

from anyio import ClosedResourceError
from mcp import types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent
from pydantic import BaseModel, ConfigDict, Field
from starlette import types as starlette_types
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from agent_platform.core import User
from agent_platform.core.agent import Agent
from agent_platform.core.payloads import InitiateStreamPayload
from agent_platform.core.thread import (
    ThreadAttachmentContent,
    ThreadTextContent,
    ThreadToolUsageContent,
)
from agent_platform.server.api.private_v2.runs import sync_run
from agent_platform.server.auth.handlers import AuthHandler, get_auth_handler
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage import StorageService

logger = logging.getLogger(__name__)


AGENT_MCP_OPENAPI_SCHEMA_PATHS = {
    "/agent-mcp/{aid}/mcp/": {
        "post": {
            "summary": "Send JSON-RPC messages to the MCP server",
            "tags": ["mcp", "agents"],
            "parameters": [
                {
                    "name": "aid",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "title": "Agent ID"},
                }
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "oneOf": [
                                {
                                    "type": "object",
                                    "required": ["jsonrpc", "id", "method"],
                                    "properties": {
                                        "jsonrpc": {"type": "string", "enum": ["2.0"]},
                                        "id": {"oneOf": [{"type": "integer"}, {"type": "string"}]},
                                        "method": {"type": "string"},
                                        "params": {"type": "object", "additionalProperties": True},
                                    },
                                },
                                {
                                    "type": "array",
                                    "items": {
                                        "oneOf": [
                                            {
                                                "type": "object",
                                                "required": ["jsonrpc", "id", "method"],
                                                "properties": {
                                                    "jsonrpc": {"type": "string", "enum": ["2.0"]},
                                                    "id": {
                                                        "oneOf": [
                                                            {"type": "integer"},
                                                            {"type": "string"},
                                                        ]
                                                    },
                                                    "method": {"type": "string"},
                                                    "params": {
                                                        "type": "object",
                                                        "additionalProperties": True,
                                                    },
                                                },
                                            },
                                            {
                                                "type": "object",
                                                "required": ["jsonrpc", "id"],
                                                "properties": {
                                                    "jsonrpc": {"type": "string", "enum": ["2.0"]},
                                                    "id": {
                                                        "oneOf": [
                                                            {"type": "integer"},
                                                            {"type": "string"},
                                                            {"type": "null"},
                                                        ]
                                                    },
                                                    "result": {
                                                        "type": "object",
                                                        "additionalProperties": True,
                                                    },
                                                    "error": {
                                                        "type": "object",
                                                        "required": ["code", "message"],
                                                        "properties": {
                                                            "code": {"type": "integer"},
                                                            "message": {"type": "string"},
                                                            "data": {
                                                                "type": "object",
                                                                "additionalProperties": True,
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                            {
                                                "type": "object",
                                                "required": ["jsonrpc", "method"],
                                                "properties": {
                                                    "jsonrpc": {"type": "string", "enum": ["2.0"]},
                                                    "method": {"type": "string"},
                                                    "params": {
                                                        "type": "object",
                                                        "additionalProperties": True,
                                                    },
                                                },
                                            },
                                        ]
                                    },
                                },
                                {
                                    "type": "object",
                                    "required": ["jsonrpc", "id"],
                                    "properties": {
                                        "jsonrpc": {"type": "string", "enum": ["2.0"]},
                                        "id": {
                                            "oneOf": [
                                                {"type": "integer"},
                                                {"type": "string"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "result": {"type": "object", "additionalProperties": True},
                                        "error": {
                                            "type": "object",
                                            "required": ["code", "message"],
                                            "properties": {
                                                "code": {"type": "integer"},
                                                "message": {"type": "string"},
                                                "data": {
                                                    "type": "object",
                                                    "additionalProperties": True,
                                                },
                                            },
                                        },
                                    },
                                },
                            ]
                        }
                    },
                    "text/event-stream": {"schema": {"type": "string"}},
                },
            },
            "responses": {
                "202": {
                    "description": (
                        "Accepted (notifications-only input)\n"
                        "Server returns no body when input is purely notifications"
                    )
                },
                "200": {
                    "description": "JSON-RPC response(s)",
                    "content": {
                        "application/json": {
                            "schema": {
                                "oneOf": [
                                    {
                                        "type": "object",
                                        "required": ["jsonrpc", "id"],
                                        "properties": {
                                            "jsonrpc": {"type": "string", "enum": ["2.0"]},
                                            "id": {
                                                "oneOf": [
                                                    {"type": "integer"},
                                                    {"type": "string"},
                                                    {"type": "null"},
                                                ]
                                            },
                                            "result": {
                                                "type": "object",
                                                "additionalProperties": True,
                                            },
                                            "error": {
                                                "type": "object",
                                                "required": ["code", "message"],
                                                "properties": {
                                                    "code": {"type": "integer"},
                                                    "message": {"type": "string"},
                                                    "data": {
                                                        "type": "object",
                                                        "additionalProperties": True,
                                                    },
                                                },
                                            },
                                        },
                                    },
                                    {
                                        "type": "array",
                                        "items": {
                                            "oneOf": [
                                                {
                                                    "type": "object",
                                                    "required": ["jsonrpc", "id", "method"],
                                                    "properties": {
                                                        "jsonrpc": {
                                                            "type": "string",
                                                            "enum": ["2.0"],
                                                        },
                                                        "id": {
                                                            "oneOf": [
                                                                {"type": "integer"},
                                                                {"type": "string"},
                                                            ]
                                                        },
                                                        "method": {"type": "string"},
                                                        "params": {
                                                            "type": "object",
                                                            "additionalProperties": True,
                                                        },
                                                    },
                                                },
                                                {
                                                    "type": "object",
                                                    "required": ["jsonrpc", "id"],
                                                    "properties": {
                                                        "jsonrpc": {
                                                            "type": "string",
                                                            "enum": ["2.0"],
                                                        },
                                                        "id": {
                                                            "oneOf": [
                                                                {"type": "integer"},
                                                                {"type": "string"},
                                                                {"type": "null"},
                                                            ]
                                                        },
                                                        "result": {
                                                            "type": "object",
                                                            "additionalProperties": True,
                                                        },
                                                        "error": {
                                                            "type": "object",
                                                            "required": ["code", "message"],
                                                            "properties": {
                                                                "code": {"type": "integer"},
                                                                "message": {"type": "string"},
                                                                "data": {
                                                                    "type": "object",
                                                                    "additionalProperties": True,
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                                {
                                                    "type": "object",
                                                    "required": ["jsonrpc", "method"],
                                                    "properties": {
                                                        "jsonrpc": {
                                                            "type": "string",
                                                            "enum": ["2.0"],
                                                        },
                                                        "method": {"type": "string"},
                                                        "params": {
                                                            "type": "object",
                                                            "additionalProperties": True,
                                                        },
                                                    },
                                                },
                                            ]
                                        },
                                    },
                                ]
                            }
                        }
                    },
                },
                "400": {"description": "Bad Request (e.g., invalid JSON-RPC message)"},
            },
        },
        "get": {
            "summary": "Open an SSE stream for server-initiated messages",
            "tags": ["mcp", "agents"],
            "parameters": [
                {
                    "name": "aid",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "title": "Agent ID"},
                }
            ],
            "responses": {
                "200": {
                    "description": "Server-Sent Events stream of JSON-RPC requests/notifications",
                    "content": {"text/event-stream": {"schema": {"type": "string"}}},
                },
                "405": {"description": "Method Not Allowed - streaming not supported"},
            },
        },
    }
}


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


@cache
def _get_auth_handler() -> AuthHandler:
    """In order to run properly, the auth handler for MCP requests
    must be initialized on the first MCP request"""
    return get_auth_handler(StorageService.get_instance())


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


class ListThreadsInputSchema(BaseModel):
    """The MCP Server implementation list_tools requires
    that a tool call has a schema, even if it's an empty one."""

    pass


class ListThreadMessagesInputSchema(BaseModel):
    thread_id: Annotated[UUID, Field(description="The ID of the thread to list messages for.")]

    model_config = ConfigDict(str_strip_whitespace=True)


# JSON schema for the chat input, used for tool registration
CHAT_WITH_AGENT_SCHEMA = ChatWithAgentInputSchema.model_json_schema()
LIST_THREADS_SCHEMA = ListThreadsInputSchema.model_json_schema()
LIST_THREAD_MESSAGES_SCHEMA = ListThreadMessagesInputSchema.model_json_schema()


def _get_tool_names(
    agent: Agent,
) -> dict[Literal["chat", "list_threads", "get_thread_messages"], str]:
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

    return {
        "chat": f"message_{agent_name}",
        "list_threads": f"list_{agent_name}_threads",
        "get_thread_messages": f"get_{agent_name}_thread_messages",
    }


async def _chat_with_agent(data: ChatWithAgentInputSchema) -> list[mcp_types.TextContent]:
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
    def _message_generator():
        nonlocal run_result
        for agent_message in run_result:
            for content in agent_message.content:
                match content:
                    case ThreadTextContent():
                        yield content.text.strip()
                    case ThreadToolUsageContent():
                        yield content.as_text_content()

    # Convert the text messages to MCP TextContent objects
    return [mcp_types.TextContent(text=text, type="text") for text in _message_generator()]


async def _list_threads() -> list[mcp_types.TextContent]:
    ctx = _ctx.get()
    threads = await StorageService.get_instance().list_threads_for_agent(
        ctx.user.user_id, ctx.agent.agent_id
    )

    data = {"threads": [{"thread_identifier": t.name, "thread_id": t.thread_id} for t in threads]}

    return [
        TextContent.model_validate(
            {
                "type": "text",
                "content_type": "application/json",
                "text": json.dumps(data),
            }
        )
    ]


async def _get_thread_messages(data: ListThreadMessagesInputSchema) -> list[mcp_types.TextContent]:
    user_id = _ctx.get().user.user_id
    thread = await StorageService.get_instance().get_thread(user_id, str(data.thread_id))

    thread_messages = []
    for message in thread.messages:
        content_data = []
        for content in message.content:
            match content:
                case ThreadTextContent(text):
                    content_data.append({"kind": content.kind, "text": text.strip()})
                case ThreadToolUsageContent():
                    content_data.append(
                        {
                            "kind": content.kind,
                            "name": content.name,
                            "status": content.status,
                            "result": content.result,
                            "error": content.error,
                        }
                    )
                case ThreadAttachmentContent():
                    attachment_data = {
                        "name": content.name,
                        "mime_type": content.mime_type,
                        "description": content.description,
                    }

                    if content.uri:
                        attachment_data["uri"] = content.uri
                    elif content.base64_data:
                        attachment_data["base64_data"] = content.base64_data
                    else:
                        logger.warning(
                            f"No URI or base64 data found for attachment {content.content_id}"
                        )
                        # Exclude attachment without base64 or uri
                        continue

                    content_data.append(attachment_data)

        thread_messages.append({"role": message.role, "content": content_data})

    return [
        mcp_types.TextContent.model_validate(
            {
                "type": "text",
                "content_type": "application/json",
                "text": json.dumps({"thread_messages": thread_messages}),
            }
        )
    ]


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
    tool_names = _get_tool_names(_ctx.get().agent)

    return [
        mcp_types.Tool(
            name=tool_names["chat"],
            inputSchema=CHAT_WITH_AGENT_SCHEMA,
        ),
        mcp_types.Tool(
            name=tool_names["list_threads"],
            inputSchema=LIST_THREADS_SCHEMA,
        ),
        mcp_types.Tool(
            name=tool_names["get_thread_messages"],
            inputSchema=LIST_THREAD_MESSAGES_SCHEMA,
        ),
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
    tool_names = _get_tool_names(_ctx.get().agent)

    if name == tool_names["chat"]:
        # Validate the arguments against the schema
        parsed_arguments = ChatWithAgentInputSchema.model_validate(arguments)

        try:
            return await _chat_with_agent(parsed_arguments)
        except Exception as e:
            logger.exception("Error running chat_with_agent tool", exc_info=e)
            raise e

    elif name == tool_names["list_threads"]:
        try:
            return await _list_threads()
        except Exception as e:
            logger.exception("Error running list_threads tool", exc_info=e)
            raise e
    elif name == tool_names["get_thread_messages"]:
        # Validate the arguments against the schema
        parsed_arguments = ListThreadMessagesInputSchema.model_validate(arguments)

        try:
            return await _get_thread_messages(parsed_arguments)
        except Exception as e:
            logger.exception("Error running get_thread_messages tool", exc_info=e)
            raise e

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
        if (user := await _get_auth_handler().handle(request)) is None:
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
    agent_mcp.mount("/{agent_id:str}/mcp/", asgi_app)

    return agent_mcp
