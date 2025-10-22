# server/tests/endpoints/conftest.py

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.server.api.private_v2 import (
    data_connections,
    evals,
    mcp_servers,
    platforms,
    work_items_private,
)
from agent_platform.server.api.public_v2 import work_items
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage.option import StorageService

# Get storage fixtures.
from server.tests.storage_fixtures import *  # noqa: F403


# ──────────────────────────────────────────────────────────────
# user + agent seeders so FK constraints pass
# ──────────────────────────────────────────────────────────────
@pytest.fixture
async def stub_user(storage):
    user, _ = await storage.get_or_create_user("tenant:test:user:endpoint")
    return user


@pytest.fixture
async def seed_agents(storage, stub_user):
    async def make(agent_id):
        agent = Agent(
            agent_id=agent_id,
            user_id=stub_user.user_id,
            name=f"Agent {agent_id}",
            description="seeded",
            runbook_structured=Runbook(raw_text="You are helpful.", content=[]),
            version="1.0.0",
            agent_architecture=AgentArchitecture(
                name="agent_platform.architectures.default",
                version="1.0.0",
            ),
            platform_configs=[],
            action_packages=[],
            mcp_servers=[],
            question_groups=[],
            observability_configs=[],
            extra={},
        )
        await storage.upsert_agent(stub_user.user_id, agent)
        return agent

    agents = []
    for aid in (
        "ce00da42-a4a1-49c2-ac7f-8ebbfccb0b7a",
        "ecb0c2cf-0226-41f1-ba14-230ce76271ef",
        "3546121f-53e6-40aa-b0e5-7872d82758a6",
    ):
        agents.append(await make(aid))

    return agents


# ──────────────────────────────────────────────────────────────
# FastAPI + client fixtures wired to whichever storage we got
# ──────────────────────────────────────────────────────────────
@pytest.fixture
def fastapi_app(storage, stub_user) -> FastAPI:
    from agent_platform.server.file_manager.option import FileManagerService

    StorageService.reset()
    StorageService.set_for_testing(storage)

    # Also reset the FileManagerService to ensure it uses the correct storage
    FileManagerService.reset()

    app = FastAPI()
    app.include_router(work_items.router, prefix="/public/v1/work-items")
    app.include_router(work_items_private.router, prefix="/api/v2/work-items")
    app.include_router(mcp_servers.router, prefix="/api/v2/private/mcp-servers")
    app.include_router(platforms.router, prefix="/api/v2/private/platforms")
    app.include_router(data_connections.router, prefix="/api/v2/private/data-connections")
    app.include_router(evals.router, prefix="/api/v2/evals")
    app.dependency_overrides[auth_user] = lambda: stub_user
    add_exception_handlers(app)
    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app)
