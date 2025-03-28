"""This module manages agent architecture plugins and creates an Enum to
be used as part of the Agent models.
"""

from importlib.metadata import entry_points
from typing import Type

import structlog
from agent_architecture import AgentArchitectureBase

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def load_agent_architectures() -> dict[str, Type[AgentArchitectureBase]]:
    architectures = {}
    for entry_point in entry_points(group="agent_architectures"):
        logger.info(f"Loading agent architecture {entry_point.name}")
        try:
            architecture_class = entry_point.load()
            architectures[entry_point.name] = architecture_class
        except Exception as e:
            logger.exception(
                f"Error loading agent architecture {entry_point.name}: {e}"
            )
    return architectures


# Global instance
_agent_architectures: dict[str, Type[AgentArchitectureBase]] | None = None


def get_agent_architectures() -> dict[str, Type[AgentArchitectureBase]]:
    """Get the global agent architectures dictionary.

    If architectures haven't been loaded yet, they will be loaded on first call.

    Returns:
        Dictionary mapping architecture names to their implementation classes.
    """
    global _agent_architectures

    if _agent_architectures is None:
        logger.info("Loading agent architectures")
        _agent_architectures = load_agent_architectures()
        logger.info(f"Loaded {len(_agent_architectures)} agent architectures")

    return _agent_architectures
