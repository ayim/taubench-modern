from typing import Annotated, List, Optional
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Path, UploadFile
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from sema4ai_agent_server.agent import runnable_agent
from sema4ai_agent_server.api.files import _store_files
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.file_manager.option import get_file_manager
from sema4ai_agent_server.schema import (
    MODEL,
    ActionPackage,
    Agent,
    AgentArchitecture,
    AgentReasoning,
    UploadedFile,
)
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)

router = APIRouter()


class AgentPayload(BaseModel):
    """Payload for creating an agent."""

    name: str = Field(..., description="The name of the agent.")
    description: str = Field(..., description="The description of the agent.")
    runbook: str = Field(..., description="The runbook for the agent.")
    model: MODEL = Field(..., description="LLM model configuration for the agent.")
    architecture: AgentArchitecture = Field(
        description="The cognitive architecture of the agent."
    )
    reasoning: AgentReasoning = Field(description="The reasoning setting of the agent.")
    action_packages: list[ActionPackage] = Field(
        default=[], description="The action packages for the agent."
    )
    metadata: Optional[dict] = Field(
        default=None, description="Additional metadata for the agent."
    )


AgentID = Annotated[str, Path(description="The ID of the agent.")]


async def _generate_welcome_message(
    user_id: str, payload: AgentPayload
) -> Optional[str]:
    thread = await get_storage().put_thread(
        user_id, str(uuid4()), agent_id=None, name="", metadata=None
    )
    config = {
        "configurable": {
            "thread_id": thread.thread_id,
            "model": payload.model,
            "type": AgentArchitecture.AGENT.value,
        }
    }
    human_prompt = (
        "Introduce yourself as a Sema4.ai Agent and tell me what you're capable of."
    )
    input = {"messages": [HumanMessage(content=human_prompt, id=str(uuid4()))]}

    try:
        response = await runnable_agent.ainvoke(input, config)
    except Exception:
        welcome_message = None
        logger.exception("Failed to generate welcome message.")
    else:
        welcome_message = response["messages"][1].content
    finally:
        await get_storage().delete_thread(thread.user_id, thread.thread_id)

    return welcome_message


@router.get("/")
async def list_agents(user: AuthedUser) -> List[Agent]:
    """List all agents for the current user."""
    agents = await get_storage().list_agents(user.user_id)
    return agents


@router.get("/{aid}")
async def get_agent(
    user: AuthedUser,
    aid: AgentID,
) -> Agent:
    """Get an agent by ID."""
    agent = await get_storage().get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("")
async def create_agent(
    user: AuthedUser,
    payload: AgentPayload,
) -> Agent:
    """Create an agent."""
    msg = await _generate_welcome_message(user.user_id, payload)

    metadata = payload.metadata or {}
    if msg is not None:
        metadata["welcome_message"] = msg

    return await get_storage().put_agent(
        user.user_id,
        str(uuid4()),
        name=payload.name,
        description=payload.description,
        runbook=payload.runbook,
        model=payload.model,
        architecture=payload.architecture,
        reasoning=payload.reasoning,
        action_packages=payload.action_packages,
        metadata=metadata,
    )


@router.put("/{aid}")
async def upsert_agent(
    user: AuthedUser,
    aid: AgentID,
    payload: AgentPayload,
) -> Agent:
    """Create or update an agent."""
    agent = await get_storage().get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    msg = await _generate_welcome_message(user.user_id, payload)
    metadata = agent.metadata or {}
    if msg is not None:
        metadata["welcome_message"] = msg

    # Update metadata with payload metadata
    if payload.metadata:
        metadata.update(payload.metadata)

    return await get_storage().put_agent(
        user.user_id,
        aid,
        name=payload.name,
        description=payload.description,
        runbook=payload.runbook,
        model=payload.model,
        architecture=payload.architecture,
        reasoning=payload.reasoning,
        action_packages=payload.action_packages,
        metadata=metadata,
    )


@router.delete("/{aid}")
async def delete_agent(
    user: AuthedUser,
    aid: AgentID,
):
    """Delete an agent by ID."""
    await get_storage().delete_agent(user.user_id, aid)
    return {"status": "ok"}


@router.get("/{aid}/files")
async def get_agent_files(
    user: AuthedUser,
    aid: AgentID,
) -> List[UploadedFile]:
    """Get an list of files associated with an agent."""
    agent = await get_storage().get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await get_storage().get_agent_files(aid)


@router.post("/{aid}/files")
async def upload_agent_files(
    files: list[UploadFile],
    user: AuthedUser,
    aid: AgentID,
) -> List[UploadedFile]:
    """Upload files to the given agent."""

    agent = await get_storage().get_agent(user.user_id, aid)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    file_manager = get_file_manager(agent.model)
    try:
        stored_files = await _store_files(agent, files, file_manager)
    except Exception as e:
        logger.exception("Failed to store a file", exception=e)
        raise HTTPException(status_code=500, detail=f"Failed to store a file: {str(e)}")

    return stored_files
