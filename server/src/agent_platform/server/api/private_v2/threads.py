import dataclasses
import hashlib
from mimetypes import guess_type
from typing import cast

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from structlog import get_logger

from agent_platform.core.context import AgentServerContext
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.files import (
    UploadedFile,
)
from agent_platform.core.payloads import (
    AddThreadMessagePayload,
    ForkThreadPayload,
    SetThreadSemanticDataModelsPayload,
    UploadFilePayload,
    UpsertThreadPayload,
)
from agent_platform.core.payloads.patch_thread import PatchThreadPayload
from agent_platform.core.payloads.semantic_data_model_payloads import (
    ValidateSemanticDataModelResult,
)
from agent_platform.core.thread import Thread
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.server.api.dependencies import (
    FileManagerDependency,
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser
from agent_platform.server.storage import (
    AgentNotFoundError,
    ThreadFileNotFoundError,
    UserPermissionError,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=Thread)
async def create_thread(
    user: AuthedUser, payload: UpsertThreadPayload, storage: StorageDependency, request: Request
) -> Thread:
    thread = UpsertThreadPayload.to_thread(payload, user.user_id)

    server_context = AgentServerContext.from_request(
        request=request,
        user=user,
        version="2.0.0",
    )

    server_context.increment_counter(
        "sema4ai.agent_server.threads",
        1,
        {
            "agent_id": thread.agent_id,
            "thread_id": thread.thread_id,
        },
    )
    server_context.increment_counter(
        "sema4ai.agent_server.messages",
        len(payload.messages),
        {"agent_id": thread.agent_id, "thread_id": thread.thread_id},
    )

    await storage.upsert_thread(user.user_id, thread)
    return thread


@router.put("/{tid}", response_model=Thread)
async def update_thread(
    user: AuthedUser,
    tid: str,
    payload: UpsertThreadPayload,
    storage: StorageDependency,
    request: Request,
) -> Thread:
    """Update an existing thread with the provided fields."""
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    server_context = AgentServerContext.from_request(
        request=request,
        user=user,
        version="2.0.0",
    )
    # Only count new messages, not existing ones being resent
    existing_message_count = len(thread.messages)
    new_message_count = max(0, len(payload.messages) - existing_message_count)

    if new_message_count > 0:
        server_context.increment_counter(
            "sema4ai.agent_server.messages",
            new_message_count,
            {"agent_id": thread.agent_id, "thread_id": thread.thread_id},
        )

    # Start with existing thread data and update with payload fields
    updated_thread = UpsertThreadPayload.to_thread(payload, user.user_id)
    # Preserve the original thread ID
    updated_thread.thread_id = tid
    # We want to merge updated metadata into thread, and then take that into
    # what we're about to insert
    name_changed = updated_thread.name != thread.name
    updated_thread.metadata = thread.update_metadata(updated_thread.metadata)
    if name_changed:
        updated_thread.set_user_named()

    await storage.upsert_thread(user.user_id, updated_thread)
    return updated_thread


@router.patch("/{tid}", response_model=Thread)
async def patch_thread(
    user: AuthedUser,
    tid: str,
    payload: PatchThreadPayload,
    storage: StorageDependency,
    request: Request,
) -> Thread:
    """Partially update a thread with only the provided fields."""
    thread = await storage.get_thread(user.user_id, tid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Only update fields that were provided
    original_name = thread.name
    thread.update_metadata(payload.metadata or {})
    if payload.name is not None:
        if payload.name != original_name:
            thread.set_user_named()
        thread.name = payload.name
    if payload.agent_id is not None:
        thread.agent_id = payload.agent_id
    if payload.work_item_id is not None:
        thread.work_item_id = payload.work_item_id
    if payload.messages is not None:
        # Convert and replace messages only if explicitly provided
        thread.messages = payload.messages
        server_context = AgentServerContext.from_request(
            request=request,
            user=user,
            version="2.0.0",
        )
        server_context.increment_counter(
            "sema4ai.agent_server.messages",
            len(payload.messages),
            {"agent_id": thread.agent_id, "thread_id": thread.thread_id},
        )

    await storage.upsert_thread(user.user_id, thread)
    return thread


@router.get("/", response_model=list[Thread])
async def list_threads(
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
        candidates = [t for t in candidates if name.lower() in t.name.lower()]
    if limit:
        candidates = candidates[:limit]

    for thread in candidates:
        thread.messages = []
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

    # Return thread without messages to improve network performance and use /{tid}/state
    # to get messages
    thread.messages = []
    return thread


# Backwards compatibility
@router.get("/{tid}/state", response_model=Thread)
async def get_thread_state(user: AuthedUser, tid: str, storage: StorageDependency) -> Thread:
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


@router.post("/{tid}/fork", response_model=Thread)
async def fork_thread(
    user: AuthedUser,
    tid: str,
    payload: ForkThreadPayload,
    storage: StorageDependency,
    request: Request,
) -> Thread:
    """Fork a thread at a specific message point.

    Creates a new thread with all messages before the specified message.
    """
    # Get the original thread
    original_thread = await storage.get_thread(user.user_id, tid)
    if original_thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Find the message
    fork_message = None
    fork_message_index = -1
    for i, msg in enumerate(original_thread.messages):
        if msg.message_id == payload.message_id:
            fork_message = msg
            fork_message_index = i
            break

    if fork_message is None:
        raise HTTPException(status_code=404, detail="Message not found in thread")

    # Check if there are any messages before the fork point
    if fork_message_index == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot fork at the first message - no previous messages to include",
        )

    # Get all threads for this agent to check existing names
    existing_threads = await storage.list_threads_for_agent(user.user_id, original_thread.agent_id)
    existing_names = {thread.name for thread in existing_threads}

    # Determine the thread name
    if payload.name:
        if payload.name in existing_names:
            raise HTTPException(status_code=400, detail="Name already in use")
        forked_thread_name = payload.name
    else:
        # Else, auto-generate name with numbered suffix
        base_name = original_thread.name
        fork_number = 1

        while f"{base_name} ({fork_number})" in existing_names:
            fork_number += 1

        forked_thread_name = f"{base_name} ({fork_number})"

    # Copy messages with new message IDs and content IDs
    copied_messages = []
    for msg in original_thread.messages[:fork_message_index]:
        copied_messages.append(msg.copy_with_new_ids())

    # Create new thread with messages before the fork point
    forked_thread = Thread(
        user_id=user.user_id,
        agent_id=original_thread.agent_id,
        name=forked_thread_name,
        messages=copied_messages,
        metadata={
            **original_thread.metadata,
            "forked_from_thread_id": original_thread.thread_id,
            "forked_at_message_id": payload.message_id,
        },
    )

    # Track metrics
    server_context = AgentServerContext.from_request(
        request=request,
        user=user,
        version="2.0.0",
    )

    server_context.increment_counter(
        "sema4ai.agent_server.threads.forked",
        1,
        {
            "agent_id": forked_thread.agent_id,
            "original_thread_id": original_thread.thread_id,
            "forked_thread_id": forked_thread.thread_id,
        },
    )

    # Save the forked thread
    await storage.upsert_thread(user.user_id, forked_thread)

    # Return thread without messages (consistent with other endpoints)
    # Create a copy to avoid modifying the stored thread
    response_thread = Thread(
        thread_id=forked_thread.thread_id,
        user_id=forked_thread.user_id,
        agent_id=forked_thread.agent_id,
        name=forked_thread.name,
        messages=[],
        created_at=forked_thread.created_at,
        updated_at=forked_thread.updated_at,
        metadata=forked_thread.metadata,
    )
    return response_thread


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


@router.post("/{tid}/messages/{message_id}/edit")
async def edit_message(
    user: AuthedUser,
    tid: str,
    message_id: str,
    agent_id: str,
    storage: StorageDependency,
):
    """
    Edit a message. Trims the messages from and after the given message_id.
    """
    try:
        # Verify the agent exists and user has access
        await storage.get_agent(user.user_id, agent_id)

        # Verify the thread exists and user has access
        thread = await storage.get_thread(user.user_id, tid)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Trim the messages from and after the given message_id
        await storage.trim_messages_from_sequence(
            user.user_id,
            tid,
            message_id,
        )

        return {"success": True, "message": "Messages trimmed successfully"}

    except AgentNotFoundError as e:
        logger.error("Error getting agent", error=e)
        raise HTTPException(
            status_code=404,
            detail="Agent not found",
        ) from e

    except UserPermissionError as e:
        logger.error(
            "User permission error in edit_message, cannot edit agent role messages",
            error=e,
            thread_id=tid,
            message_id=message_id,
        )
        raise HTTPException(
            status_code=403,
            detail="You cannot edit agent role messages.",
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in edit_message for thread {tid}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while editing the message.",
        ) from e


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
    file_manager: FileManagerDependency,
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
        raise HTTPException(status_code=404, detail="File not found (storage)")
    updated_files = await file_manager.refresh_file_paths([file])
    if not updated_files:
        raise HTTPException(status_code=404, detail="File not found (refresh)")

    # This may or may not have been updated with the corresponding presigned URL for this file.
    return dataclasses.asdict(updated_files[0])


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
    file = await get_file_by_ref(user, tid, file_ref, storage, file_manager)
    if not file["file_path"]:
        raise HTTPException(status_code=404, detail="File not found")

    media_type = guess_type(file["file_path"])[0] or "application/octet-stream"

    try:
        return StreamingResponse(
            file_manager.stream_file_contents(
                file_id=file["file_id"],
                user_id=user.user_id,
            ),
            media_type=media_type,
        )
    except Exception as e:
        logger.error(f"Error reading file: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to read file") from e


@dataclasses.dataclass
class RequestRemoteFileUploadPayload:
    file_name: str


@dataclasses.dataclass
class ConfirmRemoteFileUploadPayload:
    file_ref: str
    file_id: str


# ruff: noqa: PLR0913
@router.post("/{tid}/files/confirm-upload")
async def confirm_remote_file_upload(
    payload: ConfirmRemoteFileUploadPayload,
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    request: Request,
):
    thread = await storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    file = await file_manager.confirm_remote_file_upload(
        owner=thread, file_ref=payload.file_ref, file_id=payload.file_id
    )
    files = await file_manager.refresh_file_paths([file])

    def to_thread_message(file: UploadedFile) -> ThreadMessage:
        short_id = hashlib.md5(file.file_id.encode()).hexdigest()[:8]
        tool_call_id = f"upload-{short_id}"

        return ThreadMessage(
            role="agent",
            content=[
                ThreadToolUsageContent(
                    name="upload_file",
                    tool_call_id=tool_call_id,
                    status="finished",
                    result=f'File uploaded: "{file.file_ref}"',
                    arguments_raw="",
                )
            ],
        )

    messages: list[ThreadMessage] = [to_thread_message(file) for file in files]
    for message in messages:
        thread.add_message(message=message)

    await storage.upsert_thread(user_id=user.user_id, thread=thread)

    server_context = AgentServerContext.from_request(
        request=request,
        user=user,
        version="2.0.0",
    )
    server_context.increment_counter(
        "sema4ai.agent_server.messages",
        len(messages),
        {"agent_id": thread.agent_id, "thread_id": thread.thread_id},
    )

    return files[0]


@router.post("/{tid}/files/request-upload")
async def request_remote_file_upload(
    payload: RequestRemoteFileUploadPayload,
    user: AuthedUser,
    tid: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
):
    thread = await storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    response = await file_manager.request_remote_file_upload(
        owner=thread, file_name=payload.file_name
    )
    return response


# Thread Semantic Data Models endpoints
@router.put("/{tid}/semantic-data-models", response_model=list[dict])
async def set_thread_semantic_data_models(
    tid: str,
    payload: SetThreadSemanticDataModelsPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[dict]:
    """Set semantic data models for a thread (replace all existing associations)."""
    # Verify thread exists and belongs to user
    thread = await storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Set the semantic data models
    await storage.set_thread_semantic_data_models(tid, payload.semantic_data_model_ids)

    # Return the updated semantic data models
    return await storage.get_thread_semantic_data_models(tid)


@router.get("/{tid}/semantic-data-models", response_model=list[dict])
async def get_thread_semantic_data_models(
    tid: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[dict]:
    """Get semantic data models associated with a thread."""
    # Verify thread exists and belongs to user
    thread = await storage.get_thread(user.user_id, tid)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Return the semantic data models
    return await storage.get_thread_semantic_data_models(tid)


@router.post("/{tid}/semantic-data-models/validate")
async def validate_thread_semantic_data_models(
    tid: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[ValidateSemanticDataModelResult]:
    """Validate all semantic data models associated with a thread, returning
    the validated semantic data models with errors attached. If there are no errors,
    returns the original semantic data models."""
    thread = await storage.get_thread(user.user_id, tid)
    semantic_data_models = await storage.get_thread_semantic_data_models(thread.thread_id)
    if not semantic_data_models:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND, message="No semantic data models found for thread"
        )

    from agent_platform.core.data_frames.semantic_data_model_types import (
        SemanticDataModel,
        ValidationMessage,
    )
    from agent_platform.server.data_frames.semantic_data_model_validator import (
        SemanticDataModelValidator,
    )

    results: list[ValidateSemanticDataModelResult] = []
    for semantic_data_model_info in semantic_data_models:
        semantic_data_model_id = semantic_data_model_info["semantic_data_model_id"]
        semantic_data_model = cast(
            SemanticDataModel, semantic_data_model_info["semantic_data_model"]
        )
        try:
            validator = SemanticDataModelValidator(
                semantic_data_model=cast(SemanticDataModel, semantic_data_model),
                thread_id=thread.thread_id,
                storage=storage,
                user=user,
            )
            validated_semantic_data_model = await validator.validate()
        except Exception as e:
            logger.error(f"Error validating semantic data model: {e!s}", error=str(e))
            results.append(
                ValidateSemanticDataModelResult(
                    semantic_data_model_id=semantic_data_model_id,
                    semantic_data_model={},
                    errors=[ValidationMessage(message=str(e), level="error")],
                )
            )
            continue
        if validator.errors:
            results.append(
                ValidateSemanticDataModelResult(
                    semantic_data_model_id=semantic_data_model_id,
                    semantic_data_model=validated_semantic_data_model,
                    errors=validator.errors,
                )
            )
        else:
            results.append(
                ValidateSemanticDataModelResult(
                    semantic_data_model_id=semantic_data_model_id,
                    semantic_data_model=semantic_data_model,
                    errors=[],
                )
            )

    return results
