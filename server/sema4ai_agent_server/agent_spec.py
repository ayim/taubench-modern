from typing import Optional
from uuid import uuid4

from pydantic import parse_obj_as

from sema4ai_agent_server.schema import (
    MODEL,
    ActionPackage,
    Agent,
    AgentMetadata,
    AgentStatus,
)
from sema4ai_agent_server.storage.option import get_storage


async def create_agent_from_spec(
    *,
    spec: dict,
    user_id: str,
    agent_name: str,
    model: MODEL,
    action_server_url: Optional[str],
    action_server_api_key: Optional[str],
) -> Agent:
    agent = _replace_dashes_with_underscores(spec["agent-package"]["agents"][0])

    if agent["action_packages"] and (
        action_server_url is None or action_server_api_key is None
    ):
        raise Exception("Action server URL and API key are required")

    action_packages = []
    for action_package in agent["action_packages"]:
        action_packages.append(
            ActionPackage(
                name=action_package["name"],
                organization=action_package["organization"],
                version=action_package["version"],
                whitelist=action_package["whitelist"],
                api_key=action_server_api_key,
                url=action_server_url,
            )
        )

    # Create the agent
    return await get_storage().put_agent(
        user_id,
        str(uuid4()),
        status=AgentStatus.FILE_UPLOADS_IN_PROGRESS
        if agent["knowledge"]
        else AgentStatus.READY,
        name=agent_name,
        description=agent["description"],
        runbook=agent["runbook"],
        version=agent["version"],
        model=parse_obj_as(MODEL, model),
        architecture=agent["architecture"],
        reasoning=agent["reasoning"],
        action_packages=parse_obj_as(list[ActionPackage], action_packages),
        metadata=parse_obj_as(AgentMetadata, agent["metadata"]),
    )


def validate_spec(spec: dict, model: MODEL) -> None:
    if spec["agent-package"]["spec-version"] != "v2":
        raise Exception("Only v2 spec version is supported")
    if len(spec["agent-package"]["agents"]) != 1:
        raise Exception("Only one agent is supported")

    expected_provider = spec["agent-package"]["agents"][0]["model"]["provider"]
    expected_name = spec["agent-package"]["agents"][0]["model"]["name"]
    if model.provider != expected_provider or model.name != expected_name:
        raise Exception(
            f"Model mismatch. Expected: {expected_provider}/{expected_name}",
        )


def spec_contains_knowledge(spec: dict) -> bool:
    return len(spec["agent-package"]["agents"][0]["knowledge"]) > 0


def spec_contains_action_packages(spec: dict) -> bool:
    return len(spec["agent-package"]["agents"][0]["action-packages"]) > 0


def _replace_dashes_with_underscores(spec: dict) -> dict:
    def recursive_replace(d):
        if isinstance(d, dict):
            return {k.replace("-", "_"): recursive_replace(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [recursive_replace(item) for item in d]
        else:
            return d

    return recursive_replace(spec)
