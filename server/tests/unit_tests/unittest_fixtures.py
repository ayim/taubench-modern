import asyncio

import pytest

from sema4ai_agent_server.app import create_app
from sema4ai_agent_server.lifespan import lifespan


@pytest.fixture(scope="module", autouse=True)
async def lifespan_fixture():
    async with lifespan(create_app()):
        yield


@pytest.fixture(scope="module")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
