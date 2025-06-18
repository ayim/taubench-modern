"""Workitems service."""

__version__ = "0.1.0"

from .agents import AgentClient, AgentInfo, FastAPIAgentClient
from .lifecycle import make_workitems_app
from .main import main

__all__ = [
    "AgentClient",
    "AgentInfo",
    "FastAPIAgentClient",
    "main",
    "make_workitems_app",
]
