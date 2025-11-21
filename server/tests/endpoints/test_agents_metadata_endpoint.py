import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agent_platform.server.api.private_v2 import PRIVATE_V2_PREFIX
from agent_platform.server.api.private_v2 import router as private_v2_router
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage.option import StorageService


@pytest.fixture
async def metadata_user(storage):
    user, _ = await storage.get_or_create_user("tenant:test:metadata:user")
    return user


@pytest.fixture
async def metadata_app(storage, metadata_user):
    StorageService.set_for_testing(storage)

    app = FastAPI()
    app.include_router(private_v2_router, prefix=PRIVATE_V2_PREFIX)
    app.dependency_overrides[auth_user] = lambda: metadata_user
    add_exception_handlers(app)

    yield app

    StorageService.reset()


@pytest.fixture
async def metadata_client(metadata_app):
    async with AsyncClient(
        transport=ASGITransport(app=metadata_app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_get_agents_by_metadata_returns_hidden_agents(
    metadata_client, metadata_user, storage
):
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.runbook import Runbook

    hidden_agent = Agent(
        name="Hidden Violet Agent",
        description="hidden agent",
        user_id=metadata_user.user_id,
        runbook_structured=Runbook(raw_text="hidden", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="experimental_1", version="2.0.0"),
        extra={"metadata": {"project": "violet", "visibility": "hidden", "extra": "keep"}},
        mode="conversational",
    )

    other_agent = Agent(
        name="Visible Agent",
        description="visible agent",
        user_id=metadata_user.user_id,
        runbook_structured=Runbook(raw_text="visible", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="experimental_1", version="2.0.0"),
        extra={"metadata": {"project": "violet"}},
        mode="conversational",
    )

    await storage.upsert_agent(metadata_user.user_id, hidden_agent)
    await storage.upsert_agent(metadata_user.user_id, other_agent)

    response = await metadata_client.get(
        f"{PRIVATE_V2_PREFIX}/agents/search/by-metadata",
        params={"project": "violet", "visibility": "hidden"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == hidden_agent.agent_id
    assert data[0]["name"] == hidden_agent.name


@pytest.mark.asyncio
async def test_get_agents_by_metadata_requires_params(metadata_client):
    response = await metadata_client.get(f"{PRIVATE_V2_PREFIX}/agents/search/by-metadata")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["message"] == "At least one metadata query parameter is required."
