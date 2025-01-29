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
            logger.error(f"Error loading agent architecture {entry_point.name}: {e}")
    return architectures


# Load plugins at module import time
logger.info("Loading agent architectures")
agent_architectures = load_agent_architectures()
architecture_names = list(agent_architectures.keys())
logger.info(f"Loaded {len(architecture_names)} agent architectures")
