import uuid
from typing import Any, Dict, Optional, Sequence, Union

import langsmith.client
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.exceptions import RequestValidationError
from langchain.pydantic_v1 import ValidationError
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langserve.server import _unpack_input
from langsmith.utils import tracing_is_enabled
from orjson import orjson
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from sema4ai_agent_server.agent import runnable_agent
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.langsmith_client import (
    get_langsmith_thread_url,
    save_langsmith_thread_url,
)
from sema4ai_agent_server.schema import StreamRequest
from sema4ai_agent_server.storage.option import get_storage
from sema4ai_agent_server.stream import astream_state, invoke_state, to_sse

router = APIRouter()
langsmith_client = langsmith.client.Client() if tracing_is_enabled() else None


async def _run_input_and_config(payload: StreamRequest, user_id: str):
    thread = await get_storage().get_thread(user_id, payload.thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = await get_storage().get_agent(user_id, str(thread.agent_id))
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

    config: RunnableConfig = {
        "configurable": {
            "user_id": user_id,
            "thread_id": thread.thread_id,
            "agent_id": agent.id,
            "name": agent.name,
            "runbook": agent.runbook,
            "knowledge_files": knowledge_files,
            "model": agent.model,
            "type": agent.architecture,
            "reasoning_level": agent.reasoning,
            "action_packages": agent.action_packages,
            "use_retrieval": use_retrieval,
        },
    }

    input_ = {"messages": payload.get_langchain_messages()}
    return input_, config, thread, agent


async def background_invoke(input_, config):
    await runnable_agent.ainvoke(input_, config)
    run_id = input_["run_id"]
    await get_storage().update_async_run(run_id, "complete")


@router.post("/async_invoke")
async def create_run(
    payload: StreamRequest,
    user: AuthedUser,
    background_tasks: BackgroundTasks,
):
    """Create a run."""
    input_, config, _, _ = await _run_input_and_config(payload, user.user_id)
    run_id = str(uuid.uuid4())
    input_["run_id"] = run_id
    await get_storage().create_async_run(run_id, "in_progress")
    background_tasks.add_task(background_invoke, input_, config)
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


@router.post("/stream")
async def stream_run(
    payload: StreamRequest,
    user: AuthedUser,
) -> EventSourceResponse:
    """Create a run."""
    input_, config, thread, _ = await _run_input_and_config(payload, user.user_id)
    if langsmith_client:
        if url := get_langsmith_thread_url(langsmith_client, thread.thread_id):
            await save_langsmith_thread_url(thread, url)
    return EventSourceResponse(to_sse(astream_state(runnable_agent, input_, config)))


@router.post("/invoke")
async def invoke_run(
    payload: StreamRequest,
    user: AuthedUser,
):
    """Create a run."""
    input_, config, thread, _ = await _run_input_and_config(payload, user.user_id)
    if langsmith_client:
        if url := get_langsmith_thread_url(langsmith_client, thread.thread_id):
            await save_langsmith_thread_url(thread, url)
    return await invoke_state(runnable_agent, input_, config)
