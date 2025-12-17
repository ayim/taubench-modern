from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import structlog

from agent_platform.quality.models import (
    FileAttachment,
    Message,
    TestCase,
    TestRunResult,
    Text,
    Thought,
    ToolUse,
    WorkitemResult,
)

if TYPE_CHECKING:
    from agent_platform.core.files.files import UploadedFile

logger = structlog.get_logger(__name__)


def _index_uploaded_file_metadata(
    uploaded_files: dict[str, Any],
    attachment: FileAttachment,
    metadata: dict[str, Any],
) -> None:
    """Index uploaded file metadata by various keys for quick lookup."""
    candidate_keys = {
        attachment.file_name,
        Path(attachment.file_name).name,
    }
    file_ref = metadata.get("file_ref")
    if file_ref:
        candidate_keys.add(file_ref)
        candidate_keys.add(Path(file_ref).name)

    for key in candidate_keys:
        uploaded_files[key] = metadata


def _strip_file_attachments(messages: list[Message]) -> list[Message]:
    """Remove attachment-only content so the backend can inject file messages."""
    stripped_messages: list[Message] = []
    for message in messages:
        filtered_content = [
            content_item for content_item in message.content if not isinstance(content_item, FileAttachment)
        ]
        if filtered_content:
            stripped_messages.append(
                Message(
                    role=message.role,
                    content=cast(list[Thought | Text | ToolUse | FileAttachment], filtered_content),
                )
            )
    return stripped_messages


def _format_http_error(error: httpx.HTTPStatusError) -> str:
    """Build a concise error string from an HTTPStatusError."""

    status = error.response.status_code if error.response is not None else "unknown"
    detail_payload: Any | None = None

    if error.response is not None:
        try:
            payload = error.response.json()
            if isinstance(payload, dict):
                if "detail" in payload:
                    detail_payload = payload.get("detail")
                elif "error" in payload:
                    detail_payload = payload.get("error")
                else:
                    detail_payload = payload
            else:
                detail_payload = payload
        except ValueError:
            detail_payload = error.response.text

    message: str | None = None
    code: str | None = None

    if isinstance(detail_payload, dict):
        code = detail_payload.get("code")
        raw_message = detail_payload.get("message")
        message = raw_message if isinstance(raw_message, str) else json.dumps(detail_payload)
    elif detail_payload:
        message = str(detail_payload)

    if not message and error.response is not None:
        message = error.response.text

    if not message:
        message = str(error)

    if code:
        return f"HTTP {status} ({code}): {message}"
    return f"HTTP {status}: {message}"


def build_agent_platform_message(message: Message, uploaded_files: dict[str, Any] | None = None):
    api_content = []
    for content_item in message.content:
        match content_item:
            case Text(content=text):
                api_content.append({"kind": "text", "text": text})
            case Thought(content=thought):
                api_content.append({"kind": "thought", "thought": thought})
            case ToolUse(
                input_as_string=input_str,
                output_as_string=output_str,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                started_at=started_at,
                ended_at=ended_at,
                error=error,
            ):
                api_content.append(
                    {
                        "kind": "tool_call",
                        "name": tool_name,
                        "tool_call_id": tool_call_id,
                        "arguments_raw": input_str,
                        "result": output_str,
                        "started_at": started_at,
                        "ended_at": ended_at,
                        "error": error,
                    }
                )
            case FileAttachment(
                description=description,
                mime_type=mime_type,
                file_name=file_name,
            ):
                file_metadata = None
                if uploaded_files:
                    file_metadata = uploaded_files.get(file_name) or uploaded_files.get(Path(file_name).name)

                if file_metadata and file_metadata.get("file_id"):
                    api_content.append(
                        {
                            "kind": "attachment",
                            "base64_data": None,
                            "description": description,
                            "mime_type": file_metadata.get("mime_type", mime_type),
                            "name": file_metadata.get("file_ref", file_name),
                            "uri": f"agent-server-file://{file_metadata['file_id']}",
                            "complete": True,
                        }
                    )
                else:
                    api_content.append(
                        {
                            "kind": "attachment",
                            "base64_data": None,
                            "description": description,
                            "mime_type": mime_type,
                            "name": file_name,
                            "uri": f"agent-server-uri://{file_name}",
                        }
                    )
            case _:
                # Fallback for unknown content types
                api_content.append({"kind": "text", "text": str(content_item)})

    return {"role": message.role, "content": api_content}


