# Standard library imports
import json
import logging
from asyncio import CancelledError, create_task
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.params import Body
from sse_starlette import EventSourceResponse

from agent_platform.core.context import AgentServerContext
from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload
from agent_platform.core.runs.run import Run
from agent_platform.core.streaming.delta import (
    StreamingDeltaAgentFinished,
    StreamingDeltaAgentReady,
)
from agent_platform.core.thread import Thread
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.server.agent_architectures.arch_manager import AgentArchManager
from agent_platform.server.api.dependencies import FileManagerDependency, StorageDependency
from agent_platform.server.api.private_v2.runs import sync_run
from agent_platform.server.api.public_v2.interface import (
    AgentCompat,
    ChatMessageRequest,
    Conversation,
    CreateChatRequest,
    PaginatedResponse,
)
from agent_platform.server.auth.handlers import AuthedUser
from agent_platform.server.kernel.kernel import AgentServerKernel

logger = logging.getLogger(__name__)

router = APIRouter()


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
    response_model=AgentCompat,
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
    # the agent connector does not call this endpoint but it filters agent by name from the list
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
    data = [Conversation.from_thread(thread) for thread in threads[:limit]]
    return PaginatedResponse(next=None, has_more=False, data=data)


@router.get(
    "/{aid}/conversations/{cid}/messages",
    summary="Get conversation messages",
    description=("Returns the conversation messages of the given chat_id for the given agent."),
    response_description="Conversation",
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
) -> PaginatedResponse:
    agent = await storage.get_agent(user.user_id, aid)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    thread = await storage.get_thread(user.user_id, cid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return PaginatedResponse(next=None, has_more=False, data=thread.messages)


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
) -> Conversation:
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
    return Conversation.from_thread(new_thread)


# ruff: noqa: PLR0913
@router.post(
    "/{aid}/conversations/{cid}/messages",
    summary="Post a message (synchronous)",
    description=(
        "Post a message to a conversation thread, and get the updated conversation state."
    ),
    response_description="Conversation with messages",
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
    request: Request,
) -> PaginatedResponse:
    agent = await storage.get_agent(agent_id=aid, user_id=user.user_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    thread = await storage.get_thread(user_id=user.user_id, thread_id=cid)
    message = ThreadMessage(
        message_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        role="user",
        content=[ThreadTextContent(text=body.content)],
    )
    initial_payload = InitiateStreamPayload(
        thread_id=thread.thread_id, agent_id=agent.agent_id, messages=[message]
    )
    await sync_run(
        agent_id=agent.agent_id,
        initial_payload=initial_payload,
        request=request,
        storage=storage,
        user=user,
    )

    # refetch the thread to get the list of new messages
    thread = await storage.get_thread(user_id=user.user_id, thread_id=cid)

    return PaginatedResponse(next=None, has_more=False, data=thread.messages)


# ruff: noqa: PLR0913
@router.post(
    "/{aid}/conversations/{cid}/stream",
    summary="Post a message to a conversation and stream the response",
    description="Post a message to a conversation and stream the response",
    response_description="SSE Stream of messages",
    tags=["conversations"],
    responses={
        200: {"description": "SSE stream of Delta messages", "content": {"text/event-stream": {}}},
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def post_public_api_messages_simple(
    user: AuthedUser,
    storage: StorageDependency,
    aid: str,
    cid: str,
    body: Annotated[ChatMessageRequest, Body()],
    request: Request,
) -> EventSourceResponse:
    agent = await storage.get_agent(agent_id=aid, user_id=user.user_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    thread = await storage.get_thread(user_id=user.user_id, thread_id=cid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread_message = ThreadMessage(
        message_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        role="user",
        content=[ThreadTextContent(text=body.content)],
    )
    await storage.add_message_to_thread(
        user_id=user.user_id, thread_id=thread.thread_id, message=thread_message
    )

    active_run = Run(
        run_id=str(uuid4()),
        agent_id=aid,
        thread_id=cid,
        status="running",
        run_type="stream",
    )
    await storage.create_run(active_run)

    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    runner = await agent_arch_manager.get_runner(
        agent.agent_architecture.name,
        agent.agent_architecture.version,
        thread.thread_id,
    )

    await runner.start()

    server_context = AgentServerContext.from_request(
        request=request,
        user=user,
        version="2.0.0",
    )
    kernel = AgentServerKernel(server_context, thread, agent, active_run)
    await runner.invoke(kernel)

    ca_invoke_task = create_task(runner.invoke(kernel))

    async def event_generator():
        try:
            ready_event = StreamingDeltaAgentReady(
                run_id=active_run.run_id,
                thread_id=thread.thread_id,
                agent_id=agent.agent_id,
                timestamp=datetime.now(UTC),
            )
            yield {"event": "agent_ready", "data": json.dumps(ready_event.model_dump())}

            async for event in runner.get_event_stream():
                try:
                    yield {"event": "agent_event", "data": json.dumps(event.model_dump())}
                    if isinstance(event, StreamingDeltaAgentFinished):
                        break
                except RuntimeError:
                    break
        except CancelledError:
            logger.info("SSE stream cancelled (likely client disconnected)")
        finally:
            ca_invoke_task.cancel()

    return EventSourceResponse(event_generator())


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
) -> Conversation:
    agent = await storage.get_agent(agent_id=aid, user_id=user.user_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    thread = await storage.get_thread(user.user_id, cid)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation not found")

    files = await storage.get_thread_files(thread_id=cid, user_id=user.user_id)
    for file in files:
        await file_manager.delete(
            user_id=user.user_id, thread_id=thread.thread_id, file_id=file.file_id
        )

    await storage.delete_thread(user.user_id, cid)
    return Conversation.from_thread(thread)
