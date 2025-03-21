import datetime
import json
import uuid
from enum import Enum
from typing import Optional, List, AsyncIterator, Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.params import Body
from pydantic import BaseModel, TypeAdapter, Field

from agent_server_types.agents import (
    Agent as ASAgent,
    ActionPackage as ASActionPackage,
)

from agent_server_types import (
    Thread as ASThread, StrWithUuidInput, ChatRequest, ChatMessage,
)
from sse_starlette import EventSourceResponse
from sse_starlette.event import ServerSentEvent

from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.responses import TypeAdapterResponse
from sema4ai_agent_server.schema import StreamEndEvent, StreamDataEvent
from sema4ai_agent_server.storage.option import get_storage
from sema4ai_agent_server.api.runs import _run_input_and_config, invoke_state
from sema4ai_agent_server.agent import runnable_agent
from sema4ai_agent_server.file_manager.option import get_file_manager

from sema4ai_agent_server.stream import MessagesStream, _chunk_to_event, _error_to_event, astream_state, invoke_state



router = APIRouter()


class Mode(str, Enum):
    CONVERSATIONAL = 'conversational'
    WORKER = 'worker'


class Architecture(str, Enum):
    AGENT = 'agent'
    PLAN_EXECUTE = 'plan_execute'


class Provider(str, Enum):
    OPENAI = 'OpenAI'
    AZURE = 'Azure'
    AMAZON = 'Amazon'


class ActionPackage(BaseModel):
    name: str
    organization: str
    version: str
    actions: str

    @classmethod
    def from_action_package(cls, ap: ASActionPackage) -> 'ActionPackage':
        return cls(
            name=ap.name,
            organization=ap.organization,
            version=ap.version,
            actions=ap.whitelist,
        )


class LanguageModel(BaseModel):
    provider: Provider
    model: str


class Agent(BaseModel):
    id: str
    name: str
    description: str
    llm: LanguageModel
    architecture: Architecture
    mode: Mode


    @classmethod
    def from_agent(cls, agent: ASAgent) -> 'Agent':
        arch_str = agent.advanced_config.architecture
        if arch_str.endswith('plan_execute'):
            architecture = Architecture.PLAN_EXECUTE
        else:
            architecture = Architecture.AGENT
        return cls(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            llm=LanguageModel(provider=agent.model.provider, model=agent.model.name),
            architecture=architecture,
            mode=agent.metadata.mode,
        )


class Role(str, Enum):
    AGENT = 'agent'
    HUMAN = 'human'

class MessageType(str, Enum):
    MESSAGE = "message"
    TOKEN = "token"
    TOOL_REQUEST = "tool_request"
    TOOL_RESPONSE = "tool_response"
    START_STREAM = "start_stream"
    END_STREAM = "end_stream"


class Message(BaseModel):
    id: Optional[str]
    type: MessageType
    channel: Annotated[str, Field(default="chat")]
    role: Role
    content: str

class TokenMessage(BaseModel):
    id: Optional[str]
    type: MessageType
    channel: Annotated[str, Field(default="chat")]
    role: Role
    token: str
    token_sequence: int

class ToolCall(BaseModel):
    id: str
    name: str
    args: dict

class ToolRequest(Message):
    tool_calls: list[ToolCall]

class ToolResponse(Message):
    tool_call_id: str
    status: str
    result: dict # parsed JSON from `content`

class CreateChatRequest(BaseModel):
    name: str

class ChatMessageRequest(BaseModel):
    content: str

def translate_message(message: dict) -> Message | ToolRequest | ToolResponse:
    # tool request
    empty_content = message.content == ""
    # additional_kwargs = message.additional_kwargs 
    # tool_calls = message.
    type = message.type
    role = message.type if message.type == "human" else "agent"

    if type == "ai" and empty_content and len(message.tool_calls) > 0: # tool request
        return ToolRequest(
            id=message.id,
            type=MessageType.TOOL_REQUEST,
            role=role,
            content=message.content,
            tool_calls=[ToolCall(**tc) for tc in message.tool_calls],
        )
    elif type == "tool" and not empty_content: # tool response
        try:
            result_content = json.loads(message.content) if isinstance(message.content, str) else message.content
            if not isinstance(result_content, dict):
                result_content = {}
        except json.JSONDecodeError:
            result_content = {}

        return ToolResponse(
            id=message.id,
            type=MessageType.TOOL_RESPONSE,
            role=role,
            tool_call_id=message.tool_call_id,
            status=message.status,
            result=result_content,
            content="",
        )
    else:
        return Message(
            id=message.id,
            type=MessageType.MESSAGE,
            role=role,
            content=message.content,
        )