def from_api_response_to_messages(api_response: Any) -> list[Message]:
    agent_messages = []
    for msg_data in api_response:
        content_parts = msg_data.get("content", [])
        mapped_content = []
        for part in content_parts:
            match part.get("kind"):
                case "text":
                    mapped_content.append(Text(content=part.get("text", "")))
                case "thought":
                    mapped_content.append(Thought(content=part.get("thought", "")))
                case "tool_call":
                    mapped_content.append(
                        ToolUse(
                            input_as_string=part.get("arguments_raw", ""),
                            output_as_string=part.get("result", ""),
                            tool_name=part.get("name", ""),
                            tool_call_id=part.get("tool_call_id", ""),
                            started_at=part.get("started_at", ""),
                            ended_at=part.get("ended_at", ""),
                            error=part.get("error", None),
                        )
                    )
                case "attachment":
                    # TODO server returns it, but should it?
                    pass
                case _:
                    print(json.dumps(part, indent=4))
                    raise ValueError(f"unexpected message kind: {part.get('kind')}")

        agent_messages.append(Message(role="agent", content=mapped_content))
    return agent_messages


async def wait_for_completion(server_url, workitem_id, poll_interval=5, timeout_sec=300):
    start_time_sec = time.monotonic()

    async with httpx.AsyncClient(timeout=60.0 * 5) as client:
        while True:
            elapsed = time.monotonic() - start_time_sec
            if elapsed > timeout_sec:
                raise RuntimeError(f"Workitem {workitem_id} did not complete within {timeout_sec} seconds")

            response = await client.get(f"{server_url}/api/public/v1/work-items/{workitem_id}")
            response.raise_for_status()
            workitem = response.json()

            status = workitem.get("status")
            print(f"Workitem {workitem_id} status: {status}")

            if status in ["NEEDS_REVIEW", "COMPLETED"]:
                return workitem

            await asyncio.sleep(poll_interval)


