from typing import Annotated

from fastapi import Request
from mcp.server import FastMCP
from pydantic import Field

import agent_platform.server.api.private_v2.agents as agents_api
import agent_platform.server.api.private_v2.runs as runs_api
import agent_platform.server.api.private_v2.threads as threads_api
from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.messages import ThreadAgentMessage, ThreadUserMessage
from agent_platform.core.thread.thread import Thread
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.storage import StorageService

mcp = FastMCP("Agent Server MCP")


@mcp.tool(
    "list_agents",
    description="List all agents hosted on the server.",
)
async def list_agents() -> list[AgentCompat]:
    storage = StorageService.get_instance()
    mcp_user, _ = await storage.get_or_create_user("static-default-user-id")
    return await agents_api.list_agents(mcp_user, storage)


@mcp.tool(
    "chat_with_agent",
    description=(
        "Chat with an agent on thread (conversation) by providing a thread "
        "name and a message. If the existing_thread_id is not provided, "
        "a new thread will be created. If you need to continue a conversation "
        "with an agent, you can provide the existing_thread_id of the thread "
        "you wish to continue chatting on."
    ),
)
async def chat_with_agent(
    agent_id: Annotated[
        str,
        Field(description="The UUID of the agent to chat with, this must be provided."),
    ],
    thread_name: Annotated[
        str,
        Field(description="The name of the thread to chat on, this must be provided."),
    ],
    message: Annotated[
        str,
        Field(description="The message to send to the agent, this must be provided."),
    ],
    existing_thread_id: Annotated[
        str | None,
        Field(
            description=(
                "The UUID of the thread to continue chatting on, only provide this "
                "if you wish to continue a conversation with an agent."
            ),
        ),
    ],
) -> list[ThreadAgentMessage]:
    storage = StorageService.get_instance()
    mcp_user, _ = await storage.get_or_create_user("static-default-user-id")
    initiate_payload = InitiateStreamPayload(
        agent_id=agent_id,
        thread_id=existing_thread_id,
        name=thread_name,
        messages=[
            ThreadUserMessage(
                content=[ThreadTextContent(text=message)],
            )
        ],
    )
    return await runs_api.sync_run(
        agent_id,
        initiate_payload,
        mcp_user,
        storage,
        Request(scope={"type": "http", "method": "POST"}),
    )


@mcp.tool(
    "list_threads_for_agent",
    description="List all threads for an agent.",
)
async def list_threads_for_agent(
    agent_id: Annotated[
        str,
        Field(
            description=(
                "The UUID of the agent to list threads for, this must be provided."
            ),
        ),
    ],
) -> list[Thread]:
    storage = StorageService.get_instance()
    mcp_user, _ = await storage.get_or_create_user("static-default-user-id")
    return await threads_api.list_threads(
        mcp_user,
        storage,
        agent_id=agent_id,
        limit=50,
    )


@mcp.resource("agents://{name}")
async def agents_resource(name: str) -> AgentCompat:
    storage = StorageService.get_instance()
    mcp_user, _ = await storage.get_or_create_user("static-default-user-id")
    return await agents_api.get_agent_by_name(mcp_user, name, storage)