class Conversation(BaseModel):
    id: Optional[StrWithUuidInput]
    name: str
    agent_id: StrWithUuidInput

    @classmethod
    def from_thread(cls, thread: ASThread) -> 'Conversation':
        return cls(
            id=thread.thread_id,
            name=thread.name,
            agent_id=thread.agent_id,
        )


class ConversationState(Conversation):
    messages: Optional[list[Message | ToolRequest | ToolResponse]]

    @classmethod
    def from_thread_with_messages(cls, thread: ASThread, state: dict) -> 'ConversationState':
        if "messages" in state['values']:
            messages = [translate_message(message) for message in state['values']['messages'] if message is not None]
        else:
            messages = []

        return cls(
            id=thread.thread_id,
            name=thread.name,
            agent_id=thread.agent_id,
            messages=messages,
        )


class WorkItem(BaseModel):
    id: str
    name: str


@router.get(
    "/agents",
    summary="List agents",
    description="Returns a list of all agents for the authenticated user. You can filter by name using the 'name' query parameter.",
    response_description="List of agents",
    response_model=list[Agent],
    response_class=TypeAdapterResponse,
    tags=["agents"],
    responses={
        200: {"description": "Success"},
        500: {"description": "Internal Server Error"},
    },
)
async def get_agents(user: AuthedUser, name: str | None = Query(None, description="Filter agents by name (starts with, case insensitive).")):
    as_agents = await get_storage().list_agents(user.user_id)
    if name:
        as_agents = [agent for agent in as_agents if agent.name.lower().startswith(name.lower())]
    agents = [Agent.from_agent(as_agent) for as_agent in as_agents]
    return TypeAdapterResponse(agents, adapter=TypeAdapter(List[Agent]))
    # return []

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
async def get_agent_by_name(user: AuthedUser, aid: str) -> Agent:
    as_agent = await get_storage().get_agent(user.user_id, aid)
    if as_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return Agent.from_agent(as_agent)


@router.get(
    "/agents/{aid}/conversations",
    summary="List conversations",
    description="Returns a list of all conversations for the given agent.",
    response_description="List of conversations",
    response_model=list[Conversation],
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request"},
        500: {"description": "Internal Server Error"},
    },
)
async def get_conversations(user: AuthedUser, aid: str) -> list[Conversation]:
    threads = await get_storage().list_agent_threads(aid)
    return [Conversation.from_thread(thread) for thread in threads]