class AgentRunner:
    """Runs agent tests using the agent server sync endpoint."""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")

    async def run_test_case(
        self,
        agent_id: str,
        test_case: TestCase,
        platform_name: str,
        on_thread_created: Callable[[str], Awaitable[None]] | None = None,
        override_model_id: str | None = None,
    ) -> TestRunResult:
        """Run a test case against an agent and return agent messages."""
        if test_case.workitem is not None:
            logger.info(f"Running test case {test_case.name} (dryrun={test_case.workitem.is_preview_only})")

            if test_case.workitem.is_preview_only:
                stripped_messages = _strip_file_attachments(test_case.workitem.messages)
                api_messages = [build_agent_platform_message(message) for message in stripped_messages]
                payload = {
                    "messages": api_messages,
                    "payload": test_case.workitem.payload,
                    "agent_id": agent_id,
                }
                async with httpx.AsyncClient(timeout=60.0 * 5) as client:
                    response = await client.post(
                        f"{self.server_url}/api/v2/work-items/preview",
                        json=payload,
                    )
                    response.raise_for_status()

                    workitem_status_data = response.json()

                return TestRunResult(
                    agent_messages=test_case.workitem.messages,
                    thread_id=None,
                    workitem_result=WorkitemResult(status=workitem_status_data.get("status")),
                )

            workitem_id = None

            test_case_folder = Path(test_case.file_path).parent
            attachments = [
                attachment
                for message in test_case.workitem.messages
                for attachment in message.content
                if isinstance(attachment, FileAttachment)
            ]

            if attachments:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    for attachment in attachments:
                        file_path = test_case_folder / attachment.file_name
                        try:
                            with file_path.open("rb") as file_handle:
                                workitem_file = {
                                    "file": (
                                        attachment.file_name,
                                        file_handle,
                                        attachment.mime_type,
                                    ),
                                }
                                request_kwargs: dict[str, Any] = {"files": workitem_file}
                                if workitem_id:
                                    request_kwargs["params"] = {"work_item_id": workitem_id}
                                response = await client.post(
                                    f"{self.server_url}/api/public/v1/work-items/upload-file",
                                    **request_kwargs,
                                )
                                response.raise_for_status()
                        except httpx.HTTPError as e:
                            logger.error(f"Cannot upload files: {e}")
                            raise
                        upload_response = response.json()
                        workitem_id = upload_response.get("work_item_id", workitem_id)

            messages_without_attachments = _strip_file_attachments(test_case.workitem.messages)
            api_messages = [build_agent_platform_message(message) for message in messages_without_attachments]
            payload = {
                "messages": api_messages,
                "payload": test_case.workitem.payload,
                "agent_id": agent_id,
                "work_item_id": workitem_id,
            }
            async with httpx.AsyncClient(timeout=60.0 * 5) as client:
                response = await client.post(
                    f"{self.server_url}/api/public/v1/work-items/",
                    json=payload,
                )
                response.raise_for_status()

                agent_messages_data = response.json()

            workitem_id = agent_messages_data.get("work_item_id")
            logger.info(f"Workitem created with id {workitem_id}")
            completed_workitem = await wait_for_completion(self.server_url, workitem_id)

            async with httpx.AsyncClient(timeout=60.0 * 5) as client:
                response = await client.get(
                    f"{self.server_url}/api/v2/threads/{completed_workitem.get('thread_id')}/state",
                )
                response.raise_for_status()

                thread_data = response.json()

            agent_message_data = [msg for msg in thread_data.get("messages", []) if msg["role"] == "agent"]
            agent_messages = from_api_response_to_messages(agent_message_data)

            logger.info(f"Agent responded with {len(agent_messages)} messages")

            return TestRunResult(
                agent_messages=agent_messages,
                thread_id=completed_workitem.get("thread_id"),
                workitem_result=WorkitemResult(status=completed_workitem.get("status")),
            )

        if test_case.thread is not None:
            logger.info(f"Running test case with thread {test_case.thread.name}")

            thread_id = None
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.server_url}/api/v2/threads/",
                    json={
                        "agent_id": agent_id,
                        "name": f"Quality Test: {test_case.name} ({platform_name})",
                    },
                )
                response.raise_for_status()

                new_thread = response.json()
                thread_id = new_thread["thread_id"]
                logger.info(f"Created new thread: {thread_id}")

            if on_thread_created is not None:
                await on_thread_created(thread_id)

            test_case_folder = Path(test_case.file_path).parent
            thread_files: list[tuple[str, tuple[str, Any, str]]] = []
            thread_attachments: list[FileAttachment] = []
            open_file_handles = []
            for message in test_case.thread.messages:
                for attachment in message.content:
                    if not isinstance(attachment, FileAttachment):
                        continue

                    file_path = test_case_folder / attachment.file_name
                    file_handle = file_path.open("rb")
                    open_file_handles.append(file_handle)
                    thread_files.append(
                        (
                            "files",
                            (attachment.file_name, file_handle, attachment.mime_type),
                        )
                    )
                    thread_attachments.append(attachment)

            logger.info(f"Found {len(thread_files)} files in thread")

            uploaded_thread_files: dict[str, Any] = {}
            if thread_files:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    try:
                        response = await client.post(
                            f"{self.server_url}/api/v2/threads/{thread_id}/files",
                            files=thread_files,
                        )
                        response.raise_for_status()
                        uploaded_files = response.json() or []
                        uploaded_thread_files = {}
                        for attachment, file_info in zip(
                            thread_attachments,
                            uploaded_files,
                            strict=False,
                        ):
                            if not isinstance(file_info, dict):
                                continue

                            _index_uploaded_file_metadata(
                                uploaded_thread_files,
                                attachment,
                                file_info,
                            )

                        for file_info in uploaded_files:
                            if not isinstance(file_info, dict):
                                continue

                            file_ref = file_info.get("file_ref")
                            if file_ref:
                                uploaded_thread_files.setdefault(file_ref, file_info)
                                uploaded_thread_files.setdefault(Path(file_ref).name, file_info)
                    except httpx.HTTPError as e:
                        logger.error(f"Cannot upload files: {e}")
                        raise
                    finally:
                        for handle in open_file_handles:
                            handle.close()
            else:
                for handle in open_file_handles:
                    handle.close()

            api_messages = [
                build_agent_platform_message(
                    message,
                    uploaded_files=uploaded_thread_files,
                )
                for message in test_case.thread.messages
            ]
            payload = {
                "agent_id": agent_id,
                "name": test_case.thread.name,
                "messages": api_messages,
                "thread_id": thread_id,
            }

            # Add override_model_id if provided
            if override_model_id:
                payload["override_model_id"] = override_model_id

            request_timeout = test_case.timeout_seconds or 60.0 * 5

            async with httpx.AsyncClient(timeout=request_timeout) as client:
                try:
                    response = await client.post(
                        f"{self.server_url}/api/v2/runs/{agent_id}/sync",
                        json=payload,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    error_message = _format_http_error(e)
                    logger.error(f"Agent sync failed: {error_message}")
                    raise RuntimeError(f"Agent sync failed: {error_message}") from e

                agent_messages_data = response.json()
                agent_messages = from_api_response_to_messages(agent_messages_data)

                logger.info(f"Agent responded with {len(agent_messages)} messages")

                return TestRunResult(agent_messages=agent_messages, thread_id=thread_id, workitem_result=None)

        raise ValueError("Test case should contain either thread or workitem, found none")

    async def get_thread_files(self, thread_id: str) -> list[UploadedFile]:
        """Get all files attached to a thread.

        Args:
            thread_id: The thread ID to fetch files for.

        Returns:
            List of UploadedFile objects attached to the thread.
        """
        from agent_platform.core.files.files import UploadedFile

        async with httpx.AsyncClient(timeout=60.0 * 5) as client:
            response = await client.get(
                f"{self.server_url}/api/v2/threads/{thread_id}/files",
            )
            response.raise_for_status()

            files_data = response.json()

            # Marshall response to UploadedFile objects
            thread_files = [UploadedFile.model_validate(file_dict) for file_dict in files_data]

        return thread_files
