from __future__ import annotations

from abc import ABC, abstractmethod
from http import HTTPStatus

import httpx
from fastapi import FastAPI

from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload
from agent_platform.core.thread.base import ThreadMessage

from .models import AgentInfo, InvokeAgentResponse, RunStatusResponse, dump_initiate_stream_payload


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

    @abstractmethod
    async def invoke_agent(
        self, agent_id: str, payload: InitiateStreamPayload
    ) -> InvokeAgentResponse:
        """
        Invoke an agent.
        """
        pass

    @abstractmethod
    async def get_run_status(self, run_id: str) -> RunStatusResponse | None:
        """
        Get the status of a run by its ID.
        """
        pass

    @abstractmethod
    async def get_messages(self, run_id: str) -> list[ThreadMessage]:
        """
        Get the messages of a run by its ID.
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

    async def invoke_agent(
        self, agent_id: str, payload: InitiateStreamPayload
    ) -> InvokeAgentResponse:
        """
        Invoke an agent.
        """
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            body = dump_initiate_stream_payload(payload)
            response = await client.post(f"/api/v2/runs/{agent_id}/async", json=body)

            if response.status_code == HTTPStatus.OK.value:
                invoke_resp = response.json()
                return InvokeAgentResponse.model_validate(invoke_resp)

            raise ValueError(
                f"Unexpected status code in /runs/{agent_id}/async: {response.status_code}"
            )

    async def get_run_status(self, run_id: str) -> RunStatusResponse | None:
        """
        Get the status of a run by its ID.
        """
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.get(f"/api/v2/runs/{run_id}/status")

            if response.status_code == HTTPStatus.OK.value:
                return RunStatusResponse.model_validate(response.json())
            elif response.status_code == HTTPStatus.NOT_FOUND.value:
                return None

            response.raise_for_status()
            raise ValueError(
                f"Unexpected status code in /runs/{run_id}/status: {response.status_code}"
            )

    async def get_messages(self, run_id: str) -> list[ThreadMessage]:
        """
        Get the messages of a run by its ID.
        """
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.get(f"/api/v2/runs/{run_id}/messages")

            if response.status_code == HTTPStatus.OK.value:
                return [ThreadMessage.model_validate(message) for message in response.json()]

            response.raise_for_status()
            raise ValueError(
                f"Unexpected status code in /runs/{run_id}/messages: {response.status_code}"
            )


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

    async def invoke_agent(
        self, agent_id: str, payload: InitiateStreamPayload
    ) -> InvokeAgentResponse:
        """
        Invoke an agent.
        """
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://testserver"
        ) as client:
            body = dump_initiate_stream_payload(payload)
            response = await client.post(f"/runs/{agent_id}/async", json=body)

            if response.status_code == HTTPStatus.OK.value:
                invoke_resp = response.json()
                return InvokeAgentResponse.model_validate(invoke_resp)

            raise ValueError(
                f"Unexpected status code in /runs/{agent_id}/async: {response.status_code}"
            )

    async def get_run_status(self, run_id: str) -> RunStatusResponse | None:
        """
        Get the status of a run by its ID.
        """
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://testserver"
        ) as client:
            response = await client.get(f"/runs/{run_id}/status")

            if response.status_code == HTTPStatus.OK.value:
                return RunStatusResponse.model_validate(response.json())
            elif response.status_code == HTTPStatus.NOT_FOUND.value:
                return None

            response.raise_for_status()
            raise ValueError(
                f"Unexpected status code in /runs/{run_id}/status: {response.status_code}"
            )

    async def get_messages(self, run_id: str) -> list[ThreadMessage]:
        """
        Get the messages of a run by its ID.
        """
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://testserver"
        ) as client:
            response = await client.get(f"/runs/{run_id}/messages")

            if response.status_code == HTTPStatus.OK.value:
                return [ThreadMessage.model_validate(message) for message in response.json()]

            response.raise_for_status()
            raise ValueError(
                f"Unexpected status code in /runs/{run_id}/messages: {response.status_code}"
            )
