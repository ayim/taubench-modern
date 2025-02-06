from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_server_types_v2.payloads import AddThreadMessagePayload, UpsertThreadPayload
from agent_server_types_v2.thread import Thread
from sema4ai_agent_server.auth.handlers_v2 import AuthedUserV2
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
async def add_message_to_thread(user: AuthedUserV2, tid: str, payload: AddThreadMessagePayload) -> Thread:
    return await get_storage_v2().add_message_to_thread_v2(
        user.user_id,
        tid,
        AddThreadMessagePayload.to_thread_message(payload, user.user_id, tid),
    )
