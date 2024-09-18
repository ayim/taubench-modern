import hashlib
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from pydantic import BaseModel

from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.schema import UploadedFile
from sema4ai_agent_server.storage.option import get_storage

router = APIRouter()


class GetFilePayload(BaseModel):
    agent_id: UUID
    thread_id: UUID
    file_ref: str


@router.post("/get-file")
async def get_file(payload: GetFilePayload, user: AuthedUser) -> UploadedFile:
    """Retrieve an UploadedFile object."""
    storage = get_storage()

    # Check if the user has access to the thread
    thread = await storage.get_thread(str(user.user_id), str(payload.thread_id))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found or access denied")

    if thread.agent_id != str(payload.agent_id):
        raise HTTPException(status_code=404, detail="Agent and thread mismatch")

    # Try to get the file from the thread first
    file = await storage.get_file(thread, payload.file_ref)

    if not file:
        # If not found in thread, try to get the file from the agent
        agent = await storage.get_agent(str(user.user_id), str(payload.agent_id))
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        file = await storage.get_file(agent, payload.file_ref)

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    return file


async def _add_uploaded_messages(
    stored_files: List[UploadedFile], thread_id: str, user: AuthedUser
):
    for stored_file in stored_files:
        if stored_file is None:
            continue
        # Generate a short, unique identifier for the tool call
        short_id = hashlib.md5(stored_file.file_id.encode()).hexdigest()[:8]
        tool_call_id = f"upload-{short_id}"

        # Get current thread state
        current_state = await get_storage().get_thread_state(thread_id)
        current_messages = current_state.get("messages", [])

        # Create tool call message
        tool_call_message = AIMessage(
            content="",
            tool_calls=[
                ToolCall(
                    name="upload_file",
                    args=dict(),
                    id=tool_call_id,
                )
            ],
        )

        # Create tool response message
        tool_response_message = ToolMessage(
            tool_call_id=tool_call_id,
            content=f'File uploaded: "{stored_file.file_ref}"',
            additional_kwargs={
                "name": "upload_file",
            },
        )

        # Append new messages to existing messages
        updated_messages = current_messages + [
            tool_call_message,
            tool_response_message,
        ]

        # Update thread state with appended messages
        await get_storage().update_thread_state(
            thread_id, {"messages": updated_messages}
        )
