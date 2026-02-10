import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from jinja2 import Template

if TYPE_CHECKING:
    from agent_platform.core.agent import Agent
    from agent_platform.server.storage.abstract import AbstractStorage

logger = structlog.get_logger(__name__)

SQL_GENERATION_AGENT_DESCRIPTION = "Internal SQL generation agent for semantic data models"
SQL_GENERATION_AGENT_METADATA = {
    "visibility": os.getenv("SQL_AGENT_VISIBILITY", "hidden"),
    "feature": "sql-generation",
}
SQL_GENERATION_AGENT_VERSION = "1.1.0"
SQL_GENERATION_AGENT_ARCHITECTURE = "agent_platform.architectures.experimental_1"
_SQL_GENERATION_AGENT_NAME = "SQL Generation Agent"


def _get_runbook_template_path() -> Path:
    """Resolve the SQL generation runbook template path, handling frozen binaries."""
    from agent_platform.server.constants import IS_FROZEN

    # When frozen (PyInstaller), data files are placed under sys._MEIPASS.
    if IS_FROZEN:
        import sys

        base_dir = Path(sys._MEIPASS) / "agent_platform" / "server" / "sql_generation"  # pyright: ignore[reportAttributeAccessIssue]
        return base_dir / "runbook.md.jinja"

    # Non-frozen: runbook template lives alongside this module in the source tree
    return Path(__file__).parent / "runbook.md.jinja"


def _get_relationships_addon_path() -> Path:
    """Resolve the relationships addon path, handling frozen binaries."""
    from agent_platform.server.constants import IS_FROZEN

    # When frozen (PyInstaller), data files are placed under sys._MEIPASS.
    if IS_FROZEN:
        import sys

        base_dir = Path(sys._MEIPASS) / "agent_platform" / "server" / "sql_generation"  # pyright: ignore[reportAttributeAccessIssue]
        return base_dir / "runbook_relationships_addon.md"

    # Non-frozen: addon lives alongside this module in the source tree
    return Path(__file__).parent / "runbook_relationships_addon.md"


# Runbook template is stored alongside this module and packaged with the server executable
RUNBOOK_TEMPLATE_PATH = _get_runbook_template_path()
RELATIONSHIPS_ADDON_PATH = _get_relationships_addon_path()


def _load_runbook_template() -> Template:
    """Load runbook template from runbook.md.jinja in the sql_generation module."""
    try:
        with open(RUNBOOK_TEMPLATE_PATH, encoding="utf-8") as f:
            return Template(f.read())
    except Exception as e:
        logger.error(f"Failed to load SQL generation agent runbook template: {e}")
        raise


def _load_relationships_addon() -> str:
    """Load relationships addon content from runbook_relationships_addon.md."""
    try:
        with open(RELATIONSHIPS_ADDON_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load SQL generation relationships addon: {e}")
        raise


def _build_sql_generation_agent(user_id: str) -> "Agent":
    """Return the Agent definition for the SQL generation agent.

    Conditionally includes relationship guidance based on SystemConfig.enable_relationship_guidance.
    """
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.runbook import Runbook
    from agent_platform.server.constants import SystemConfig

    runbook_template = _load_runbook_template()

    # Conditionally include relationship guidance if the feature is enabled
    relationships_guidance = ""
    if SystemConfig.enable_relationship_guidance:
        relationships_addon = _load_relationships_addon()
        # Add newlines before and after to maintain proper spacing
        relationships_guidance = f"\n{relationships_addon}\n"

    # Render the template with the relationships guidance (or empty string)
    runbook_text = runbook_template.render(relationships_guidance=relationships_guidance)

    return Agent(
        name=_SQL_GENERATION_AGENT_NAME,
        description=SQL_GENERATION_AGENT_DESCRIPTION,
        user_id=user_id,
        runbook_structured=Runbook(raw_text=runbook_text, content=[]),
        version=SQL_GENERATION_AGENT_VERSION,
        platform_configs=[],
        agent_architecture=AgentArchitecture(name=SQL_GENERATION_AGENT_ARCHITECTURE, version="2.0.0"),
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


async def get_sql_generation_agent(storage: "AbstractStorage | None" = None) -> "Agent | None":
    """Get the preinstalled SQL generation agent.

    Args:
        storage: Optional storage instance. If None, uses the singleton StorageService.

    Returns:
        The SQL generation Agent instance, or None if it does not exist.
    """
    if storage is None:
        from agent_platform.server.storage import StorageService

        storage = StorageService.get_instance()

    # Find all pre-installed agents.
    system_user_id = await _get_preinstalled_agents_system_user_id(storage)
    system_user = await storage.get_user_by_id(system_user_id)

    # Find the SQL generation agent from the agents owned by that pre-installed user.
    system_agents = await storage.list_agents(system_user.user_id)
    agent = next(
        (candidate for candidate in system_agents if candidate.name == _SQL_GENERATION_AGENT_NAME),
        None,
    )

    return agent


def _agent_needs_update(existing: "Agent", desired: "Agent") -> bool:
    """Check if the existing agent differs from the desired specification.

    Note: platform_configs are not compared as they are user/system configured,
    not part of the agent specification.
    """
    return (
        existing.description != desired.description
        or existing.version != desired.version
        or existing.mode != desired.mode
        or existing.extra != desired.extra
        or existing.runbook_structured.raw_text != desired.runbook_structured.raw_text
        or existing.agent_architecture.model_dump() != desired.agent_architecture.model_dump()
    )


async def ensure_sql_generation_agent(storage: "AbstractStorage | None" = None) -> None:
    """Ensure the SQL generation agent exists with the correct settings."""

    if storage is None:
        from agent_platform.server.storage import StorageService

        storage = StorageService.get_instance()

    system_user_id = await _get_preinstalled_agents_system_user_id(storage)
    system_user = await storage.get_user_by_id(system_user_id)

    desired_agent = _build_sql_generation_agent(system_user.user_id)

    # Find the agent by name and user_id
    system_agents = await storage.list_agents(system_user.user_id)
    existing_agent = next(
        (candidate for candidate in system_agents if candidate.name == _SQL_GENERATION_AGENT_NAME),
        None,
    )

    # If agent doesn't exist, create it
    if existing_agent is None:
        await storage.upsert_agent(system_user.user_id, desired_agent)
        logger.info(
            "SQL generation agent created",
            agent_id=desired_agent.agent_id,
            agent_name=desired_agent.name,
            system_user_id=system_user.user_id,
            version=SQL_GENERATION_AGENT_VERSION,
        )
        return

    # If agent exists but needs update, upsert with preserved agent_id and platform_configs
    if _agent_needs_update(existing_agent, desired_agent):
        agent_to_upsert = existing_agent.copy(
            description=desired_agent.description,
            version=desired_agent.version,
            mode=desired_agent.mode,
            extra=desired_agent.extra,
            runbook_structured=desired_agent.runbook_structured,
            agent_architecture=desired_agent.agent_architecture,
            updated_at=datetime.now(UTC),
            # Note: platform_configs are preserved from existing_agent
        )
        await storage.upsert_agent(system_user.user_id, agent_to_upsert)
        logger.info(
            "SQL generation agent updated",
            agent_id=agent_to_upsert.agent_id,
            agent_name=agent_to_upsert.name,
            system_user_id=system_user.user_id,
            version=SQL_GENERATION_AGENT_VERSION,
        )
    else:
        logger.debug(
            "SQL generation agent already up to date",
            agent_id=existing_agent.agent_id,
            agent_name=existing_agent.name,
            system_user_id=system_user.user_id,
            version=SQL_GENERATION_AGENT_VERSION,
        )
