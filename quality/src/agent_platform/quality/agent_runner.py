from pathlib import Path

import httpx
import structlog

from agent_platform.quality.models import FileAttachment, Message, TestCase, Text, Thought, ToolUse

logger = structlog.get_logger(__name__)


class AgentRunner:
    """Runs agent tests using the agent server sync endpoint."""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")

    async def run_test_case(  # noqa: C901, PLR0912, PLR0915
        self, agent_id: str, test_case: TestCase, platform_name: str
    ) -> list[Message]:
        """Run a test case against an agent and return agent messages."""
        logger.info(f"Running test case: {test_case.thread.name}")

        thread_id = None
        async with httpx.AsyncClient() as client:
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
                        f"{self.server_url}/api/v2/threads/{thread_id}/files", files=thread_files
                    )
                    response.raise_for_status()
                except httpx.HTTPError as e:
                    logger.error(f"Cannot upload files: {e}")
                    raise

        # Convert test case messages to the API format
        api_messages = []
        for msg in test_case.thread.messages:
            if msg.role == "user":
                # Extract text content from the content objects
                api_content = []
                for content_item in msg.content:
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

                api_messages.append({"role": "user", "content": api_content})
            # Skip assistant messages - we're testing what the agent responds

        # Create the payload for the sync endpoint
        payload = {
            "agent_id": agent_id,
            "name": test_case.thread.name,
            "messages": api_messages,
            "thread_id": thread_id,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.server_url}/api/v2/runs/{agent_id}/sync",
                json=payload,
                timeout=60.0 * 5,  # Allow up to 5 minutes for agent responses
            )
            response.raise_for_status()

            # Parse response - it should be a list of agent messages
            agent_messages_data = response.json()

            # Convert API response to our Message format
            agent_messages = []
            for msg_data in agent_messages_data:
                # Extract text content from the message
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

        logger.info(f"Agent responded with {len(agent_messages)} messages")
        return agent_messages
