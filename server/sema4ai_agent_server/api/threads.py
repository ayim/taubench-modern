import datetime
from mimetypes import guess_type
from pathlib import Path
from typing import Annotated, Any, Dict, List, Sequence, Union
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import structlog
from agent_server_types import (
    THREAD_LIST_ADAPTER,
    UPLOADED_FILE_LIST_ADAPTER,
    Thread,
    UploadedFile,
)
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, Query
from fastapi.responses import StreamingResponse
from httpx import Response
from langchain_core.messages import AIMessage
from opentelemetry import metrics
from pydantic import BaseModel, Field

from sema4ai_agent_server.api.files import _add_uploaded_messages
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.file_manager.base import RemoteFileUploadData
from sema4ai_agent_server.file_manager.local import url_to_fs_path
from sema4ai_agent_server.file_manager.option import get_file_manager
from sema4ai_agent_server.llms import (
    ContextStats,
    get_context_stats,
    get_context_summary,
)
from sema4ai_agent_server.message_types import AnyNonChunkMessage
from sema4ai_agent_server.otel import otel_is_enabled
from sema4ai_agent_server.responses import PydanticResponse, TypeAdapterResponse
from sema4ai_agent_server.schema import UploadFileRequest
from sema4ai_agent_server.storage.embed import guess_mimetype
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)

router = APIRouter()

ThreadID = Annotated[str, Path(description="The ID of the thread.")]

if otel_is_enabled():
    meter = metrics.get_meter(__name__)
    thread_counter = meter.create_counter(
        name="sema4ai.agent_server.threads",
        description="Number of threads created",
    )
    token_counter = meter.create_counter(
        name="sema4ai.agent_server.tokens",
        description="Total number of tokens in the thread",
    )
    message_counter = meter.create_counter(
        name="sema4ai.agent_server.messages",
        description="Total number of messages in the thread",
    )


class ThreadPostRequest(BaseModel):
    """Payload for creating a thread."""

    name: str = Field(..., description="The name of the thread.")
    agent_id: str = Field(..., description="The ID of the agent to use.")
    starting_message: str | None = Field(
        None, description="The starting AI message for the thread."
    )


class ThreadPutRequest(BaseModel):
    """Payload for updating a thread."""

    name: str = Field(..., description="The name of the thread.")
    agent_id: str = Field(..., description="The ID of the agent to use.")


class ThreadStatePostRequest(BaseModel):
    """Payload for adding state to a thread."""

    values: Union[Sequence[AnyNonChunkMessage], Dict[str, Any]]


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
        return cls(file_url=file.file_path)


@router.get("/", response_model=List[Thread], response_class=TypeAdapterResponse)
async def list_threads(user: AuthedUser,
                       name: str | None = Query(None, description="Filter threads by name (contains)."),
                       aid: str | None = Query(None, description="Filter threads by agent ID."),
                       limit: int | None = Query(None, description="Limit the number of threads returned.")):
    """List all threads for the current user."""
    if limit is not None and limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be greater than 0.")
    threads = await get_storage().list_threads(user.user_id, aid=aid, name=name, limit=limit)
    return TypeAdapterResponse(threads, adapter=THREAD_LIST_ADAPTER)


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
    if otel_is_enabled():
        agent = await get_storage().get_agent(user.user_id, thread.agent_id)
        if agent is None:
            logger.critical(
                f"Unable to find agent for user: {user.user_id}, agent: {thread.agent_id}"
            )
        else:
            stats = get_context_stats(agent.model, state)
            summary = get_context_summary(stats)
            attributes = {
                "agent_id": thread.agent_id,
                "thread_id": thread.thread_id,
                "llm.provider": agent.model.provider,
                "llm.model": getattr(agent.model, "name", ""),
                # NoneType fails to be encoded so we use "None" instead
                "user_id": user.cr_user_id if user.cr_user_id else "None",
                "system_id": user.cr_system_id if user.cr_system_id else "None",
            }
            message_counter.add(
                len(stats.tokens_per_message),
                attributes,
            )

            token_attributes = {key: value for key, value in attributes.items()}
            token_attributes["context_window_size"] = (
                summary.context_window_size
                if summary.context_window_size is not None
                else "None"
            )
            token_counter.add(
                summary.total_tokens,
                token_attributes,
            )

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


@router.get("/{tid}", response_model=Thread, response_class=PydanticResponse)
async def get_thread(
    user: AuthedUser,
    tid: ThreadID,
):
    """Get a thread by ID."""
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return PydanticResponse(thread)


@router.post("", response_model=Thread, response_class=PydanticResponse)
async def create_thread(
    user: AuthedUser,
    payload: ThreadPostRequest,
):
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
        created_at=datetime.datetime.now(datetime.timezone.utc),
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
                "agent_id": thread.agent_id,
                "thread_id": thread.thread_id,
                # NoneType fails to be encoded so we use "None" instead
                "user_id": user.cr_user_id if user.cr_user_id else "None",
                "system_id": user.cr_system_id if user.cr_system_id else "None",
            },
        )

    return PydanticResponse(thread)


