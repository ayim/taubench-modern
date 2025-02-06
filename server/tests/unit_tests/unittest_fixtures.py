import pytest

from sema4ai_agent_server.lifespan import lifespan
from sema4ai_agent_server.server import app


@pytest.fixture(scope="module", autouse=True)
async def _lifespan_fixture():
    async with lifespan(app):
        yield

