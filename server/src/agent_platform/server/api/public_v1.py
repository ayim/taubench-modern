# Standard library imports
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any

# Third-party imports
from fastapi import APIRouter, Query
from fastapi.params import Body
from sse_starlette import EventSourceResponse

from agent_platform.server.auth.handlers import AuthedUser

PUBLIC_V1_PREFIX = "/api/public/v1"

router = APIRouter()


class Mode(str, Enum):
    CONVERSATIONAL = "conversational"
    WORKER = "worker"


class Architecture(str, Enum):
    AGENT = "agent"
    PLAN_EXECUTE = "plan_execute"


class Provider(str, Enum):
    OPENAI = "OpenAI"
    AZURE = "Azure"
    AMAZON = "Amazon"
    SNOWFLAKE_CORTEX = "Snowflake Cortex AI"


@dataclass
class ActionPackage:
    name: str
    organization: str
    version: str
    actions: str


@dataclass
class LanguageModel:
    provider: Provider
    model: str


@dataclass
class Agent:
    id: str
    name: str
    description: str
    llm: LanguageModel
    architecture: Architecture
    mode: Mode


class Role(str, Enum):
    AGENT = "agent"
    HUMAN = "human"


class MessageType(str, Enum):
    MESSAGE = "message"
    TOKEN = "token"
    TOOL_REQUEST = "action_request"
    TOOL_RESPONSE = "action_response"
    START_STREAM = "start_stream"
    END_STREAM = "end_stream"


@dataclass
class Message:
    id: str | None
    type: MessageType
    role: Role
    content: str
    channel: str = field(default="chat")


@dataclass
class TokenMessage:
    id: str | None
    type: MessageType
    role: Role
    token: str
    token_sequence: int
    channel: str = field(default="chat")


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class ToolRequest:
    action_calls: list[ToolCall]
    id: str | None
    type: MessageType
    role: Role
    content: str
    channel: str = field(default="chat")


@dataclass
class ToolResponse:
    action_call_id: str
    status: str
    result: dict
    id: str | None
    type: MessageType
    role: Role
    content: str
    channel: str = field(default="chat")


@dataclass
class CreateChatRequest:
    name: str


@dataclass
class ChatMessageRequest:
    content: str


@dataclass
class PaginatedResponse:
    next: str | None
    has_more: bool
    data: list[Any]


@dataclass
class Conversation:
    id: str | None
    name: str
    agent_id: str


@dataclass
class ConversationState(Conversation):
    messages: list[Message | ToolRequest | ToolResponse] | None


@router.get(
    "/agents",
    summary="List agents",
    description=(
        "Returns a list of all agents for the authenticated user. You can "
        "filter by name using the 'name' query parameter."
    ),
    response_description="List of agents",
    response_model=PaginatedResponse,
    tags=["agents"],
    responses={
        200: {"description": "Success"},
        500: {"description": "Internal Server Error"},
    },
)
async def get_agents(
    user: AuthedUser,
    limit: int | None = None,
    name: str | None = Query(
        None,
        description="Filter agents by name (starts with, case insensitive).",
    ),
) -> PaginatedResponse:
    raise NotImplementedError("Not implemented")


@router.get(
    "/agents/{aid}",
    summary="Get agent",
    description="Returns the agent with the given name.",
    response_description="Agent",
    response_model=Agent,
    tags=["agents"],
    responses={
        200: {"description": "Success"},
        404: {"description": "Agent not found"},
        500: {"description": "Internal Server Error"},
    },
)
async def get_agent_by_name(
    user: AuthedUser,
    aid: str,
) -> Agent:
    raise NotImplementedError("Not implemented")


@router.get(
    "/agents/{aid}/conversations",
    summary="List conversations",
    description="Returns a list of all conversations for the given agent.",
    response_description="List of conversations",
    response_model=PaginatedResponse,
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request"},
        500: {"description": "Internal Server Error"},
    },
)
async def get_conversations(
    user: AuthedUser,
    aid: str,
    limit: int | None = None,
) -> PaginatedResponse:
    raise NotImplementedError("Not implemented")


@router.get(
    "/agents/{aid}/conversations/{cid}/messages",
    summary="Get conversation messages",
    description=(
        "Returns the conversation messages of the given chat_id for the given agent."
    ),
    response_description="Conversation",
    response_model=ConversationState,
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        404: {"description": "Agent/Conversation not found"},
        500: {"description": "Internal Server Error"},
    },
)
async def get_chat_messages(
    user: AuthedUser,
    aid: str,
    cid: str,
) -> ConversationState:
    raise NotImplementedError("Not implemented")


@router.post(
    "/agents/{aid}/conversations",
    summary="Create new conversation",
    description="Creates a new conversation for the given agent.",
    response_description="Conversation",
    response_model=Conversation,
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def create_conversation(
    user: AuthedUser,
    aid: str,
    body: Annotated[CreateChatRequest, Body()],
) -> Conversation:
    raise NotImplementedError("Not implemented")


@router.post(
    "/agents/{aid}/conversations/{cid}/messages",
    summary="Post a message (synchronous)",
    description=(
        "Post a message to a conversation thread, and get the updated "
        "conversation state."
    ),
    response_description="Conversation with messages",
    response_model=ConversationState,
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def post_messages_simple(
    user: AuthedUser,
    aid: str,
    cid: str,
    body: Annotated[ChatMessageRequest, Body()],
) -> ConversationState:
    raise NotImplementedError("Not implemented")


@router.post(
    "/agents/{aid}/conversations/{cid}/stream",
    summary="Post a message to a conversation and stream the response",
    description="Post a message to a conversation and stream the response",
    response_description="SSE Stream of messages",
    response_model=None,  # EventSourceResponse is not a Pydantic model
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def post_public_api_messages_simple(
    user: AuthedUser,
    aid: str,
    cid: str,
    body: Annotated[ChatMessageRequest, Body()],
) -> EventSourceResponse:
    raise NotImplementedError("Not implemented")


@router.post(
    "/agents/{aid}/conversations/{cid}/messages/detailed",
    summary="Post messages (synchronous)",
    description=(
        "Post messages to a conversation thread, and get the updated "
        "conversation state."
    ),
    response_description="Conversation with messages",
    response_model=ConversationState,
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def post_messages_detailed(
    user: AuthedUser,
    aid: str,
    cid: str,
    messages: list[Message],
) -> ConversationState:
    raise NotImplementedError("Not implemented")


@router.post(
    "/agents/{aid}/conversations/{cid}/stream/detailed",
    summary="Post messages to a conversation and stream the response",
    description="Post messages to a conversation and stream the response",
    response_description="SSE Stream of messages",
    response_model=None,  # EventSourceResponse is not a Pydantic model
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def post_public_api_messages_detailed(
    user: AuthedUser,
    aid: str,
    cid: str,
    messages: list[Message],
) -> EventSourceResponse:
    raise NotImplementedError("Not implemented")


@router.delete(
    "/agents/{aid}/conversations/{cid}",
    summary="Delete conversation",
    description=(
        "Deletes the conversation with the given conversation ID for the given agent."
    ),
    response_description="Conversation",
    response_model=Conversation,
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        404: {"description": "Conversation not found"},
        500: {"description": "Internal Server Error"},
    },
)
async def delete_chat(
    user: AuthedUser,
    aid: str,
    cid: str,
):
    raise NotImplementedError("Not implemented")
