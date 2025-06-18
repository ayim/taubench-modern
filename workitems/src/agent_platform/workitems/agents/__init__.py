"""
Agent-related functionality for the workitems service.

This package contains the AgentClient interface and implementations
for validating agent existence when creating work items.
"""

from .client import AgentClient, AgentInfo, FastAPIAgentClient

__all__ = [
    "AgentClient",
    "AgentInfo",
    "FastAPIAgentClient",
]
