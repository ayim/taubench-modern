from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Sequence, Union
from uuid import uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from langchain.schema.messages import AnyMessage
from langchain_core.messages import AIMessage
from opentelemetry import metrics
from pydantic import BaseModel, Field

from sema4ai_agent_server.api.files import _add_uploaded_messages
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.file_manager.base import RemoteFileUploadData
from sema4ai_agent_server.file_manager.option import get_file_manager
from sema4ai_agent_server.otel import otel_is_enabled
from sema4ai_agent_server.schema import Thread, UploadedFile, UploadFileRequest
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)

router = APIRouter()

ThreadID = Annotated[str, Path(description="The ID of the thread.")]

if otel_is_enabled():
    meter = metrics.get_meter(__name__)
    thread_counter = meter.create_counter(
        name="sema4ai.agent_server.thread_counter",
        description="Number of threads created",
    )


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


class RequestRemoteFileUploadPayload(BaseModel):
    file_name: str


class ConfirmRemoteFileUploadPayload(BaseModel):
    file_ref: str
    file_id: str


class FileByRefResponse(BaseModel):
    # In Studio: file:///home/my-file.pdf. in ACE: https://pre-signed-get-url.com
    file_url: str

    @classmethod
    def from_file(cls, file: UploadedFile) -> "FileByRefResponse":
        if file.file_path.startswith(("http", "https")):
            file_url = file.file_path
        else:
            file_url = Path(file.file_path).as_uri()
        return cls(file_url=file_url)


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
    state = await get_storage().get_thread_state(tid)
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
    return await get_storage().update_thread_state(tid, payload.values)


@router.get("/{tid}/history")
async def get_thread_history(
    user: AuthedUser,
    tid: ThreadID,
):
    """Get all past states for a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    history = await get_storage().get_thread_history(tid)
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
            thread_id=thread.thread_id, values={"messages": [message]}
        )

    if otel_is_enabled():
        thread_counter.add(
            1,
            {
                "agentId": thread.agent_id,
                "threadId": thread.thread_id,
                # NoneType fails to be encoded so we use "None" instead
                "userId": user.cr_user_id if user.cr_user_id else "None",
                "systemId": user.cr_system_id if user.cr_system_id else "None",
            },
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
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    file_manager = get_file_manager()
    files = await get_storage().get_thread_files(tid)
    for file in files:
        await file_manager.delete(file.file_id)

    await get_storage().delete_thread(user.user_id, tid)
    return {"status": "ok"}


@router.get("/{tid}/file-by-ref")
async def get_file_by_ref(
    user: AuthedUser,
    tid: ThreadID,
    file_ref: str,
) -> FileByRefResponse:
    thread = await get_storage().get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    file = await get_storage().get_file(thread, file_ref)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    files = await get_file_manager().refresh_file_paths([file])
    return FileByRefResponse.from_file(files[0])


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
    background_tasks: BackgroundTasks,
) -> List[UploadedFile]:
    """Upload files to the given agent."""

    thread = await get_storage().get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = await get_storage().get_agent(user.user_id, thread.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    file_manager = get_file_manager()
    stored_files = await file_manager.upload(
        [UploadFileRequest(file=f) for f in files], thread
    )

    await _add_uploaded_messages(stored_files, tid, user)

    background_tasks.add_task(
        file_manager.create_missing_embeddings, agent.model, thread
    )
    return stored_files


@router.post("/{tid}/files/request-upload")
async def request_remote_file_upload(
    payload: RequestRemoteFileUploadPayload, user: AuthedUser, tid: ThreadID
) -> RemoteFileUploadData:
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    response = await get_file_manager().request_remote_file_upload(
        thread=thread, file_name=payload.file_name
    )
    return response


@router.post("/{tid}/files/confirm-upload")
async def confirm_remote_file_upload(
    payload: ConfirmRemoteFileUploadPayload, user: AuthedUser, tid: ThreadID
) -> UploadedFile:
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    file = await get_file_manager().confirm_remote_file_upload(
        thread=thread, file_ref=payload.file_ref, file_id=payload.file_id
    )
    files = await get_file_manager().refresh_file_paths([file])
    await _add_uploaded_messages(files, tid, user)
    return files[0]
