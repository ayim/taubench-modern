from fastapi import APIRouter, HTTPException, UploadFile
from structlog import get_logger

from agent_server_types_v2.files import UploadedFile, UploadFileRequest
from agent_server_types_v2.payloads import AddThreadMessagePayload, UpsertThreadPayload
from agent_server_types_v2.thread import Thread
from sema4ai_agent_server.auth.handlers_v2 import AuthedUserV2
from sema4ai_agent_server.file_manager.v2.option_v2 import get_file_manager_v2
from sema4ai_agent_server.storage.v2 import get_storage_v2

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=Thread)
async def create_thread(user: AuthedUserV2, payload: UpsertThreadPayload) -> Thread:
    thread = UpsertThreadPayload.to_thread(payload, user.user_id)
    await get_storage_v2().upsert_thread_v2(user.user_id, thread)
    return thread


@router.get("/", response_model=list[Thread])
async def list_threads(
    user: AuthedUserV2,
    agent_id: str | None = None,
) -> list[Thread]:
    if agent_id:
        return await get_storage_v2().list_threads_for_agent_v2(user.user_id, agent_id)
    else:
        return await get_storage_v2().list_threads_v2(user.user_id)


@router.get("/{tid}", response_model=Thread)
async def get_thread(user: AuthedUserV2, tid: str) -> Thread:
    thread = await get_storage_v2().get_thread_v2(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/{tid}", status_code=204)
async def delete_thread(user: AuthedUserV2, tid: str) -> None:
    await get_storage_v2().delete_thread_v2(user.user_id, tid)


@router.post("/{tid}/messages", response_model=Thread)
async def add_message_to_thread(
    user: AuthedUserV2,
    tid: str,
    payload: AddThreadMessagePayload,
) -> Thread:
    return await get_storage_v2().add_message_to_thread_v2(
        user.user_id,
        tid,
        AddThreadMessagePayload.to_thread_message(payload, user.user_id, tid),
    )


# File operations
file_manager = get_file_manager_v2()


@router.get("/{tid}/files", response_model=list[UploadedFile])
async def get_thread_files(
    user: AuthedUserV2,
    tid: str,
):
    """Get a list of files associated with a thread."""
    thread = await get_storage_v2().get_thread_v2(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread_files = await get_storage_v2().get_thread_files_v2(tid, user.user_id)
    return thread_files


@router.get(
    "/{tid}/file-by-ref",
    response_model=UploadedFile,
)
async def get_file_by_ref(
    user: AuthedUserV2,
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
    thread = await get_storage_v2().get_thread_v2(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    file = await get_storage_v2().get_file_by_ref_v2(thread, file_ref, user.user_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.post("/{tid}/files", response_model=list[UploadedFile])
async def upload_thread_files(
    files: list[UploadFile],
    user: AuthedUserV2,
    tid: str,
):
    """Upload files to a thread."""
    logger.info(f"Uploading files to thread {tid} for user {user.user_id}")
    thread = await get_storage_v2().get_thread_v2(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    upload_requests = [UploadFileRequest(file=f) for f in files]
    stored_files = await file_manager.upload(upload_requests, thread, user.user_id)

    return stored_files


@router.delete("/{tid}/files/{file_id}", status_code=204)
async def delete_file_by_id(
    user: AuthedUserV2,
    tid: str,
    file_id: str,
):
    """Delete a file associated with a thread."""
    thread = await get_storage_v2().get_thread_v2(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await file_manager.delete(tid, user.user_id, file_id)


@router.delete("/{tid}/files", status_code=204)
async def delete_thread_files(
    user: AuthedUserV2,
    tid: str,
):
    """Delete all files associated with a thread."""
    thread = await get_storage_v2().get_thread_v2(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await file_manager.delete_thread_files(tid, user.user_id)
