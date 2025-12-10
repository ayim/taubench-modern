from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agent_platform.core.agent import Agent
    from agent_platform.server.storage.abstract import AbstractStorage

logger = structlog.get_logger(__name__)

SQL_GENERATION_AGENT_DESCRIPTION = "Internal SQL generation agent for semantic data models"
SQL_GENERATION_AGENT_METADATA = {
    "visibility": "hidden",
    "feature": "sql-generation",
}
SQL_GENERATION_AGENT_VERSION = "1.0.0"
SQL_GENERATION_AGENT_ARCHITECTURE = "agent_platform.architectures.experimental_1"
_SQL_GENERATION_AGENT_NAME = "SQL Generation Agent"


def _get_runbook_path() -> Path:
    """Resolve the SQL generation runbook path, handling frozen binaries."""
    from agent_platform.server.constants import IS_FROZEN

    # When frozen (PyInstaller), data files are placed under sys._MEIPASS.
    if IS_FROZEN:
        import sys

        base_dir = Path(sys._MEIPASS) / "agent_platform" / "server" / "sql_generation"  # pyright: ignore[reportAttributeAccessIssue]
        return base_dir / "runbook.md"

    # Non-frozen: runbook lives alongside this module in the source tree
    return Path(__file__).parent / "runbook.md"


# Runbook is stored alongside this module and packaged with the server executable
RUNBOOK_PATH = _get_runbook_path()


def _has_required_metadata(candidate_metadata: object) -> bool:
    """Check if candidate metadata contains at least the required entries."""
    if not isinstance(candidate_metadata, dict):
        return False

    return all(
        candidate_metadata.get(key) == value for key, value in SQL_GENERATION_AGENT_METADATA.items()
    )


def _load_runbook() -> str:
    """Load runbook content from runbook.md in the sql_generation module."""
    try:
        with open(RUNBOOK_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load SQL generation agent runbook: {e}")
        raise


def _build_sql_generation_agent(user_id: str) -> "Agent":
    """Return the Agent definition for the SQL generation agent."""
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.runbook import Runbook

    runbook_text = _load_runbook()

    return Agent(
        name=_SQL_GENERATION_AGENT_NAME,
        description=SQL_GENERATION_AGENT_DESCRIPTION,
        user_id=user_id,
        runbook_structured=Runbook(raw_text=runbook_text, content=[]),
        version=SQL_GENERATION_AGENT_VERSION,
        platform_configs=[],
        agent_architecture=AgentArchitecture(
            name=SQL_GENERATION_AGENT_ARCHITECTURE, version="2.0.0"
        ),
        extra={
            "metadata": SQL_GENERATION_AGENT_METADATA.copy(),
            "agent_settings": {
                "enable_sql_generation": True,
                "enable_data_frames": False,
            },
        },
        mode="conversational",
    )


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


async def ensure_sql_generation_agent(storage: "AbstractStorage | None" = None) -> None:
    """Ensure the SQL generation agent exists with the correct settings."""

    if storage is None:
        from agent_platform.server.storage import StorageService

        storage = StorageService.get_instance()

    system_user_id = await _get_preinstalled_agents_system_user_id(storage)
    system_user = await storage.get_user_by_id(system_user_id)

    desired_agent = _build_sql_generation_agent(system_user.user_id)

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

    # If agent exists, preserve its agent_id and name
    if agent is not None:
        agent_to_upsert = agent.copy(
            description=SQL_GENERATION_AGENT_DESCRIPTION,
            platform_configs=[],
            agent_architecture=desired_agent.agent_architecture,
            extra=desired_agent.extra,
            mode="conversational",
            version=SQL_GENERATION_AGENT_VERSION,
            updated_at=datetime.now(UTC),
        )
    else:
        agent_to_upsert = desired_agent

    await storage.upsert_agent(system_user.user_id, agent_to_upsert)
    logger.info(
        "SQL generation agent is updated",
        agent_id=agent_to_upsert.agent_id,
        agent_name=agent_to_upsert.name,
        system_user_id=system_user.user_id,
        version=SQL_GENERATION_AGENT_VERSION,
        existed=agent is not None,
    )
