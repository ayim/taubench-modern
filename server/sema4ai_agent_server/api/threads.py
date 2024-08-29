from typing import Annotated, Any, Dict, List, Optional, Sequence, Union
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Path, UploadFile
from langchain.schema.messages import AnyMessage
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from sema4ai_agent_server.api.files import _add_uploaded_messages, _store_files
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.file_manager.option import get_file_manager
from sema4ai_agent_server.schema import Thread, UploadedFile
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)

router = APIRouter()

ThreadID = Annotated[str, Path(description="The ID of the thread.")]


class ThreadPostRequest(BaseModel):
    """Payload for creating a thread."""

    name: str = Field(..., description="The name of the thread.")
    agent_id: str = Field(..., description="The ID of the agent to use.")
    starting_message: Optional[str] = Field(
        None, description="The starting AI message for the thread."
    )


class ThreadPutRequest(BaseModel):
    """Payload for updating a thread."""

    name: str = Field(..., description="The name of the thread.")
    agent_id: str = Field(..., description="The ID of the agent to use.")


class ThreadStatePostRequest(BaseModel):
    """Payload for adding state to a thread."""

    values: Union[Sequence[AnyMessage], Dict[str, Any]]


@router.get("/")
async def list_threads(user: AuthedUser) -> List[Thread]:
    """List all threads for the current user."""
    threads = await get_storage().list_threads(user.user_id)
    return threads


@router.get("/{tid}/state")
async def get_thread_state(
    user: AuthedUser,
    tid: ThreadID,
):
    """Get state for a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    state = await get_storage().get_thread_state(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return state


# TODO Check for usage and remove if not used
@router.post("/{tid}/state")
async def add_thread_state(
    user: AuthedUser,
    tid: ThreadID,
    payload: ThreadStatePostRequest,
):
    """Add state to a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return await get_storage().update_thread_state(user.user_id, tid, payload.values)


@router.get("/{tid}/history")
async def get_thread_history(
    user: AuthedUser,
    tid: ThreadID,
):
    """Get all past states for a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    history = await get_storage().get_thread_history(
        user_id=user.user_id, thread_id=tid
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return history


@router.get("/{tid}")
async def get_thread(
    user: AuthedUser,
    tid: ThreadID,
) -> Thread:
    """Get a thread by ID."""
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.post("")
async def create_thread(
    user: AuthedUser,
    payload: ThreadPostRequest,
) -> Thread:
    """Create a thread."""
    # Check if user has access to the agent
    agent = await get_storage().get_agent(user.user_id, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    thread = await get_storage().put_thread(
        user.user_id,
        str(uuid4()),
        agent_id=payload.agent_id,
        name=payload.name,
        metadata=None,
    )
    if payload.starting_message is not None:
        message = AIMessage(id=str(uuid4()), content=payload.starting_message)
        await get_storage().update_thread_state(
            user_id=user.user_id,
            thread_id=thread.thread_id,
            values={"messages": [message]},
        )
    return thread


@router.put("/{tid}")
async def upsert_thread(
    user: AuthedUser,
    tid: ThreadID,
    payload: ThreadPutRequest,
) -> Thread:
    """Update a thread."""
    # Check if user has access to the agent
    agent = await get_storage().get_agent(user.user_id, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return await get_storage().put_thread(
        user.user_id,
        tid,
        agent_id=payload.agent_id,
        name=payload.name,
        metadata=thread.metadata,
    )


@router.delete("/{tid}")
async def delete_thread(
    user: AuthedUser,
    tid: ThreadID,
):
    """Delete a thread by ID."""
    await get_storage().delete_thread(user.user_id, tid)
    return {"status": "ok"}


@router.get("/{tid}/files")
async def get_thread_files(
    user: AuthedUser,
    tid: ThreadID,
) -> List[UploadedFile]:
    """Get a list of files associated with a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return await get_storage().get_thread_files(tid)


@router.post("/{tid}/files")
async def upload_thread_files(
    files: list[UploadFile],
    user: AuthedUser,
    tid: ThreadID,
) -> List[UploadedFile]:
    """Upload files to the given agent."""

    thread = await get_storage().get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = await get_storage().get_agent(user.user_id, thread.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    file_manager = get_file_manager(agent.model)
    try:
        stored_files = await _store_files(thread, files, file_manager)
    except Exception as e:
        logger.exception("Failed to store a file", exception=e)
        raise HTTPException(status_code=500, detail=f"Failed to store a file: {str(e)}")

    await _add_uploaded_messages(stored_files, tid, user)

    return stored_files
