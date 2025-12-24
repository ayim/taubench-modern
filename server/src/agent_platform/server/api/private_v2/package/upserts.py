import copy

from fastapi import HTTPException
from starlette import status
from structlog import get_logger

from agent_platform.core.actions import ActionPackage
from agent_platform.core.agent import AgentArchitecture
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.read import read_agent_package
from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.payloads import AgentPackagePayload, UpsertAgentPayload
from agent_platform.core.selected_tools import SelectedTools
from agent_platform.core.telemetry.otel_orchestrator import OtelOrchestrator
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.api.private_v2.package.payload_utils import (
    find_matching_sdm,
    resolve_data_connection_names,
)
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.tools_caching import ToolDefinitionCache
from agent_platform.server.storage import AgentNotFoundError

logger = get_logger(__name__)


async def upsert_agent_from_package(
    user: AuthedUser,
    aid: str,
    payload: AgentPackagePayload,
    storage: StorageDependency,
    handler: AgentPackageHandler | None = None,
) -> AgentCompat:
    # This handles the cases from /agents/package endpoints - they never
    # provide ZIP file and always rely on URL/base64 representation.
    if handler is None:
        if payload.agent_package_base64:
            handler = await AgentPackageHandler.from_base64(payload.agent_package_base64)
        elif payload.agent_package_url:
            handler = await AgentPackageHandler.from_url(payload.agent_package_url)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Package URL or base64 provided")

    # TODO (agent-cli sunset):
    # Langsmith support for Package import should most likely be dropped.
    advanced_config = {}
    if payload.langsmith is not None:
        advanced_config["langsmith"] = payload.langsmith.model_dump()

    # Bring over action server config from payload (if it's there)
    # NOTE: just as in v1 code, we only can take the first action server
    # here (seems the idea of having multiple was never used...)
    action_server_url = None
    action_server_api_key = None

    if payload.action_servers:
        action_server_url = payload.action_servers[0].url
        action_server_api_key = payload.action_servers[0].api_key
    if isinstance(action_server_api_key, str):
        action_server_api_key = SecretString(action_server_api_key)

    with handler:
        read_package_result = await read_agent_package(handler)

        spec_agent = read_package_result.spec_agent

        # Original architecture name (if not present, use default)
        mapped_architecture_name = spec_agent.architecture or "agent_platform.architectures.default"
        if not mapped_architecture_name.startswith("agent_platform.architectures."):
            # If we have any legacy value, use default
            mapped_architecture_name = "agent_platform.architectures.default"

        # Reading selected tools from AgentSpec.
        spec_selected_tools = spec_agent.selected_tools
        selected_tools = spec_selected_tools.to_selected_tools() if spec_selected_tools else SelectedTools()

        as_upsert_payload = UpsertAgentPayload(  # type: ignore[call-arg]
            name=payload.name,  # Want name from payload, not agent project
            description=payload.description if payload.description is not None else spec_agent.description,
            version=spec_agent.version or "1.0.0",
            action_packages=[
                ActionPackage(
                    name=action_package.name,
                    organization=action_package.organization,
                    version=action_package.version,
                    url=action_server_url,
                    api_key=action_server_api_key,
                )
                for action_package in spec_agent.action_packages
            ],
            mcp_servers=payload.mcp_servers,
            mcp_server_ids=payload.mcp_server_ids,
            selected_tools=selected_tools,
            platform_params_ids=payload.platform_params_ids,
            runbook=read_package_result.runbook,
            advanced_config=advanced_config,
            question_groups=read_package_result.question_groups,
            agent_settings=spec_agent.agent_settings or {},
            extra={
                "conversation_starter": spec_agent.conversation_starter,
                "welcome_message": spec_agent.welcome_message,
                "agent_settings": spec_agent.agent_settings,
            },
            model=payload.model,
            agent_architecture=AgentArchitecture(
                # Take architecture name from package, force
                # version to 1.0.0 (we don't support arch versioning yet
                # across the stack)
                name=mapped_architecture_name,
                version="1.0.0",
            ),
            metadata={
                **(spec_agent.metadata.model_dump(exclude_none=True) if spec_agent.metadata is not None else {}),
            },
            document_intelligence=spec_agent.document_intelligence,
        )

    # Now, for the third and final step, we have essentially a normal
    # agent create (just as the upsert_agent endpoint does)
    try:
        existing_agent = await storage.get_agent(user.user_id, aid)
    except AgentNotFoundError:
        existing_agent = None

    as_agent = UpsertAgentPayload.to_agent(
        payload=as_upsert_payload,
        agent_id=aid,
        user_id=user.user_id,
        existing_agent=existing_agent,
    )
    await storage.upsert_agent(user.user_id, as_agent)

    # Reload orchestrator to include new/updated agent in routing map
    orchestrator = OtelOrchestrator.get_instance()
    await orchestrator.reload_from_storage(storage)
    logger.info(f"Reloaded orchestrator after creating/updating agent {aid} from package")

    # We might technically clear on a create here, which shouldn't be
    # problem (even if it's not strictly necessary)
    ToolDefinitionCache().clear_for_agent(as_agent)

    # We've written this Agent to storage. If we get an error after this point, we have
    # to clean up after ourselves.
    try:
        # Import semantic data models if present in the package
        await upsert_semantic_data_models(
            agent_id=aid,
            sdms=read_package_result.semantic_data_models_map,
            storage=storage,
        )

        return AgentCompat.from_agent(as_agent)
    except Exception as e:
        # Try to restore the original agent def'n if it existed prior (update case)
        if existing_agent:
            try:
                await storage.upsert_agent(user.user_id, existing_agent)
            except Exception as e2:
                logger.exception("Failed to restore original agent after failed update.", agent_id=aid, error=e2)
                # fall through to raise the original error
        else:
            # Delete the agent if it didn't exist prior (create case)
            try:
                await storage.delete_agent(user.user_id, aid)
            except Exception as e2:
                logger.exception("Failed to delete agent during cleanup. Agent is orphaned!", agent_id=aid, error=e2)
                # fall through to raise the original error

        raise e


