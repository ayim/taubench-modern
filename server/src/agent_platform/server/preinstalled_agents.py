from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from agent_platform.core.agent import Agent
    from agent_platform.server.storage.abstract import AbstractStorage

logger = structlog.get_logger(__name__)

PREINSTALLED_AGENT_DESCRIPTION = "Internal zero-config agent."
PREINSTALLED_AGENT_METADATA = {"project": "violet", "visibility": "hidden"}
PREINSTALLED_AGENT_VERSION = "1.0.1"
PREINSTALLED_AGENT_ARCHITECTURE = "agent_platform.architectures.experimental_3"
_PREINSTALLED_AGENT_NAME_PREFIX = "My Associate ["


def _has_required_metadata(candidate_metadata: object) -> bool:
    """Check if candidate metadata contains at least the required entries."""
    if not isinstance(candidate_metadata, dict):
        return False

    return all(
        candidate_metadata.get(key) == value for key, value in PREINSTALLED_AGENT_METADATA.items()
    )


def _merge_required_metadata(candidate_metadata: object) -> dict[str, object]:
    """Return metadata containing the required entries, preserving any extras."""
    merged_metadata: dict[str, object]
    if isinstance(candidate_metadata, dict):
        merged_metadata = dict(candidate_metadata)
    else:
        merged_metadata = {}

    merged_metadata.update(PREINSTALLED_AGENT_METADATA)
    return merged_metadata


def _build_preinstalled_agent(user_id: str, *, name: str | None = None) -> "Agent":
    """Return the Agent definition for the pre-installed system agent."""
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.runbook import Runbook

    return Agent(
        name=name or f"{_PREINSTALLED_AGENT_NAME_PREFIX}{uuid4()}]",
        description=PREINSTALLED_AGENT_DESCRIPTION,
        user_id=user_id,
        runbook_structured=Runbook(raw_text="You are a helpful assistant.", content=[]),
        version=PREINSTALLED_AGENT_VERSION,
        platform_configs=[],
        agent_architecture=AgentArchitecture(name=PREINSTALLED_AGENT_ARCHITECTURE, version="2.0.0"),
        extra={"metadata": PREINSTALLED_AGENT_METADATA.copy()},
        mode="conversational",
    )


def _is_desired_version_newer(current_version: str, desired_version: str) -> bool:
    """Return True if the desired version is newer than the current one."""
    from packaging.version import InvalidVersion, Version

    try:
        return Version(desired_version) > Version(current_version)
    except InvalidVersion:
        logger.warning(
            "Unable to compare pre-installed agent versions",
            current_version=current_version,
            desired_version=desired_version,
        )
        return desired_version != current_version


async def _get_preinstalled_agents_system_user_id(storage: "AbstractStorage") -> str:
    """Get or create the system user for preinstalled agents."""
    from agent_platform.server.constants import PREINSTALLED_AGENTS_SYSTEM_USER_SUB
    from agent_platform.server.storage.errors import NoSystemUserError

    try:
        return await storage.get_system_user_id()
    except NoSystemUserError:
        system_user, _ = await storage.get_or_create_user(
            sub=PREINSTALLED_AGENTS_SYSTEM_USER_SUB,
        )
        logger.info(f"Created system user {system_user.user_id}")
        return system_user.user_id


async def ensure_preinstalled_agents(storage: "AbstractStorage | None" = None) -> None:
    """Ensure required pre-installed agents exist with the correct settings."""

    if storage is None:
        from agent_platform.server.storage import StorageService

        storage = StorageService.get_instance()

    system_user_id = await _get_preinstalled_agents_system_user_id(storage)
    system_user = await storage.get_user_by_id(system_user_id)

    desired_agent = _build_preinstalled_agent(system_user.user_id)

    system_agents = await storage.list_agents(system_user.user_id)
    agent = next(
        (
            candidate
            for candidate in system_agents
            if candidate.user_id == system_user.user_id
            and _has_required_metadata((candidate.extra or {}).get("metadata"))
        ),
        None,
    )

    if agent is None:
        await storage.upsert_agent(system_user.user_id, desired_agent)
        logger.info(
            "Created pre-installed agent",
            agent_id=desired_agent.agent_id,
            agent_name=desired_agent.name,
            system_user_id=system_user.user_id,
            metadata=PREINSTALLED_AGENT_METADATA,
        )
        return

    updated_extra = dict(agent.extra or {})
    needs_update = False
    update_reasons: list[str] = []
    updated_name = agent.name
    updated_version = agent.version

    # Metadata has to be there and consistent with the desired metadata
    existing_metadata = updated_extra.get("metadata")
    if not _has_required_metadata(existing_metadata):
        updated_extra["metadata"] = _merge_required_metadata(existing_metadata)
        needs_update = True
        update_reasons.append("metadata")

    # For everything else, you should be bumping the version to get
    # other changes to take effect.
    if _is_desired_version_newer(agent.version, desired_agent.version):
        updated_version = desired_agent.version
        needs_update = True
        update_reasons.append("version")

    if not needs_update:
        logger.info(
            "Pre-installed agent already up-to-date",
            agent_id=agent.agent_id,
            system_user_id=system_user.user_id,
        )
        return

    updated_agent = agent.copy(
        description=PREINSTALLED_AGENT_DESCRIPTION,
        platform_configs=[],
        agent_architecture=desired_agent.agent_architecture,
        extra=updated_extra,
        mode="conversational",
        name=updated_name,
        version=updated_version,
        updated_at=datetime.now(UTC),
    )
    await storage.upsert_agent(system_user.user_id, updated_agent)
    logger.info(
        "Updated pre-installed agent",
        agent_id=updated_agent.agent_id,
        agent_name=updated_name,
        system_user_id=system_user.user_id,
        reasons=update_reasons,
    )
