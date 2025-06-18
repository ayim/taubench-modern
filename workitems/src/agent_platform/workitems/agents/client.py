from __future__ import annotations

from abc import ABC, abstractmethod
from http import HTTPStatus

import httpx
from fastapi import FastAPI


class AgentInfo:
    """Basic agent information needed for validation."""

    def __init__(self, agent_id: str, name: str, user_id: str):
        self.agent_id = agent_id
        self.name = name
        self.user_id = user_id


class AgentClient(ABC):
    """Interface for agent operations."""

    @abstractmethod
    async def describe_agent(self, agent_id: str) -> AgentInfo | None:
        """
        Retrieve basic information about an agent.

        Args:
            agent_id: The ID of the agent to describe

        Returns:
            AgentInfo if agent exists, None if not found
        """
        pass


class HttpAgentClient(AgentClient):
    """AgentClient implementation using HTTP transport."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def describe_agent(self, agent_id: str) -> AgentInfo | None:
        """
        Retrieve basic information about an agent using the FastAPI app.

        Args:
            agent_id: The ID of the agent to describe

        Returns:
            AgentInfo if agent exists, None if not found or on error
        """
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            # Use the private API endpoint for agent retrieval
            response = await client.get(f"/api/v2/agents/{agent_id}")

            if response.status_code == HTTPStatus.OK.value:
                agent_data = response.json()
                return AgentInfo(
                    agent_id=agent_data["agent_id"],
                    name=agent_data["name"],
                    user_id=agent_data["user_id"],
                )
            elif response.status_code == HTTPStatus.NOT_FOUND.value:
                return None
            else:
                raise ValueError(f"Unexpected status code: {response.status_code}")


class FastAPIAgentClient(AgentClient):
    """AgentClient implementation using FastAPI app via ASGITransport."""

    def __init__(self, app: FastAPI):
        self.app = app

    async def describe_agent(self, agent_id: str) -> AgentInfo | None:
        """
        Retrieve basic information about an agent using the FastAPI app.

        Args:
            agent_id: The ID of the agent to describe

        Returns:
            AgentInfo if agent exists, None if not found or on error
        """
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://testserver"
        ) as client:
            # The agentserver is publicly mounted at /api/v2/agents, but
            # we're seeing the internal router at `/agents`
            response = await client.get(f"/agents/{agent_id}")

            if response.status_code == HTTPStatus.OK.value:
                agent_data = response.json()
                return AgentInfo(
                    agent_id=agent_data["agent_id"],
                    name=agent_data["name"],
                    user_id=agent_data["user_id"],
                )
            elif response.status_code == HTTPStatus.NOT_FOUND.value:
                return None
            else:
                raise ValueError(f"Unexpected status code: {response.status_code}")
