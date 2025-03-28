from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from typing_extensions import AsyncGenerator


@asynccontextmanager
async def get_client() -> AsyncGenerator[AsyncClient, None]:
    """Get the app."""
    from sema4ai_agent_server.app import create_app

    async with AsyncClient(
        transport=ASGITransport(create_app()),
        base_url="http://test",
    ) as ac:
        yield ac
