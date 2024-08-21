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
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from sema4ai_agent_server.agent import runnable_agent
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.langsmith_client import (
    get_langsmith_thread_url,
    save_langsmith_thread_url,
)
from sema4ai_agent_server.storage.option import get_storage
from sema4ai_agent_server.stream import astream_state, invoke_state, to_sse
from sema4ai_agent_server.tools import AvailableTools

router = APIRouter()
langsmith_client = langsmith.client.Client() if tracing_is_enabled() else None


class CreateRunPayload(BaseModel):
    """Payload for creating a run."""

    thread_id: str
    input: Optional[Union[Sequence[AnyMessage], Dict[str, Any]]] = Field(
        default_factory=dict
    )
    config: Optional[RunnableConfig] = None


async def _run_input_and_config(payload: CreateRunPayload, user_id: str):
    thread = await get_storage().get_thread(user_id, payload.thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = await get_storage().get_agent(user_id, str(thread.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    knowledge_files = (None,)
    if agent:
        uploaded_files = await get_storage().get_agent_files(agent.id)
        knowledge_files = [file.file_ref for file in uploaded_files]

    config: RunnableConfig = {
        **agent.config,
        "configurable": {
            **agent.config["configurable"],
            **((payload.config or {}).get("configurable") or {}),
            "user_id": user_id,
            "thread_id": thread.thread_id,
            "agent_id": agent.id,
            "name": agent.name,
            "knowledge_files": knowledge_files,
            "model": agent.model,
        },
    }

    thread_files = await get_storage().get_thread_files(thread.thread_id)

    # Add retriever tool if there are any files (knowledge or thread) and it's not already present
    if knowledge_files or thread_files:
        tools = config["configurable"].get("tools", [])
        if not any(tool.get("type") == AvailableTools.RETRIEVAL for tool in tools):
            tools.append(
                {
                    "type": AvailableTools.RETRIEVAL.value,
                    "name": "Retrieval",
                    "description": "Look up information in uploaded files.",
                    "config": {
                        "name": "Retrieval",
                    },
                }
            )
        config["configurable"]["tools"] = tools

    try:
        input_ = (
            _unpack_input(
                runnable_agent.get_input_schema(config).validate(payload.input)
            )
            if payload.input is not None
            else None
        )
        input_ = {"messages": input_ or []}
    except ValidationError as e:
        raise RequestValidationError(e.errors(), body=payload)

    return input_, config, thread, agent


runs = {}


async def background_invoke(input_, config):
    await runnable_agent.ainvoke(input_, config)
    run_id = input_["run_id"]
    await get_storage().update_async_run(run_id, "complete")


@router.post("/async_invoke")
async def create_run(
    payload: CreateRunPayload,
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
    payload: CreateRunPayload,
    user: AuthedUser,
):
    """Create a run."""
    input_, config, thread, _ = await _run_input_and_config(payload, user.user_id)
    if langsmith_client:
        if url := get_langsmith_thread_url(langsmith_client, thread.thread_id):
            await save_langsmith_thread_url(thread, url)
    return EventSourceResponse(to_sse(astream_state(runnable_agent, input_, config)))


@router.post("/invoke")
async def invoke_run(
    payload: CreateRunPayload,
    user: AuthedUser,
):
    """Create a run."""
    input_, config, thread, _ = await _run_input_and_config(payload, user.user_id)
    if langsmith_client:
        if url := get_langsmith_thread_url(langsmith_client, thread.thread_id):
            await save_langsmith_thread_url(thread, url)
    return await invoke_state(runnable_agent, input_, config)
