import os
import shutil
import tempfile
from typing import Annotated, List, Optional
from uuid import uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, UploadFile
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, SecretStr

from sema4ai_agent_server.agent import runnable_agent
from sema4ai_agent_server.agent_spec import (
    SpecFile,
    download_agent_package,
    get_knowledge_files,
    get_spec,
    knowledge_dir,
    put_agent_from_spec,
    validate_spec,
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
    RawAgent,
    UploadedFile,
)
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)

router = APIRouter()


class AgentPayload(BaseModel):
    """Payload for creating an agent."""

    public: bool = Field(False, description="Whether the agent is public.")
    name: str = Field(..., description="The name of the agent.")
    description: str = Field(..., description="The description of the agent.")
    runbook: SecretStr = Field(..., description="The runbook for the agent.")
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

    public: bool = Field(True, description="Whether the agent is public.")
    name: str = Field(..., description="The name of the agent.")
    agent_package_url: str = Field(..., description="The URL of the agent package.")
    model: MODEL = Field(..., description="LLM configuration for the agent.")
    action_servers: list[AgentPayloadPackageActionServer] = Field(
        ..., description="Action Server configurations."
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


@router.get("/raw")
async def list_raw_agents(user: AuthedUser) -> List[RawAgent]:
    """List all agents for the current user."""
    agents = await get_storage().list_agents(user.user_id)
    return [agent.raw() for agent in agents]


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


@router.get("/{aid}/raw")
async def get_raw_agent(
    user: AuthedUser,
    aid: AgentID,
) -> RawAgent:
    """Get an agent by ID (sensitive data is masked)."""
    agent = await get_storage().get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.raw()


@router.put("/package/{aid}")
async def upsert_agent_via_package(
    user: AuthedUser,
    aid: AgentID,
    payload: AgentPayloadPackage,
    background_tasks: BackgroundTasks,
) -> Agent:
    root_dir = tempfile.mkdtemp()

    agent = await get_storage().get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        await download_agent_package(root_dir, payload.agent_package_url)
        spec = get_spec(root_dir)
        validate_spec(spec, root_dir, payload.model, payload.action_servers)

        # Using the first action server for now. In the future, Control Room
        # may provide us with a list of multiple action servers.
        action_server_url = (
            payload.action_servers[0].url if payload.action_servers else None
        )
        action_server_api_key = (
            payload.action_servers[0].api_key if payload.action_servers else None
        )

        # Create the agent
        agent = await put_agent_from_spec(
            root_dir=root_dir,
            spec=spec,
            user_id=user.user_id,
            agent_id=agent.id,
            public=payload.public,
            agent_name=payload.name,
            model=payload.model,
            action_server_url=action_server_url,
            action_server_api_key=action_server_api_key,
        )

        existing_files = await get_storage().get_agent_files(agent.id)
        background_tasks.add_task(
            _put_files,
            user,
            agent.id,
            root_dir,
            existing_files,
            get_knowledge_files(spec),
        )

        return agent

    # Not using finally because background task needs to have access to the dir
    except Exception as e:
        shutil.rmtree(root_dir)
        logger.exception("Failed to update agent via package", exception=e)
        raise HTTPException(
            status_code=400, detail=e.detail if isinstance(e, HTTPException) else str(e)
        )


@router.post("/package")
async def create_agent_via_package(
    user: AuthedUser,
    payload: AgentPayloadPackage,
    background_tasks: BackgroundTasks,
) -> Agent:
    root_dir = tempfile.mkdtemp()

    try:
        await download_agent_package(root_dir, payload.agent_package_url)
        spec = get_spec(root_dir)
        validate_spec(spec, root_dir, payload.model, payload.action_servers)

        # Using the first action server for now. In the future, Control Room
        # may provide us with a list of multiple action servers.
        action_server_url = (
            payload.action_servers[0].url if payload.action_servers else None
        )
        action_server_api_key = (
            payload.action_servers[0].api_key if payload.action_servers else None
        )

        # Create the agent
        agent = await put_agent_from_spec(
            root_dir=root_dir,
            spec=spec,
            user_id=user.user_id,
            agent_id=str(uuid4()),
            public=payload.public,
            agent_name=payload.name,
            model=payload.model,
            action_server_url=action_server_url,
            action_server_api_key=action_server_api_key,
        )

        existing_files = []
        background_tasks.add_task(
            _put_files,
            user,
            agent.id,
            root_dir,
            existing_files,
            get_knowledge_files(spec),
        )
        return agent

    # Not using finally because background task needs to have access to the dir
    except Exception as e:
        shutil.rmtree(root_dir)
        logger.exception("Failed to create agent via package", exception=e)
        raise HTTPException(
            status_code=400, detail=e.detail if isinstance(e, HTTPException) else str(e)
        )


async def _put_files(
    user: AuthedUser,
    aid: str,
    root_dir: str,
    existing_files: list[UploadedFile],
    new_files: list[SpecFile],
):
    """
    Given existing files and new files, takes care of ensuring the
    correct state of the agent's knowledge. Files that are in the existing
    and new files are left untouched unless the content has changed (checking
    via digest/file_hash). If they changed, the existing file is deleted and
    the new file is uploaded.
    """
    open_files = []
    try:
        files_to_upload, files_to_delete = get_files_to_upload_and_delete(
            existing_files, new_files
        )
        logger.info(f"Files to delete: {[file.file_ref for file in files_to_delete]}")
        logger.info(f"Files to upload: {[file.name for file in files_to_upload]}")

        for file in files_to_delete:
            await get_file_manager().delete(file.file_id)
            logger.info(f"Deleted file: {file.file_ref}")

        if files_to_upload:
            upload_files: list[UploadFile] = []
            for file in files_to_upload:
                f = open(os.path.join(knowledge_dir(root_dir), file.name), "rb")
                open_files.append(f)
                upload_files.append(UploadFile(filename=file.name, file=f))

            stored_files = await upload_agent_files(upload_files, user, aid)
            logger.info(f"Successfully uploaded files: {stored_files}.")

    except Exception as e:
        await get_storage().update_agent_status(
            user.user_id, aid, AgentStatus.FILE_OPERATIONS_FAILED
        )
        logger.exception("Failed to upload files", exception=e)
    else:
        await get_storage().update_agent_status(user.user_id, aid, AgentStatus.READY)
    finally:
        # Close all opened files and remove the temporary directory
        for f in open_files:
            f.close()
        shutil.rmtree(root_dir)


def get_files_to_upload_and_delete(
    existing_files: list[UploadedFile], new_files: list[SpecFile]
) -> tuple[list[SpecFile], list[UploadedFile]]:
    """
    Compare the existing files with the new files and return a list of files
    to upload and delete.
    """
    files_to_upload: list[SpecFile] = []
    files_to_delete: list[UploadedFile] = []

    existing_dict = {file.file_ref: file for file in existing_files}
    new_dict = {file.name: file for file in new_files}

    # Check for files to upload and update (update means delete old and upload new)
    for name, new_file in new_dict.items():
        if name not in existing_dict:
            # File is completely new, so upload.
            files_to_upload.append(new_file)
        else:
            if new_file.digest != existing_dict[name].file_hash:
                # File has changed, so delete the old version and upload the new one.
                files_to_upload.append(new_file)
                files_to_delete.append(existing_dict[name])

    # Check for files to delete
    for name, existing_file in existing_dict.items():
        if name not in new_dict:
            # File is no longer in the spec, so delete.
            files_to_delete.append(existing_file)

    return files_to_upload, files_to_delete


@router.post("")
async def create_agent(
    user: AuthedUser,
    payload: AgentPayload,
) -> RawAgent:
    """Create an agent."""
    msg = await _generate_welcome_message(user.user_id, payload)

    if msg is not None:
        payload.metadata.welcome_message = msg

    agent = await get_storage().put_agent(
        user.user_id,
        str(uuid4()),
        public=payload.public,
        status=AgentStatus.READY,
        name=payload.name,
        description=payload.description,
        runbook=payload.runbook.get_secret_value(),
        version=payload.version,
        model=payload.model,
        architecture=payload.architecture,
        reasoning=payload.reasoning,
        action_packages=payload.action_packages,
        metadata=payload.metadata,
    )
    return agent.raw()


@router.put("/{aid}")
async def upsert_agent(
    user: AuthedUser,
    aid: AgentID,
    payload: AgentPayload,
) -> RawAgent:
    """Create or update an agent."""
    agent = await get_storage().get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    msg = await _generate_welcome_message(user.user_id, payload)
    if msg is not None:
        payload.metadata.welcome_message = msg

    agent = await get_storage().put_agent(
        user.user_id,
        aid,
        public=payload.public,
        status=AgentStatus.READY,
        name=payload.name,
        description=payload.description,
        runbook=payload.runbook.get_secret_value(),
        version=payload.version,
        model=payload.model,
        architecture=payload.architecture,
        reasoning=payload.reasoning,
        action_packages=payload.action_packages,
        metadata=payload.metadata,
    )
    return agent.raw()


@router.delete("/{aid}")
async def delete_agent(
    user: AuthedUser,
    aid: AgentID,
) -> dict[str, Agent]:
    """Delete an agent by ID."""
    agent = await get_storage().get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    file_manager = get_file_manager()
    files = await get_storage().get_agent_files(aid)
    for file in files:
        await file_manager.delete(file.file_id)

    await get_storage().delete_agent(user.user_id, aid)
    return {"deleted": agent}


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

    file_manager = get_file_manager()
    try:
        stored_files = await _store_files(agent, files, file_manager, agent.model)
    except Exception as e:
        logger.exception("Failed to store a file", exception=e)
        raise HTTPException(status_code=500, detail=f"Failed to store a file: {str(e)}")

    return stored_files