@router.put("/{tid}", response_model=Thread, response_class=PydanticResponse)
async def upsert_thread(
    user: AuthedUser,
    tid: ThreadID,
    payload: ThreadPutRequest,
):
    """Update a thread."""
    # Check if user has access to the agent
    agent = await get_storage().get_agent(user.user_id, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread = await get_storage().put_thread(
        user.user_id,
        tid,
        agent_id=payload.agent_id,
        name=payload.name,
        metadata=thread.metadata,
        created_at=thread.created_at,
    )
    return PydanticResponse(thread)


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
    # TODO: Update return to match how delete_agent works
    return {"status": "ok"}


async def _get_file_by_ref(
    user: AuthedUser, tid: ThreadID, file_ref: str
) -> UploadedFile:
    """Helper function to get the fileinfo by reference"""
    if (thread := await get_storage().get_thread(user.user_id, tid)) is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    if (file := await get_storage().get_file(thread, file_ref)) is None:
        raise HTTPException(status_code=404, detail="File not found")

    if uploaded_files := await get_file_manager().refresh_file_paths([file]):
        return uploaded_files[0]

    raise HTTPException(status_code=404, detail="File not found")


@router.get(
    "/{tid}/file-by-ref",
    response_model=FileByRefResponse,
    response_class=PydanticResponse,
)
async def get_file_by_ref(
    user: AuthedUser,
    tid: ThreadID,
    file_ref: str,
):
    file = await _get_file_by_ref(user, tid, file_ref)
    return PydanticResponse(FileByRefResponse.from_file(file))


@router.get("/{tid}/files/download/")
async def download_file_by_ref(
    user: AuthedUser,
    tid: ThreadID,
    file_ref: str,
):
    chunk_size = 8 * 1024

    file = await _get_file_by_ref(user, tid, file_ref)
    parsed_url = urlparse(file.file_path)
    media_type = guess_type(file.file_path)[0] or "application/octet-stream"

    match parsed_url.scheme:
        case "file":
            path = url_to_fs_path(file.file_path)

            def _handler():
                nonlocal path, chunk_size
                with Path(path).open(mode="rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk

        case "http" | "https":

            async def _handler():
                nonlocal chunk_size, file
                async with httpx.stream("GET", file.file_path) as response:  # type: Response
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                        yield chunk
        case _:
            logger.error(f"Unsupported file scheme: {parsed_url.scheme}")
            raise HTTPException(status_code=500, detail="Invalid file")

    return StreamingResponse(_handler(), media_type=media_type)


@router.get(
    "/{tid}/files",
    response_model=List[UploadedFile],
    response_class=TypeAdapterResponse,
)
async def get_thread_files(
    user: AuthedUser,
    tid: ThreadID,
):
    """Get a list of files associated with a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread_files = await get_storage().get_thread_files(tid)
    return TypeAdapterResponse(thread_files, adapter=UPLOADED_FILE_LIST_ADAPTER)


@router.post(
    "/{tid}/files",
    response_model=List[UploadedFile],
    response_class=TypeAdapterResponse,
)
async def upload_thread_files(
    files: list[UploadFile],
    user: AuthedUser,
    tid: ThreadID,
    background_tasks: BackgroundTasks,
    embedded: bool | None = None,
):
    """
    Upload files to the given agent.

    Args:
        files: The files to upload.
        user: The user uploading the files.
        tid: The thread ID to upload the files to.
        background_tasks: The background tasks to run.
        embedded: Whether to embed the files. If not given, it will be inferred from the file type.
    """

    thread = await get_storage().get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = await get_storage().get_agent(user.user_id, thread.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    file_manager = get_file_manager()
    stored_files = await file_manager.upload(
        [UploadFileRequest(file=f, embedded=embedded) for f in files], thread
    )

    await _add_uploaded_messages(stored_files, tid, user)

    if any(file.embedded for file in stored_files):
        background_tasks.add_task(
            file_manager.create_missing_embeddings, agent.model, thread
        )
    return TypeAdapterResponse(stored_files, adapter=UPLOADED_FILE_LIST_ADAPTER)


@router.post(
    "/{tid}/files/request-upload",
    response_model=RemoteFileUploadData,
    response_class=PydanticResponse,
)
async def request_remote_file_upload(
    payload: RequestRemoteFileUploadPayload, user: AuthedUser, tid: ThreadID
):
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    response = await get_file_manager().request_remote_file_upload(
        thread=thread, file_name=payload.file_name
    )
    return PydanticResponse(response)


@router.post(
    "/{tid}/files/confirm-upload",
    response_model=UploadedFile,
    response_class=PydanticResponse,
)
async def confirm_remote_file_upload(
    payload: ConfirmRemoteFileUploadPayload, user: AuthedUser, tid: ThreadID
):
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    file = await get_file_manager().confirm_remote_file_upload(
        thread=thread, file_ref=payload.file_ref, file_id=payload.file_id
    )
    files = await get_file_manager().refresh_file_paths([file])
    await _add_uploaded_messages(files, tid, user)
    return PydanticResponse(files[0])


@router.get(
    "/{tid}/context-stats",
    response_model=ContextStats,
    response_class=PydanticResponse,
)
async def context_stats(user: AuthedUser, tid: ThreadID):
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = await get_storage().get_agent(user.user_id, thread.agent_id)
    if agent is None:
        detail = "Unattached thread. Unable to process stats without model info."
        raise HTTPException(status_code=422, detail=detail)

    state = await get_storage().get_thread_state(tid)
    try:
        return PydanticResponse(get_context_stats(agent.model, state))
    except ValueError as e:
        logger.exception("Failed to get context stats")
        raise HTTPException(status_code=400, detail=str(e))
