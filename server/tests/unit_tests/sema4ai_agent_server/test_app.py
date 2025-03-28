"""Test the server and client together."""

from typing import Optional, Sequence
from unittest import skip
from uuid import uuid4

import pytest
from psycopg_pool.pool import ConnectionPool
from fastapi import status

from tests.unit_tests.sema4ai_agent_server.helpers import get_client


def _project(d: dict, *, exclude_keys: Optional[Sequence[str]]) -> dict:
    """Return a dict with only the keys specified."""
    _exclude = set(exclude_keys) if exclude_keys else set()
    return {k: v for k, v in d.items() if k not in _exclude}


@pytest.fixture()
async def pool():
    print("pool created")


@skip("TODO: Remove references to postgres and use sqlite for unit tests.")
async def test_list_and_create_agents(pool: ConnectionPool) -> None:
    """Test list and create agents."""
    headers = {"Cookie": "agent_server_user_id=1"}
    aid = str(uuid4())

    async with pool.acquire() as conn:
        assert len(await conn.fetch("SELECT * FROM agent;")) == 0

    async with get_client() as client:
        response = await client.get(
            "/api/v1/agents/",
            headers=headers,
        )
        assert response.status_code == 200

        assert response.json() == []

        # Create an agent
        response = await client.put(
            f"/api/v1/agents/{aid}",
            json={"name": "bobby"},
            headers=headers,
        )
        assert response.status_code == 200
        assert _project(response.json(), exclude_keys=["updated_at", "user_id"]) == {
            "id": aid,
            "name": "bobby",
        }
        async with pool.acquire() as conn:
            assert len(await conn.fetch("SELECT * FROM agent;")) == 1

        response = await client.get("/api/v1/agents/", headers=headers)
        assert [
            _project(d, exclude_keys=["updated_at", "user_id"]) for d in response.json()
        ] == [{"id": aid, "name": "bobby"}]

        response = await client.put(
            f"/api/v1/agents/{aid}",
            json={"name": "bobby"},
            headers=headers,
        )

        assert _project(response.json(), exclude_keys=["updated_at", "user_id"]) == {
            "id": aid,
            "name": "bobby",
        }

        # Check not visible to other users
        headers = {"Cookie": "agent_server_user_id=2"}
        response = await client.get("/api/v1/agents/", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == []


@skip("TODO: Remove references to postgres and use sqlite for unit tests.")
async def test_threads() -> None:
    """Test put thread."""
    headers = {"Cookie": "agent_server_user_id=1"}
    aid = str(uuid4())
    tid = str(uuid4())

    async with get_client() as client:
        response = await client.put(
            f"/api/v1/agents/{aid}",
            json={"name": "agent"},
            headers=headers,
        )

        response = await client.put(
            f"/api/v1/threads/{tid}",
            json={"name": "bobby", "agent_id": aid},
            headers=headers,
        )
        assert response.status_code == 200, response.text

        response = await client.get(f"/api/v1/threads/{tid}/state", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"values": None, "next": []}

        response = await client.get("/api/v1/threads/", headers=headers)

        assert response.status_code == 200
        assert [
            _project(d, exclude_keys=["updated_at", "user_id"]) for d in response.json()
        ] == [
            {
                "agent_id": aid,
                "name": "bobby",
                "thread_id": tid,
                "metadata": {"agent_type": "chatbot"},
            }
        ]

        response = await client.put(
            f"/api/v1/threads/{tid}",
            headers={"Cookie": "agent_server_user_id=2"},
        )
        assert response.status_code == 422


@pytest.fixture
async def agent():
    """Fixture to create and clean up an agent."""
    headers = {"Cookie": "agent_server_user_id=1"}
    async with get_client() as client:
        # Create an agent
        response = await client.post(
            "/api/v1/agents",
            json={
                "public": False,
                "name": "Test agent",
                "description": "Test agent",
                "runbook": "Test runbook",
                "version": "1.0",
                "model": {
                    "provider": "OpenAI",
                    "model": "gpt-3",
                    "config": {
                        "api_key": "your-api-key",
                        "other_config": "value"
                    }
                },
                "advanced_config": {
                    "architecture": "agent",
                    "reasoning": "disabled"
                },
                "action_packages": [],
                "metadata": {
                    "mode": "conversational",
                    "question_groups": []
                }
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        aid = response.json()["id"]

        yield aid, headers  # Provide the agent ID and headers to the test

        # Cleanup: Delete the agent after the test
        response = await client.delete(f"/api/v1/agents/{aid}", headers=headers)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_create_conversation(agent):
    """Test creating a new conversation."""
    aid, headers = agent
    conversation_name = "Test Conversation"

    async with get_client() as client:
        # Create a new conversation using the agent ID from the fixture
        response = await client.post(
            f"/api/public/v1/agents/{aid}/conversations?name={conversation_name}",
            headers=headers,
        )
        if response.status_code != status.HTTP_200_OK:
            print("Create Conversation Error:", response.json())
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == conversation_name


@skip
async def test_post_messages_to_conversation(agent):
    """Test posting messages to a conversation."""
    aid, headers = agent
    conversation_name = "Test Conversation"
    messages = [{
        "id": str(uuid4()),  # Add a unique ID for each message
        "type": "human",
        "role": "human",
        "content": "Hello, agent!"
    }]

    async with get_client() as client:
        # Create a new conversation using the agent ID from the fixture
        response = await client.post(
            f"/api/public/v1/agents/{aid}/conversations?name={conversation_name}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        cid = response.json()["id"]

        # Post messages to the conversation
        response = await client.post(
            f"/api/public/v1/agents/{aid}/conversations/{cid}/messages",
            json=messages,  # Send the list of messages directly
            headers=headers,
        )
        if response.status_code != status.HTTP_200_OK:
            print("Post Messages Error:", response.json())
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["messages"][0]["content"] == "Hello, agent!"
