from typing import Any, Dict, Optional, Sequence, Union

import langsmith.client
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.exceptions import RequestValidationError
from langchain.pydantic_v1 import ValidationError
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langserve.schema import FeedbackCreateRequest
from langserve.server import _unpack_input
from langsmith.utils import tracing_is_enabled
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from sema4ai_agent_server.agent import agent
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.langsmith_client import (
    get_langsmith_thread_url,
    save_langsmith_thread_url,
)
from sema4ai_agent_server.storage.option import get_storage
from sema4ai_agent_server.stream import astream_state, invoke_state, to_sse

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

    assistant = await get_storage().get_assistant(user_id, str(thread["assistant_id"]))
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")

    knowledge_files = (None,)
    if assistant:
        uploaded_files = await get_storage().get_assistant_files(
            assistant["assistant_id"]
        )
        knowledge_files = [file["file_ref"] for file in uploaded_files]

    config: RunnableConfig = {
        **assistant["config"],
        "configurable": {
            **assistant["config"]["configurable"],
            **((payload.config or {}).get("configurable") or {}),
            "user_id": user_id,
            "thread_id": str(thread["thread_id"]),
            "assistant_id": str(assistant["assistant_id"]),
            "name": assistant["name"],
            "knowledge_files": knowledge_files,
        },
    }

    try:
        input_ = (
            _unpack_input(agent.get_input_schema(config).validate(payload.input))
            if payload.input is not None
            else None
        )
        input_ = {"messages": input_ or []}
    except ValidationError as e:
        raise RequestValidationError(e.errors(), body=payload)

    return input_, config, thread, assistant


@router.post("")
async def create_run(
    payload: CreateRunPayload,
    user: AuthedUser,
    background_tasks: BackgroundTasks,
):
    """Create a run."""
    input_, config, _, _ = await _run_input_and_config(payload, user.user_id)
    background_tasks.add_task(agent.ainvoke, input_, config)
    return {"status": "ok"}  # TODO add a run id


@router.post("/stream")
async def stream_run(
    payload: CreateRunPayload,
    user: AuthedUser,
):
    """Create a run."""
    input_, config, thread, _ = await _run_input_and_config(payload, user.user_id)
    if langsmith_client:
        if url := get_langsmith_thread_url(langsmith_client, thread["thread_id"]):
            await save_langsmith_thread_url(thread, url)
    return EventSourceResponse(to_sse(astream_state(agent, input_, config)))


@router.post("/invoke")
async def invoke_run(
    payload: CreateRunPayload,
    user: AuthedUser,
):
    """Create a run."""
    input_, config, thread, _ = await _run_input_and_config(payload, user.user_id)
    if langsmith_client:
        if url := get_langsmith_thread_url(langsmith_client, thread["thread_id"]):
            await save_langsmith_thread_url(thread, url)
    return await invoke_state(agent, input_, config)


@router.get("/input_schema")
async def input_schema() -> dict:
    """Return the input schema of the runnable."""
    return agent.get_input_schema().schema()


@router.get("/output_schema")
async def output_schema() -> dict:
    """Return the output schema of the runnable."""
    return agent.get_output_schema().schema()


@router.get("/config_schema")
async def config_schema() -> dict:
    """Return the config schema of the runnable."""
    return agent.config_schema().schema()


if langsmith_client:

    @router.post("/feedback")
    def create_run_feedback(feedback_create_req: FeedbackCreateRequest) -> dict:
        """
        Send feedback on an individual run to langsmith

        Note that a successful response means that feedback was successfully
        submitted. It does not guarantee that the feedback is recorded by
        langsmith. Requests may be silently rejected if they are
        unauthenticated or invalid by the server.
        """

        langsmith_client.create_feedback(
            feedback_create_req.run_id,
            feedback_create_req.key,
            score=feedback_create_req.score,
            value=feedback_create_req.value,
            comment=feedback_create_req.comment,
            source_info={
                "from_langserve": True,
            },
        )

        return {"status": "ok"}
