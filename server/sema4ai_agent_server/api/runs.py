import uuid
from typing import Optional

from agent_server_types import Agent, ChatRequest, Thread
from fastapi import APIRouter, BackgroundTasks, HTTPException
from opentelemetry import metrics
from sse_starlette import EventSourceResponse

from sema4ai_agent_server.agent import runnable_agent
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.langsmith_client import (
    Langsmith,
    get_langsmith,
    save_langsmith_thread_url,
    trace,
)
from sema4ai_agent_server.otel import otel_is_enabled
from sema4ai_agent_server.schema import (
    AgentServerRunnableConfig,
    AgentServerRunnableConfigurable,
    AgentStreamEvent,
    User,
)
from sema4ai_agent_server.storage.option import get_storage
from sema4ai_agent_server.stream import astream_state, invoke_state, to_sse
from sema4ai_agent_server.utils import convert_chat_to_langchain

router = APIRouter()

if otel_is_enabled():
    meter = metrics.get_meter(__name__)
    run_counter = meter.create_counter(
        name="sema4ai.agent_server.runs",
        description="Number of runs created",
    )


def _run_counter_attrs(
    user: AuthedUser, thread: Thread, agent: Agent, type: str
) -> dict:
    return {
        "agent_id": agent.id,
        "thread_id": thread.thread_id,
        "llm.provider": agent.model.provider,
        "llm.model": getattr(agent.model, "name", ""),
        # NoneType fails to be encoded so we use "None" instead
        "user_id": user.cr_user_id if user.cr_user_id else "None",
        "system_id": user.cr_system_id if user.cr_system_id else "None",
        "type": type,
    }


async def _run_input_and_config(payload: ChatRequest, user: User):
    thread = await get_storage().get_thread(user.user_id, payload.thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = await get_storage().get_agent(user.user_id, str(thread.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    knowledge_files = None
    if agent:
        uploaded_files = await get_storage().get_agent_files(agent.id)
        knowledge_files = [file.file_ref for file in uploaded_files]

    thread_files = await get_storage().get_thread_files(thread.thread_id)
    use_retrieval = (knowledge_files is not None and len(knowledge_files) > 0) or len(
        thread_files
    ) > 0

    config = AgentServerRunnableConfig(
        configurable=AgentServerRunnableConfigurable(
            agent=agent,  # TODO: Need to handle secret strings deeper in the stack from here
            thread=thread,
            use_retrieval=use_retrieval,
            interrupt_before_action=False,  # TODO: Where does this come from?
            knowledge_files=knowledge_files,
        ),
    )

    input_ = {"messages": convert_chat_to_langchain(payload)}
    return input_, config, thread, agent


async def background_invoke(input_, config, ls: Optional[Langsmith] = None):
    with trace(ls):
        await runnable_agent.ainvoke(input_, config)
    run_id = input_["run_id"]
    await get_storage().update_async_run(run_id, "complete")


@router.post("/async_invoke")
async def create_run(
    payload: ChatRequest,
    user: AuthedUser,
    background_tasks: BackgroundTasks,
):
    """Create a run."""
    input_, config, thread, agent = await _run_input_and_config(payload, user)
    run_id = str(uuid.uuid4())
    input_["run_id"] = run_id
    await get_storage().create_async_run(run_id, "in_progress")
    if ls := get_langsmith(agent):
        await save_langsmith_thread_url(ls, thread)
    background_tasks.add_task(background_invoke, input_, config, ls)
    if otel_is_enabled():
        run_counter.add(1, _run_counter_attrs(user, thread, agent, "async_invoke"))
    return {
        "status": "in_progress",
        "run_id": run_id,
    }


@router.get("/{rid}/status")
async def get_run_status(rid: str):
    status = await get_storage().get_async_run_status(rid)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": rid, "status": status}


@router.post(
    "/stream",
    response_model=AgentStreamEvent,
    response_class=EventSourceResponse,
    responses={
        200: {
            "description": "A stream of Server-Sent Events containing AgentStreamEvents.",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "oneOf": [
                            {
                                "$ref": "#/components/schemas/StreamMetadataEvent",
                            },
                            {
                                "$ref": "#/components/schemas/StreamDataEvent",
                            },
                            {
                                "$ref": "#/components/schemas/StreamErrorEvent",
                            },
                            {
                                "$ref": "#/components/schemas/StreamEndEvent",
                            },
                        ],
                        "discriminator": {
                            "propertyName": "event",
                            "mapping": {
                                "metadata": "#/components/schemas/StreamMetadataEvent",
                                "data": "#/components/schemas/StreamDataEvent",
                                "error": "#/components/schemas/StreamErrorEvent",
                                "end": "#/components/schemas/StreamEndEvent",
                            },
                        },
                    },
                }
            },
        },
    },
)
async def stream_run(
    payload: ChatRequest,
    user: AuthedUser,
):
    """Create a run."""
    # TODO: Performance gains may be possible as part of implementing stream protocol v2.
    #       We should consider using StreamingResponse based on performance tests.
    input_, config, thread, agent = await _run_input_and_config(payload, user)
    if ls := get_langsmith(agent):
        await save_langsmith_thread_url(ls, thread)
    if otel_is_enabled():
        run_counter.add(1, _run_counter_attrs(user, thread, agent, "stream"))
    return EventSourceResponse(
        to_sse(astream_state(runnable_agent, input_, config, ls))
    )


@router.post("/invoke")
async def invoke_run(
    payload: ChatRequest,
    user: AuthedUser,
):
    """Create a run."""
    input_, config, thread, agent = await _run_input_and_config(payload, user)
    if ls := get_langsmith(agent):
        await save_langsmith_thread_url(ls, thread)
    if otel_is_enabled():
        run_counter.add(1, _run_counter_attrs(user, thread, agent, "invoke"))
    return await invoke_state(runnable_agent, input_, config, ls)
