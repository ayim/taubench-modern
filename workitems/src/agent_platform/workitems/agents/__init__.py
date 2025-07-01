"""
Agent-related functionality for the workitems service.

This package contains the AgentClient interface and implementations
for validating agent existence when creating work items.
"""

import logging

from fastapi import FastAPI

from .client import AgentClient, AgentInfo, FastAPIAgentClient, HttpAgentClient

logger = logging.getLogger(__name__)


def create_agent_client(app: FastAPI) -> AgentClient:
    agent_app = app.state.agent_app if hasattr(app.state, "agent_app") else None
    if agent_app is None:
        url = app.state.agent_server_url if hasattr(app.state, "agent_server_url") else None
        if url is None:
            raise ValueError("agent_app or agent_server_url is required")
        logger.info(f"Using agent server url over HTTP: {url}")
        return HttpAgentClient(url)

    logger.info(f"Using agent app over ASGI: {agent_app}")
    return FastAPIAgentClient(agent_app)


__all__ = [
    "AgentClient",
    "AgentInfo",
    "FastAPIAgentClient",
    "HttpAgentClient",
    "create_agent_client",
]
