"""This module manages agent architecture plugins and creates an Enum to
be used as part of the Agent models.
"""

from importlib.metadata import entry_points
from typing import Type

from agent_architecture import AgentArchitectureBase


def load_agent_architectures() -> dict[str, Type[AgentArchitectureBase]]:
    architectures = {}
    for entry_point in entry_points(group="agent_architectures"):
        architecture_class = entry_point.load()
        architectures[entry_point.name] = architecture_class
    return architectures


# Load plugins at module import time
agent_architectures = load_agent_architectures()
architecture_names = list(agent_architectures.keys())
