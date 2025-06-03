# Standard library imports
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.params import Body
from sse_starlette import EventSourceResponse

from agent_platform.core.thread import Thread
from agent_platform.server.api.dependencies import FileManagerDependency, StorageDependency
from agent_platform.server.api.public_v2.compat import AgentCompat, ConversationCompat
from agent_platform.server.auth.handlers import AuthedUser

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
    "/",
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
    storage: StorageDependency,
    limit: int | None = None,
    name: str | None = Query(
        None,
        description="Filter agents by name (starts with, case insensitive).",
    ),
) -> PaginatedResponse:
    agents = [AgentCompat.from_agent(a) for a in await storage.list_agents(user.user_id)]
    if name:
        agents = [agent for agent in agents if agent.name.lower().startswith(name.lower())]
    return PaginatedResponse(next=None, has_more=False, data=agents)


@router.get(
    "/{aid}",
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
    storage: StorageDependency,
    aid: str,
) -> AgentCompat:
    # TODO api v1 don't search by name despite the name of this endpoint
    agent = await storage.get_agent(user.user_id, aid)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentCompat.from_agent(agent)


@router.get(
    "/{aid}/conversations",
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
    storage: StorageDependency,
    limit: int | None = None,
) -> PaginatedResponse:
    agent = await storage.get_agent(user.user_id, aid)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    threads = await storage.list_threads_for_agent(user.user_id, agent.agent_id)
    data = [ConversationCompat.from_thread(thread) for thread in threads[:limit]]
    return PaginatedResponse(next=None, has_more=False, data=data)


@router.get(
    "/{aid}/conversations/{cid}/messages",
    summary="Get conversation messages",
    description=("Returns the conversation messages of the given chat_id for the given agent."),
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
    storage: StorageDependency,
    aid: str,
    cid: str,
) -> ConversationCompat | None:
    agent = await storage.get_agent(user.user_id, aid)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    thread = await storage.get_thread(user.user_id, cid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationCompat.from_thread_with_messages(thread) if thread else None


@router.post(
    "/{aid}/conversations",
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
    storage: StorageDependency,
    aid: str,
    body: Annotated[CreateChatRequest, Body()],
) -> ConversationCompat:
    agent = await storage.get_agent(user.user_id, aid)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    new_thread = Thread(
        user_id=user.user_id,
        thread_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        name=body.name,
        agent_id=agent.agent_id,
        messages=[],
        metadata={},
    )
    await storage.upsert_thread(user.user_id, thread=new_thread)
    return ConversationCompat.from_thread(new_thread)


@router.post(
    "/{aid}/conversations/{cid}/messages",
    summary="Post a message (synchronous)",
    description=(
        "Post a message to a conversation thread, and get the updated conversation state."
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
    storage: StorageDependency,
    aid: str,
    cid: str,
    body: Annotated[ChatMessageRequest, Body()],
) -> ConversationCompat | None:
    raise NotImplementedError("Not implemented")


@router.post(
    "/{aid}/conversations/{cid}/stream",
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
    "/{aid}/conversations/{cid}/messages/detailed",
    summary="Post messages (synchronous)",
    description=("Post messages to a conversation thread, and get the updated conversation state."),
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
    "/{aid}/conversations/{cid}/stream/detailed",
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
    "/{aid}/conversations/{cid}",
    summary="Delete conversation",
    description=("Deletes the conversation with the given conversation ID for the given agent."),
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
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    aid: str,
    cid: str,
) -> ConversationCompat:
    thread = await storage.get_thread(user.user_id, cid)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation not found")

    files = await storage.get_thread_files(thread_id=cid, user_id=user.user_id)
    for file in files:
        await file_manager.delete(
            user_id=user.user_id, thread_id=thread.thread_id, file_id=file.file_id
        )

    await storage.delete_thread(user.user_id, cid)
    return ConversationCompat.from_thread(thread)
