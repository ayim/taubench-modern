import asyncio
import time
from pathlib import Path
from typing import Any

import httpx
import structlog

from agent_platform.quality.models import (
    FileAttachment,
    Message,
    TestCase,
    Text,
    Thought,
    ToolUse,
    WorkitemResult,
)

logger = structlog.get_logger(__name__)


def build_agent_platform_user_message(message: Message):
    if message.role != "user":
        raise ValueError(f"Expected user role, found {message.role}")

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
                started_at=started_at,
                ended_at=ended_at,
                error=error,
            ):
                api_content.append(
                    {
                        "kind": "tool_call",
                        "name": tool_name,
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

    return {"role": "user", "content": api_content}


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
                            started_at=part.get("started_at", ""),
                            ended_at=part.get("ended_at", ""),
                            error=part.get("error", None),
                        )
                    )

    agent_messages.append(Message(role="agent", content=mapped_content))
    return agent_messages


async def wait_for_completion(server_url, workitem_id, poll_interval=5, timeout_sec=300):
    start_time_sec = time.monotonic()

    async with httpx.AsyncClient(timeout=60.0 * 5) as client:
        while True:
            elapsed = time.monotonic() - start_time_sec
            if elapsed > timeout_sec:
                raise RuntimeError(
                    f"Workitem {workitem_id} did not complete within {timeout_sec} seconds"
                )

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

    async def run_test_case(  # noqa: PLR0915
        self, agent_id: str, test_case: TestCase, platform_name: str
    ) -> tuple[list[Message], WorkitemResult | None]:
        """Run a test case against an agent and return agent messages."""
        if test_case.workitem is not None:
            logger.info(f"Running test case with workitem {test_case.name}")

            workitem_id = None

            test_case_folder = Path(test_case.file_path).parent
            attachments = [
                attachment
                for message in test_case.workitem.messages
                for attachment in message.content
                if isinstance(attachment, FileAttachment)
            ]

            if len(attachments) > 1:
                raise ValueError(f"Only one file is allowed in workitems. Found {len(attachments)}")

            if len(attachments) == 1:
                attachment = attachments[0]
                workitem_file = {
                    "file": (
                        attachment.file_name,
                        open(test_case_folder / attachment.file_name, "rb"),
                        attachment.mime_type,
                    ),
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    try:
                        response = await client.post(
                            f"{self.server_url}/api/public/v1/work-items/upload-file",
                            files=workitem_file,
                        )
                        response.raise_for_status()

                        workitem = response.json()
                        workitem_id = workitem.get("work_item_id")
                    except httpx.HTTPError as e:
                        logger.error(f"Cannot upload files: {e}")
                        raise

            api_messages = [
                build_agent_platform_user_message(message)
                for message in test_case.workitem.messages
            ]
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

            agent_message_data = [
                msg for msg in thread_data.get("messages", []) if msg["role"] == "agent"
            ]
            agent_messages = from_api_response_to_messages(agent_message_data)

            logger.info(f"Agent responded with {len(agent_messages)} messages")
            return agent_messages, WorkitemResult(status=completed_workitem.get("status"))

        if test_case.thread is not None:
            logger.info(f"Running test case with thread {test_case.thread.name}")

            thread_id = None
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.server_url}/api/v2/threads/",
                    json={"agent_id": agent_id, "name": f"Quality Test Run on {platform_name}"},
                )
                response.raise_for_status()

                new_thread = response.json()
                thread_id = new_thread["thread_id"]
                logger.info(f"Created new thread: {thread_id}")

            test_case_folder = Path(test_case.file_path).parent
            thread_files = [
                (
                    "files",
                    (
                        attachment.file_name,
                        open(test_case_folder / attachment.file_name, "rb"),
                        attachment.mime_type,
                    ),
                )
                for message in test_case.thread.messages
                for attachment in message.content
                if isinstance(attachment, FileAttachment)
            ]

            logger.info(f"Found {len(thread_files)} files in thread")

            if len(thread_files) > 0:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    try:
                        response = await client.post(
                            f"{self.server_url}/api/v2/threads/{thread_id}/files",
                            files=thread_files,
                        )
                        response.raise_for_status()
                    except httpx.HTTPError as e:
                        logger.error(f"Cannot upload files: {e}")
                        raise

            api_messages = [
                build_agent_platform_user_message(message) for message in test_case.thread.messages
            ]
            payload = {
                "agent_id": agent_id,
                "name": test_case.thread.name,
                "messages": api_messages,
                "thread_id": thread_id,
            }

            async with httpx.AsyncClient(timeout=60.0 * 5) as client:
                response = await client.post(
                    f"{self.server_url}/api/v2/runs/{agent_id}/sync",
                    json=payload,
                )
                response.raise_for_status()

                agent_messages_data = response.json()
                agent_messages = from_api_response_to_messages(agent_messages_data)

                logger.info(f"Agent responded with {len(agent_messages)} messages")
                return agent_messages, None

        raise ValueError("Test case should contain either thread or workitem, found none")
