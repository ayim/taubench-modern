# server/tests/endpoints/conftest.py
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.server.api.private_v2 import work_items
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage import PostgresStorage, SQLiteStorage
from agent_platform.server.storage.option import StorageService


# ──────────────────────────────────────────────────────────────
# 1.  spin-up Postgres once per session (copied from file manager)
# ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", params=[pytest.param("", marks=[pytest.mark.postgresql])])
async def postgres_test_db() -> AsyncGenerator[
    AsyncConnectionPool[AsyncConnection[TupleRow]], None
]:
    import testing.postgresql

    with testing.postgresql.Postgresql() as pg:
        pool = AsyncConnectionPool(pg.url(), min_size=2, max_size=50, open=False)
        await pool.open()
        yield cast(AsyncConnectionPool[AsyncConnection[TupleRow]], pool)
        await pool.close()


# ──────────────────────────────────────────────────────────────
# 2.  “storage” fixture that switches between back-ends
# ──────────────────────────────────────────────────────────────
@pytest.fixture(
    params=[
        pytest.param("sqlite", marks=[]),
        pytest.param("postgres", marks=[pytest.mark.postgresql]),
    ]
)
async def storage(request, tmp_path: Path, postgres_test_db):
    if request.param == "postgres":
        # reset the schema and use the pool created above
        async with postgres_test_db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP SCHEMA IF EXISTS v2 CASCADE;")
                await cur.execute("CREATE SCHEMA v2;")
        store = PostgresStorage(postgres_test_db)
    else:
        db_file = tmp_path / "test.db"
        if db_file.exists():
            db_file.unlink()
        store = SQLiteStorage(db_path=str(db_file))

    await store.setup()
    await store.get_or_create_user(sub="tenant:testing:system:system_user")
    yield store
    await store.teardown()


# ──────────────────────────────────────────────────────────────
# 3.  user + agent seeders so FK constraints pass
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
# 4.  FastAPI + client fixtures wired to whichever storage we got
# ──────────────────────────────────────────────────────────────
@pytest.fixture
def fastapi_app(storage, stub_user) -> FastAPI:
    StorageService.reset()
    StorageService.set_for_testing(storage)

    app = FastAPI()
    app.include_router(work_items.router, prefix="/v2/work-items")
    app.dependency_overrides[auth_user] = lambda: stub_user
    add_exception_handlers(app)
    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app)