async def upsert_semantic_data_models(
    agent_id: str,
    sdms: dict[str, SemanticDataModel],
    storage: StorageDependency,
) -> None:
    """
    Import semantic data models from agent package with deduplication.

    Mode: Additive - preserves existing SDMs and adds new ones.

    Args:
        agent_id: ID of the agent to link SDMs to
        sdms: Dictionary of SDM filename to content (or None if no SDMs)
        storage: Storage dependency
    """
    if not sdms:
        logger.info(f"No SDMs to import for agent {agent_id}")
        return

    logger.info(f"Importing {len(sdms)} SDMs for agent {agent_id}", agent_id=agent_id)

    # Get existing SDMs for this agent
    existing_sdms = await storage.get_agent_semantic_data_models(agent_id)

    # Track which SDM IDs to link (existing + new)
    sdm_ids_to_link = []

    # Keep existing SDM IDs (additive mode)
    existing_ids = [next(iter(sdm_entry.keys())) for sdm_entry in existing_sdms]
    sdm_ids_to_link.extend(existing_ids)
    logger.info(f"Keeping {len(existing_ids)} existing SDMs", count=len(existing_ids))

    # Process each SDM from package
    for filename, sdm_instance in sdms.items():
        # Resolve data connection names to IDs (if possible)
        sdm_resolved = await resolve_data_connection_names(sdm_instance, storage)

        # Check for match (find_matching_sdm uses class methods for normalization)
        matching_id = find_matching_sdm(sdm_resolved, existing_sdms)

        if matching_id:
            logger.info(
                f"Reusing existing SDM {matching_id} for {filename}",
                sdm_id=matching_id,
                sdm_filename=filename,
            )
            # Don't add to list if already there (from additive mode)
            if matching_id not in sdm_ids_to_link:
                sdm_ids_to_link.append(matching_id)
        else:
            # Prepare SDM for storage: keep data_connection_id, remove data_connection_name
            sdm_for_storage = copy.deepcopy(sdm_resolved)
            for table in sdm_for_storage.get("tables", []):
                if "base_table" in table:
                    base_table = table["base_table"]
                    # Only remove data_connection_name if data_connection_id was resolved.
                    # If data_connection_id is missing but name exists, keep the name
                    # so validation can report the unresolved connection as an error.
                    if base_table.get("data_connection_id"):
                        base_table.pop("data_connection_name", None)

            # Extract data connection IDs from resolved SDM (for junction table)
            data_connection_ids = []
            for table in sdm_resolved.get("tables", []):
                base_table = table.get("base_table", {})
                if "data_connection_id" in base_table:
                    dc_id = base_table["data_connection_id"]
                    if dc_id and dc_id not in data_connection_ids:
                        data_connection_ids.append(dc_id)

            # Create new SDM
            # Note: We store sdm_for_storage which has data_connection_id (for querying)
            # The junction table also stores the IDs for reference
            new_id = await storage.set_semantic_data_model(
                semantic_data_model_id=None,
                semantic_model=sdm_for_storage,
                data_connection_ids=data_connection_ids,
                file_references=[],
            )
            logger.info(
                f"Created new SDM {new_id} for {filename}",
                sdm_id=new_id,
                sdm_filename=filename,
                sdm_name=sdm_for_storage.get("name", ""),
                data_connection_count=len(data_connection_ids),
            )
            sdm_ids_to_link.append(new_id)

    # Link all SDMs to agent
    if sdm_ids_to_link:
        await storage.set_agent_semantic_data_models(agent_id, sdm_ids_to_link)
        logger.info(
            f"Linked {len(sdm_ids_to_link)} SDMs to agent {agent_id}",
            agent_id=agent_id,
            sdm_count=len(sdm_ids_to_link),
        )