@router.get(
    "/agents/{aid}/conversations/{cid}/messages",
    summary="Get conversation messages",
    description="Returns the conversation messages of the given chat_id for the given agent.",
    response_description="Conversation",
    response_model=ConversationState,
    tags=["conversations"],
    responses={
        200: {"description": "Success"},
        404: {"description": "Agent/Conversation not found"},
        500: {"description": "Internal Server Error"},
    },

)
async def get_chat_messages(user: AuthedUser, aid: str, cid: str) -> ConversationState:
    agent = await get_storage().get_agent(user.user_id, aid)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    state = await get_storage().get_thread_state(cid)
    thread = await get_storage().get_thread(user.user_id, cid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationState.from_thread_with_messages(thread, state) if thread else None

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
async def create_chat(user: AuthedUser, aid: str, body: CreateChatRequest = Body(...)) -> Conversation:
    agent = await get_storage().get_agent(user.user_id, aid)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    thread = await get_storage().put_thread(
        user.user_id,
        str(uuid.uuid4()),
        agent_id=aid,
        name=body.name,
        metadata=None,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    return Conversation.from_thread(thread)


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def to_public_api_sse(messages_stream: MessagesStream) -> AsyncIterator[dict]:
    try:
        # token tracking
        last_len = 0 # last length of the message content
        sequence = 0 # token sequence number
        async for chunk in messages_stream:
            out_event = _chunk_to_event(chunk)
            if isinstance(out_event.data, list) and len(out_event.data) == 1:
                message = out_event.data[0]

                # Tool Call Response
                if ("finish_reason" in message.response_metadata
                        and message.response_metadata["finish_reason"] == "tool_calls"):
                    tr = ToolRequest(
                        id=message.id,
                        type="tool_request",
                        role="agent",
                        content=message.content,
                        tool_calls=[ToolCall(**tc) for tc in message.tool_calls],
                    )
                    yield ServerSentEvent(data=json.dumps(tr.model_dump()), event="data")
                # use the tool_event message to look for tool call responses
                if message.type == "tool_event":
                    last_len = 0
                    # Tool Call Response
                    if message.output is not None:
                        tr =  ToolResponse(
                            id=message.id,
                            type="tool_response",
                            role="agent",
                            tool_call_id=message.tool_call_id,
                            status="success",
                            result=json.loads(message.output),
                            content="",
                        )
                        yield ServerSentEvent(data=json.dumps(tr.model_dump()), event="data")
                ## Start of Stream
                elif message.content == "" and not "tool_calls" in message.additional_kwargs: # empty content
                    msg = Message(
                        id=message.id,
                        type="start_stream",
                        role=_translate_role(message.type),
                        content="",
                    )
                    yield ServerSentEvent(data=json.dumps(msg.model_dump()), event="data")
                # Stream Message
                elif message.content != "": # regular streaming message
                    msg_txt = message.content[last_len:]
                    if last_len == len(message.content): # end of stream
                        end_msg = Message(
                            id=message.id,
                            type="end_stream",
                            role=_translate_role(message.type),
                            content="",
                        )
                        msg = Message(
                            id=message.id,
                            type="message",
                            role=_translate_role(message.type),
                            content=message.content,
                        )
                        yield ServerSentEvent(data=json.dumps(end_msg.model_dump()), event="data")
                        yield ServerSentEvent(data=json.dumps(msg.model_dump()), event="data")
                    if msg_txt != "":
                        last_len = len(message.content)
                        msg = TokenMessage(
                            id=message.id,
                            type=MessageType.TOKEN,
                            role=_translate_role(message.type),
                            token=msg_txt,
                            token_sequence=sequence,
                        )
                        sequence += 1
                        yield ServerSentEvent(data=json.dumps(msg.model_dump()), event="data")
    except Exception as e:
        logger.warn("error in stream", exc_info=True)
        out_event = _error_to_event(e)
        yield out_event.to_sse()

    # Send an end event to signal the end of the stream
    yield StreamEndEvent().to_sse()

@router.post(
    "/agents/{aid}/conversations/{cid}/messages",
    summary="Post avmessage (synchronous)",
    description="Post a message to a conversation thread, and get the updated conversation state.",
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
async def post_messages_simple(user: AuthedUser, aid: str, cid: str, body: ChatMessageRequest = Body(...)) -> ConversationState:
    msg_id = str(uuid.uuid4())
    payload = ChatRequest(
        thread_id=cid,
        input=[ChatMessage(
            id=msg_id,
            type=Role.HUMAN,
            content=body.content,
        )],
    )
    input_, config, thread, agent = await _run_input_and_config(payload, user)
    await invoke_state(runnable_agent, input_, config, None)
    state = await get_storage().get_thread_state(payload.thread_id)
    return ConversationState.from_thread_with_messages(thread, state) if thread else None


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
async def post_public_api_messages_simple(user: AuthedUser, aid: str, cid: str, body: ChatMessageRequest = Body(...)) -> EventSourceResponse:
    chat_messages = [ChatMessage(type=Role.HUMAN, content=body.content)]
    payload = ChatRequest(input=chat_messages, thread_id=cid)
    input_, config, thread, agent = await _run_input_and_config(payload, user)
    return EventSourceResponse(
        to_public_api_sse(astream_state(runnable_agent, input_, config, None))
    )


@router.post(
    "/agents/{aid}/conversations/{cid}/messages/detailed",
    summary="Post messages (synchronous)",
    description="Post messages to a conversation thread, and get the updated conversation state.",
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
async def post_messages_detailed(user: AuthedUser, aid: str, cid: str, messages: List[Message]) -> ConversationState:
    payload = ChatRequest(
        thread_id=cid,
        input=[ChatMessage(
            id=message.id,
            type=message.type,
            content=message.content,
        ) for message in messages],
    )
    input_, config, thread, agent = await _run_input_and_config(payload, user)
    await invoke_state(runnable_agent, input_, config, None)
    state = await get_storage().get_thread_state(payload.thread_id)
    return ConversationState.from_thread_with_messages(thread, state) if thread else None

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
async def post_public_api_messages_detailed(user: AuthedUser, aid: str, cid: str, messages: list[Message]) -> EventSourceResponse:
    chat_messages = [ChatMessage(type=_translate_role(message.role), content=message.content) for message in messages]
    payload = ChatRequest(input=chat_messages, thread_id=cid)
    input_, config, thread, agent = await _run_input_and_config(payload, user)
    return EventSourceResponse(
        to_public_api_sse(astream_state(runnable_agent, input_, config, None))
    )


def _translate_role(role: str) -> Role:
    if role == "agent":
        return "ai"
    elif role == "ai":
        return "agent"
    else:
        return "human"


@router.delete(
    "/agents/{aid}/conversations/{cid}",
    summary="Delete conversation",
    description="Deletes the conversation with the given conversation ID for the given agent.",
    response_description="Conversation",
    response_model=Conversation,
    tags=["conversations"],
    responses={
            200: {"description": "Success"},
            404: {"description": "Conversation not found"},
            500: {"description": "Internal Server Error"},
        },
)
async def delete_chat(user: AuthedUser, aid: str, cid: str):
    thread = await get_storage().get_thread(user.user_id, cid)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation not found")

    file_manager = get_file_manager()
    files = await get_storage().get_thread_files(cid)
    for file in files:
        await file_manager.delete(file.file_id)

    await get_storage().delete_thread(user.user_id, cid)
    return Conversation.from_thread(thread)


# TODO: Revisit work item agent-thread-workitem relationship and adjust paths accordingly
# for now work items are on hold until we have a better understanding of the relationship
# @router.get(
#     "/agents/{aid}/conversations/{cid}/workitems",
#     summary="List workitems",
#     description="Returns a list of all workitems for the given chat.",
#     response_description="List of workitems",
#     response_model=list[WorkItem],
#     tags=["work items"],
# )
# async def get_workitems(aid: str, cid: str) -> list[WorkItem]:
#     pass
#
# @router.get(
#     "/agents/{aid}/conversations/{cid}/workitems/{workitem_id}",
#     summary="Get workitem",
#     description="Returns the workitem with the given workitem_id for the given chat.",
#     response_description="Workitem",
#     response_model=WorkItem,
#     tags=["work items"],
# )
# async def get_workitem(aid: str, cid: str, workitem_id: str) -> WorkItem:
#     return WorkItem(id=workitem_id, name="name")
#
# @router.post(
#     "/agents/{aid}/conversations/{cid}/workitems",
#     summary="Create new workitem",
#     description="Creates a new workitem for the given chat.",
#     response_description="Workitem",
#     response_model=WorkItem,
#     tags=["work items"],
# )
# async def create_workitem(aid: str, cid: str, Workitem) -> WorkItem:
#     pass
#
#
# @router.put(
#     "/agents/{aid}/conversations/{cid}/workitems/{wid}",
#     summary="Update workitem",
#     description="Updates the workitem with the given workitem_id for the given chat.",
#     response_description="Workitem",
#     response_model=WorkItem,
#     tags=["work items"],
# )
# async def update_workitem(aid: str, cid: str, wid: str, Workitem) -> WorkItem:
#     pass
#
#
# @router.delete(
#     "/agents/{aid}/conversations/{cid}/workitems/{wid}",
#     summary="Delete workitem",
#     description="Deletes the workitem with the given workitem_id for the given chat.",
#     response_description="Workitem",
#     response_model=WorkItem,
#     tags=["work items"],
# )
# async def delete_workitem(aid: str, cid: str, wid: str):
#     pass
