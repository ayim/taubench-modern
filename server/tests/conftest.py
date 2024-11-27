import asyncio

import pytest

from sema4ai_agent_server.lifespan import lifespan
from sema4ai_agent_server.server import app


@pytest.fixture(scope="module", autouse=True)
async def lifespan_fixture():
    async with lifespan(app):
        yield


@pytest.fixture(scope="module")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Exclude the integration_tests directory from the pytest collection
collect_ignore = ["integration_tests"]
