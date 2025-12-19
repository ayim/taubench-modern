# server/tests/endpoints/conftest.py
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.agent_package.spec import AgentSpec, SpecAgent
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.server.api.private_v2 import (
    data_connections,
    evals,
    mcp_servers,
    observability,
    platforms,
)
from agent_platform.server.api.private_v2 import (
    work_items_router as work_items_private,
)
from agent_platform.server.api.public_v2 import work_items_router as work_items_public
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
    app.include_router(work_items_public, prefix="/api/public/v1/work-items")
    app.include_router(work_items_private, prefix="/api/v2/work-items")
    app.include_router(mcp_servers.router, prefix="/api/v2/private/mcp-servers")
    app.include_router(platforms.router, prefix="/api/v2/private/platforms")
    app.include_router(data_connections.router, prefix="/api/v2/private/data-connections")
    app.include_router(observability.router, prefix="/api/v2")
    app.include_router(evals.router, prefix="/api/v2/evals")
    app.dependency_overrides[auth_user] = lambda: stub_user
    add_exception_handlers(app)
    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app)


# ──────────────────────────────────────────────────────────────
# AgentPackageHandler fixtures
# ──────────────────────────────────────────────────────────────
@pytest.fixture
def agent_package_handler_factory():
    def _create_agent_package_handler(mock_package_spec: dict):
        handler = AsyncMock()

        handler.read_agent_spec = AsyncMock(return_value=AgentSpec.model_validate(mock_package_spec["spec"]))
        handler.get_spec_agent = AsyncMock(
            return_value=SpecAgent.model_validate(mock_package_spec["spec"]["agent-package"]["agents"][0])
        )

        # Configure the mock to behave as an asynchronous context manager
        # that returns itself
        handler.__enter__.return_value = handler
        handler.__exit__.return_value = None

        handler.read_runbook = AsyncMock(return_value=None)
        handler.read_conversation_guide_raw = AsyncMock(return_value=None)
        handler.read_semantic_data_model_raw = AsyncMock(return_value=None)
        handler.get_spooled_file_bytes = AsyncMock(return_value=b"")
        handler.read_all_semantic_data_models = AsyncMock(return_value={})
        handler.read_conversation_guide = AsyncMock(return_value=[])

        if "runbook_text" in mock_package_spec:
            handler.read_runbook = AsyncMock(return_value=mock_package_spec["runbook_text"])

        if "question_groups" in mock_package_spec:
            handler.read_conversation_guide = AsyncMock(return_value=mock_package_spec["question_groups"])

        if "semantic_data_models" in mock_package_spec:
            handler.read_semantic_data_models = AsyncMock(return_value=mock_package_spec["semantic_data_models"])

        return handler

    return _create_agent_package_handler
