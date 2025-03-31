from fastapi import APIRouter, HTTPException, UploadFile
from structlog import get_logger

from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads import (
    AddThreadMessagePayload,
    UploadFilePayload,
    UpsertThreadPayload,
)
from agent_platform.core.thread import Thread
from agent_platform.server.auth.handlers import AuthedUser
from agent_platform.server.file_manager.option import get_file_manager
from agent_platform.server.storage import get_storage

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=Thread)
async def create_thread(user: AuthedUser, payload: UpsertThreadPayload) -> Thread:
    thread = UpsertThreadPayload.to_thread(payload, user.user_id)
    await get_storage().upsert_thread(user.user_id, thread)
    return thread


@router.get("/", response_model=list[Thread])
async def list_threads(
    user: AuthedUser,
    agent_id: str | None = None,
) -> list[Thread]:
    if agent_id:
        return await get_storage().list_threads_for_agent(user.user_id, agent_id)
    else:
        return await get_storage().list_threads(user.user_id)


@router.get("/{tid}", response_model=Thread)
async def get_thread(user: AuthedUser, tid: str) -> Thread:
    thread = await get_storage().get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/{tid}", status_code=204)
async def delete_thread(user: AuthedUser, tid: str) -> None:
    await get_storage().delete_thread(user.user_id, tid)


@router.post("/{tid}/messages", response_model=Thread)
async def add_message_to_thread(
    user: AuthedUser,
    tid: str,
    payload: AddThreadMessagePayload,
) -> Thread:
    await get_storage().add_message_to_thread(
        user.user_id,
        tid,
        AddThreadMessagePayload.to_thread_message(payload),
    )
    return await get_storage().get_thread(user.user_id, tid)

# File operations
file_manager = get_file_manager()


@router.get("/{tid}/files", response_model=list[UploadedFile])
async def get_thread_files(
    user: AuthedUser,
    tid: str,
):
    """Get a list of files associated with a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread_files = await get_storage().get_thread_files(tid, user.user_id)
    return thread_files


@router.get(
    "/{tid}/file-by-ref",
    response_model=UploadedFile,
)
async def get_file_by_ref(
    user: AuthedUser,
    tid: str,
    file_ref: str,
):
    """Get a file by its reference."""
    logger.info(
        "Getting file by ref",
        file_ref=file_ref,
        thread_id=tid,
        user_id=user.user_id,
    )
    thread = await get_storage().get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    file = await get_storage().get_file_by_ref(thread, file_ref, user.user_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.post("/{tid}/files", response_model=list[UploadedFile])
async def upload_thread_files(
    files: list[UploadFile],
    user: AuthedUser,
    tid: str,
):
    """Upload files to a thread."""
    logger.info(f"Uploading files to thread {tid} for user {user.user_id}")
    thread = await get_storage().get_thread(user.user_id, tid)
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
):
    """Delete a file associated with a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await file_manager.delete(tid, user.user_id, file_id)


@router.delete("/{tid}/files", status_code=204)
async def delete_thread_files(
    user: AuthedUser,
    tid: str,
):
    """Delete all files associated with a thread."""
    thread = await get_storage().get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await file_manager.delete_thread_files(tid, user.user_id)
