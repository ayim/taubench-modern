import os
import shutil
import subprocess
import tempfile
from typing import Annotated, List, Optional
from uuid import uuid4

import aiohttp
import structlog
import yaml
from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, UploadFile
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, validator

from sema4ai_agent_server.agent import runnable_agent
from sema4ai_agent_server.agent_spec import (
    create_agent_from_spec,
    spec_contains_knowledge,
)
from sema4ai_agent_server.api.files import _store_files
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.file_manager.option import get_file_manager
from sema4ai_agent_server.schema import (
    MODEL,
    ActionPackage,
    Agent,
    AgentArchitecture,
    AgentMetadata,
    AgentReasoning,
    AgentStatus,
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
    version: str = Field(..., description="The version of the agent.")
    model: MODEL = Field(..., description="LLM model configuration for the agent.")
    architecture: AgentArchitecture = Field(
        description="The cognitive architecture of the agent."
    )
    reasoning: AgentReasoning = Field(description="The reasoning setting of the agent.")
    action_packages: list[ActionPackage] = Field(
        default=[], description="The action packages for the agent."
    )
    metadata: AgentMetadata = Field(
        ..., description="Additional metadata for the agent."
    )


class AgentPayloadPackageActionServer(BaseModel):
    url: str = Field(..., description="The URL of action server.")
    api_key: str = Field(..., description="The API key of action server.")


class AgentPayloadPackage(BaseModel):
    """Payload for creating an agent via package."""

    name: str = Field(..., description="The name of the agent.")
    agent_package_url: str = Field(..., description="The URL of the agent package.")
    model: MODEL = Field(..., description="LLM configuration for the agent.")
    action_servers: list[AgentPayloadPackageActionServer] = Field(
        ..., description="Action Server configurations."
    )

    @validator("action_servers")
    def validate_action_servers(cls, v):
        if not v:
            raise ValueError("At least one action server must be provided.")
        return v


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


@router.post("/package")
async def create_agent_via_package(
    user: AuthedUser,
    payload: AgentPayloadPackage,
    background_tasks: BackgroundTasks,
) -> Agent:
    root_dir = tempfile.mkdtemp()

    try:
        # Download the agent package
        package_path = os.path.join(root_dir, "agent_package.zip")
        async with aiohttp.ClientSession() as session:
            async with session.get(payload.agent_package_url) as resp:
                if resp.status == 200:
                    with open(package_path, "wb") as f:
                        f.write(await resp.read())
                else:
                    raise HTTPException(
                        status_code=400, detail="Failed to download agent package"
                    )

        # Extract the agent package
        output_path = os.path.join(root_dir, "output")
        subprocess.run(
            [
                "agent-cli",
                "package",
                "extract",
                "--package",
                package_path,
                "--output-dir",
                output_path,
            ],
            check=True,
        )
        with open(os.path.join(output_path, "agent-spec.yaml"), "r") as f:
            spec = yaml.safe_load(f)

        # Create the agent
        agent = await create_agent_from_spec(
            spec=spec,
            user_id=user.user_id,
            agent_name=payload.name,
            model=payload.model,
            action_server_url=payload.action_servers[0].url,
            action_server_api_key=payload.action_servers[0].api_key,
        )

        # Upload knowledge files in the background if the agent has knowledge
        if spec_contains_knowledge(spec):
            logger.info("Uploading knowledge files.")
            knowledge_dir = os.path.join(output_path, "knowledge")
            background_tasks.add_task(
                _upload_knowledge_files, user, agent.id, root_dir, knowledge_dir
            )
        else:
            logger.info("No knowledge files to upload. Skipping.")
            shutil.rmtree(root_dir)

        return agent

    # Not using finally because background task needs to have access to the dir
    except Exception as e:
        shutil.rmtree(root_dir)
        logger.exception("Failed to create agent via package", exception=e)
        raise HTTPException(status_code=400, detail=str(e))


async def _upload_knowledge_files(
    user: AuthedUser, aid: str, root_dir: str, knowledge_dir: str
):
    open_files = []
    try:
        upload_files = []
        for root, _, files in os.walk(knowledge_dir):
            for file in files:
                f = open(os.path.join(root, file), "rb")
                open_files.append(f)
                upload_files.append(UploadFile(filename=file, file=f))

        stored_files = await upload_agent_files(upload_files, user, aid)
        logger.info(f"Successfully uploaded files: {stored_files}.")
    except Exception as e:
        await get_storage().update_agent_status(
            user.user_id, aid, AgentStatus.FILE_UPLOADS_FAILED
        )
        logger.exception("Failed to upload files", exception=e)
    else:
        await get_storage().update_agent_status(user.user_id, aid, AgentStatus.READY)
    finally:
        # Close all opened files and remove the temporary directory
        for f in open_files:
            f.close()
        shutil.rmtree(root_dir)


@router.post("")
async def create_agent(
    user: AuthedUser,
    payload: AgentPayload,
) -> Agent:
    """Create an agent."""
    msg = await _generate_welcome_message(user.user_id, payload)

    if msg is not None:
        payload.metadata.welcome_message = msg

    return await get_storage().put_agent(
        user.user_id,
        str(uuid4()),
        status=AgentStatus.READY,
        name=payload.name,
        description=payload.description,
        runbook=payload.runbook,
        version=payload.version,
        model=payload.model,
        architecture=payload.architecture,
        reasoning=payload.reasoning,
        action_packages=payload.action_packages,
        metadata=payload.metadata,
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
    if msg is not None:
        payload.metadata.welcome_message = msg

    return await get_storage().put_agent(
        user.user_id,
        aid,
        status=AgentStatus.READY,
        name=payload.name,
        description=payload.description,
        runbook=payload.runbook,
        version=payload.version,
        model=payload.model,
        architecture=payload.architecture,
        reasoning=payload.reasoning,
        action_packages=payload.action_packages,
        metadata=payload.metadata,
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
