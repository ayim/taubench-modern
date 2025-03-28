import hashlib
from typing import List

from agent_server_types import UploadedFile
from fastapi import APIRouter
from langchain_core.messages import AIMessage, ToolCall, ToolMessage

from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.storage.option import get_storage

router = APIRouter()


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

        # User may ask a question about the file right after uploading it.
        # Anthropic will break in this case because human message will immediately
        # follow the tool call message, which is not allowed. So we add an AI
        # message here. https://github.com/langchain-ai/langchain-aws/issues/141
        tool_ai_summary_message = AIMessage(
            content=f'File uploaded: "{stored_file.file_ref}"'
        )

        # Append new messages to existing messages
        updated_messages = current_messages + [
            tool_call_message,
            tool_response_message,
            tool_ai_summary_message,
        ]

        # Update thread state with appended messages
        await get_storage().update_thread_state(
            thread_id, {"messages": updated_messages}
        )
