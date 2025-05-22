from mimetypes import guess_type

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from structlog import get_logger

from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads import (
    AddThreadMessagePayload,
    UploadFilePayload,
    UpsertThreadPayload,
)
from agent_platform.core.thread import Thread
from agent_platform.server.api.dependencies import (
    FileManagerDependency,
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser
from agent_platform.server.storage import ThreadFileNotFoundError

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=Thread)
async def create_thread(
    user: AuthedUser,
    payload: UpsertThreadPayload,
    storage: StorageDependency,
) -> Thread:
    thread = UpsertThreadPayload.to_thread(payload, user.user_id)
    await storage.upsert_thread(user.user_id, thread)
    return thread


@router.put("/{tid}", response_model=Thread)
async def update_thread(
    user: AuthedUser,
    tid: str,
    payload: UpsertThreadPayload,
    storage: StorageDependency,
) -> Thread:
    """Update an existing thread with the provided fields."""
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Start with existing thread data and update with payload fields
    updated_thread = UpsertThreadPayload.to_thread(payload, user.user_id)
    # Preserve the original thread ID
    updated_thread.thread_id = tid

    await storage.upsert_thread(user.user_id, updated_thread)
    return updated_thread


@router.get("/", response_model=list[Thread])
async def list_threads(  # noqa: PLR0913
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str | None = None,
    aid: str | None = None,  # Backwards compatibility
    name: str | None = None,
    limit: int | None = None,
) -> list[Thread]:
    if agent_id:
        candidates = await storage.list_threads_for_agent(user.user_id, agent_id)
    elif aid:
        candidates = await storage.list_threads_for_agent(user.user_id, aid)
    else:
        candidates = await storage.list_threads(user.user_id)
    # TODO: name/limit should be pushed down to the storage layer
    if name:
        candidates = [t for t in candidates if name in t.name]
    if limit:
        candidates = candidates[:limit]
    return candidates


@router.delete("/", status_code=204)
async def delete_threads_for_agent(
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str,
    thread_ids: list[str] | None = None,
):
    agent = await storage.get_agent(user.user_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await storage.delete_threads_for_agent(user.user_id, agent_id, thread_ids)


@router.get("/{tid}", response_model=Thread)
async def get_thread(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
) -> Thread:
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


# Backwards compatibility
@router.get("/{tid}/state", response_model=Thread)
async def get_thread_state(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
) -> Thread:
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


# Backwards compatibility
@router.get("/{tid}/context-stats", response_model=dict)
async def get_thread_context_stats(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
) -> dict:
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    # TODO: this was a bad idea originally, context window size is NOT
    # a property of the thread, token counts are NOT a property of the message
    # This is all model/prompt dependent and we really just _shouldn't_ need
    # to do this if we manage context appropriately.
    return dict(
        context_window_size=100000,
        tokens_per_message={m.message_id: 0 for m in thread.messages},
    )


@router.delete("/{tid}", status_code=204)
async def delete_thread(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
) -> None:
    await storage.delete_thread(user.user_id, tid)


@router.post("/{tid}/messages", response_model=Thread)
async def add_message_to_thread(
    user: AuthedUser,
    tid: str,
    payload: AddThreadMessagePayload,
    storage: StorageDependency,
) -> Thread:
    await storage.add_message_to_thread(
        user.user_id,
        tid,
        AddThreadMessagePayload.to_thread_message(payload),
    )
    return await storage.get_thread(user.user_id, tid)


# File operations


@router.get("/{tid}/files", response_model=list[UploadedFile])
async def get_thread_files(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
):
    """Get a list of files associated with a thread."""
    thread = await storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    try:
        thread_files = await storage.get_thread_files(tid, user.user_id)
    except ThreadFileNotFoundError:
        return []
    return thread_files


@router.get(
    "/{tid}/file-by-ref",
    response_model=UploadedFile,
)
async def get_file_by_ref(
    user: AuthedUser,
    tid: str,
    file_ref: str,
    storage: StorageDependency,
):
    """Get a file by its reference."""
    logger.info(
        "Getting file by ref",
        file_ref=file_ref,
        thread_id=tid,
        user_id=user.user_id,
    )
    thread = await storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    file = await storage.get_file_by_ref(thread, file_ref, user.user_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.post("/{tid}/files", response_model=list[UploadedFile])
async def upload_thread_files(
    files: list[UploadFile],
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
):
    """Upload files to a thread."""
    logger.info(f"Uploading files to thread {tid} for user {user.user_id}")
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    upload_requests = [UploadFilePayload(file=f) for f in files]
    stored_files = await file_manager.upload(upload_requests, thread, user.user_id)

    return stored_files


@router.delete("/{tid}/files/{file_id}", status_code=204)
async def delete_file_by_id(
    user: AuthedUser,
    tid: str,
    file_id: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
):
    """Delete a file associated with a thread."""
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await file_manager.delete(tid, user.user_id, file_id)


@router.delete("/{tid}/files", status_code=204)
async def delete_thread_files(
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
):
    """Delete all files associated with a thread."""
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await file_manager.delete_thread_files(tid, user.user_id)


@router.get("/{tid}/files/download/")
async def download_file_by_ref(
    user: AuthedUser,
    tid: str,
    file_ref: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
):
    file = await get_file_by_ref(user, tid, file_ref, storage)
    if not file.file_path:
        raise HTTPException(status_code=404, detail="File not found")

    media_type = guess_type(file.file_path)[0] or "application/octet-stream"

    try:
        return StreamingResponse(
            file_manager.stream_file_contents(
                file_id=file.file_id,
                user_id=user.user_id,
            ),
            media_type=media_type,
        )
    except Exception as e:
        logger.error(f"Error reading file: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to read file") from e
