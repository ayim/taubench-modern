from agent_platform.core.actions.action_package import (
    ActionPackage,
)
from agent_platform.core.agent import AgentArchitecture
from agent_platform.core.agent_spec.extract_spec import (
    extract_and_validate_agent_package,
)
from agent_platform.core.payloads import (
    AgentPackagePayload,
    UpsertAgentPayload,
)
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.tools_caching import ToolDefinitionCache


async def create_or_update_agent_from_package(
    user: AuthedUser,
    aid: str,
    payload: AgentPackagePayload,
    storage: StorageDependency,
) -> AgentCompat:
    # We do a 3 step dance here: wetake the payload, and extract the agent
    # spec and runbook from it (and knowledge files... but ignore those for now)
    agent_package = await extract_and_validate_agent_package(
        path=None,  # No local path option here: either URL or base64
        url=payload.agent_package_url,
        package_base64=payload.agent_package_base64,
        include_knowledge=False,
        knowledge_return="stream",
    )
    # The spec _must_ be the v2 agent spec; which represents "v1 agents"
    # from our perspective. So we use UpsertAgentPayload to re-use our
    # legacy conversion logic and get a "v2 agent" out of it.
    agent0 = agent_package.spec["agent-package"]["agents"][0]

    # Bring over langsmith config from payload
    advanced_config = {}
    if payload.langsmith:
        advanced_config["langsmith"] = payload.langsmith.model_dump()

    # Bring over action server config from payload (if it's there)
    # NOTE: just as in v1 code, we only can take the first action server
    # here (seems the idea of having multiple was never used...)
    action_server_url = None
    action_server_api_key = None
    if len(payload.action_servers) > 0:
        action_server_url = payload.action_servers[0].url
        action_server_api_key = payload.action_servers[0].api_key
    if isinstance(action_server_api_key, str):
        action_server_api_key = SecretString(action_server_api_key)

    as_upsert_payload = UpsertAgentPayload(
        name=payload.name,  # Want name from payload, not agent project
        description=payload.description
        if payload.description is not None
        else agent0.get("description", ""),
        version=agent0.get("version", "1.0.0"),
        action_packages=[
            ActionPackage(
                name=action_package["name"],
                organization=action_package["organization"],
                version=action_package["version"],
                url=action_server_url,
                api_key=action_server_api_key,
            )
            for action_package in agent0.get("action-packages", [])
        ],
        mcp_servers=payload.mcp_servers,
        runbook=agent_package.runbook_text,
        advanced_config=advanced_config,
        question_groups=agent_package.question_groups,
        agent_settings=agent_package.agent_settings or {},
        extra={
            "conversation_starter": agent_package.conversation_starter,
            "welcome_message": agent_package.welcome_message,
            "agent_settings": agent_package.agent_settings,
        },
        model=payload.model,
        agent_architecture=AgentArchitecture(
            # Doesn't matter what we were given, all legacy architectures
            # get mapped to default for v2 & v3
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
        metadata={
            **agent0.get("metadata", {}),
        },
    )

    # Now, for the third and final step, we have essentially a normal
    # agent create (just as the upsert_agent endpoint does)
    as_agent = UpsertAgentPayload.to_agent(
        payload=as_upsert_payload,
        agent_id=aid,
        user_id=user.user_id,
    )
    await storage.upsert_agent(user.user_id, as_agent)
    # We might technically clear on a create here, which shouldn't be
    # problem (even if it's not strictly necessary)
    ToolDefinitionCache().clear_for_agent(as_agent)
    return AgentCompat.from_agent(as_agent)
