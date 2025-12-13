import asyncio
import time
import typing
from collections.abc import AsyncGenerator

import pytest
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.fixture
async def sample_user_id(storage: "SQLiteStorage | PostgresStorage") -> str:
    from agent_platform.server.storage.sqlite.sqlite import SQLiteStorage

    if isinstance(storage, SQLiteStorage):
        user, _ = await storage.get_or_create_user(
            sub="tenant:testing:user:oauth_test",
        )
        return user.user_id
    else:
        return await storage.get_system_user_id()


@pytest.fixture
async def sample_mcp_url(storage: "SQLiteStorage | PostgresStorage", sample_user_id: str) -> AsyncGenerator[str, None]:
    from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource

    mcp_url = "https://example.com/mcp"
    mcp_server = MCPServer(
        name="test-oauth-mcp",
        transport="streamable-http",
        url=mcp_url,
    )
    await storage.create_mcp_server(mcp_server, MCPServerSource.API)
    servers = await storage.list_mcp_servers()
    mcp_server_id = next(iter(servers.keys()))
    yield mcp_url
    await storage.delete_mcp_server([mcp_server_id])


@pytest.mark.asyncio
async def test_oauth_token_save_and_retrieve(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_mcp_url: str,
) -> None:
    """Test basic OAuth token save and retrieve operations."""
    initial_token = OAuthToken(
        access_token="test_access_token_123",
        token_type="Bearer",
        expires_in=3600,  # 1 hour
        scope="read write",
        refresh_token="test_refresh_token_456",
    )

    await storage.set_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, token=initial_token)

    retrieved_token = await storage.get_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=True)
    assert retrieved_token is not None
    assert retrieved_token.access_token == "test_access_token_123"
    assert retrieved_token.token_type == "Bearer"
    assert retrieved_token.scope == "read write"
    assert retrieved_token.refresh_token == "test_refresh_token_456"
    assert retrieved_token.expires_in is not None
    assert 3590 <= retrieved_token.expires_in <= 3600


@pytest.mark.asyncio
async def test_oauth_token_ttl_recalculation(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_mcp_url: str,
) -> None:
    """Test that OAuth token TTL is recalculated correctly over time."""
    initial_token = OAuthToken(
        access_token="test_access_token_123",
        token_type="Bearer",
        expires_in=3600,  # 1 hour
        scope="read write",
        refresh_token="test_refresh_token_456",
    )

    await storage.set_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, token=initial_token)

    retrieved_token = await storage.get_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=True)
    assert retrieved_token is not None
    assert retrieved_token.expires_in is not None

    await asyncio.sleep(2)
    retrieved_token_after_wait = await storage.get_mcp_oauth_token(
        user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=True
    )
    assert retrieved_token_after_wait is not None
    assert retrieved_token_after_wait.expires_in is not None
    assert (retrieved_token.expires_in - retrieved_token_after_wait.expires_in) >= 1  # At least 1 second difference


@pytest.mark.asyncio
async def test_oauth_token_update(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_mcp_url: str,
) -> None:
    """Test updating an existing OAuth token."""
    initial_token = OAuthToken(
        access_token="test_access_token_123",
        token_type="Bearer",
        expires_in=3600,
        scope="read write",
        refresh_token="test_refresh_token_456",
    )
    await storage.set_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, token=initial_token)

    updated_token = OAuthToken(
        access_token="new_access_token_789",
        token_type="Bearer",
        expires_in=7200,  # 2 hours
        scope="read",
        refresh_token="new_refresh_token_012",
    )
    await storage.set_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, token=updated_token)

    retrieved_updated = await storage.get_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=True)
    assert retrieved_updated is not None
    assert retrieved_updated.access_token == "new_access_token_789"
    assert retrieved_updated.expires_in is not None
    assert 7190 <= retrieved_updated.expires_in <= 7200


@pytest.mark.asyncio
async def test_oauth_client_info_save_and_retrieve(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_mcp_url: str,
) -> None:
    """Test OAuth client information save and retrieve operations."""
    client_info = OAuthClientInformationFull(
        client_id="test_client_id_123",
        client_secret="test_client_secret_456",
        client_id_issued_at=int(time.time()),
        client_secret_expires_at=int(time.time()) + 86400,  # 24 hours from now
        redirect_uris=[AnyHttpUrl("https://example.com/callback")],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope="read write",
        client_name="Test OAuth Client",
    )

    await storage.set_mcp_oauth_client_info(user_id=sample_user_id, mcp_url=sample_mcp_url, client_info=client_info)

    retrieved_client_info = await storage.get_mcp_oauth_client_info(
        user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=True
    )
    assert retrieved_client_info is not None
    assert retrieved_client_info.client_id == "test_client_id_123"
    assert retrieved_client_info.client_secret == "test_client_secret_456"
    assert retrieved_client_info.client_id_issued_at == client_info.client_id_issued_at
    assert retrieved_client_info.client_secret_expires_at == client_info.client_secret_expires_at
    assert retrieved_client_info.client_name == "Test OAuth Client"
    assert retrieved_client_info.scope == "read write"
    assert len(retrieved_client_info.redirect_uris) == 1
    assert str(retrieved_client_info.redirect_uris[0]) == "https://example.com/callback"


@pytest.mark.asyncio
async def test_oauth_token_without_expires_in(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_mcp_url: str,
) -> None:
    """Test OAuth token storage when expires_in is None."""
    token_no_expiry = OAuthToken(
        access_token="token_no_expiry",
        token_type="Bearer",
        expires_in=None,
        refresh_token="refresh_no_expiry",
    )
    await storage.set_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, token=token_no_expiry)

    retrieved_no_expiry = await storage.get_mcp_oauth_token(
        user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=True
    )
    assert retrieved_no_expiry is not None
    assert retrieved_no_expiry.expires_in is None


@pytest.mark.asyncio
async def test_oauth_token_without_refresh_token(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_mcp_url: str,
) -> None:
    """Test OAuth token storage when refresh_token is not provided."""
    token_no_refresh = OAuthToken(
        access_token="token_no_refresh",
        token_type="Bearer",
        expires_in=1800,
    )
    await storage.set_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, token=token_no_refresh)

    retrieved_no_refresh = await storage.get_mcp_oauth_token(
        user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=True
    )
    assert retrieved_no_refresh is not None
    assert retrieved_no_refresh.refresh_token is None


@pytest.mark.asyncio
async def test_oauth_token_deletion(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_mcp_url: str,
) -> None:
    """Test OAuth token deletion."""
    initial_token = OAuthToken(
        access_token="test_access_token_123",
        token_type="Bearer",
        expires_in=3600,
        refresh_token="test_refresh_token_456",
    )
    await storage.set_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, token=initial_token)

    await storage.delete_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url)
    deleted_token = await storage.get_mcp_oauth_token(user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=False)
    assert deleted_token is None


@pytest.mark.asyncio
async def test_oauth_client_info_deletion(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_mcp_url: str,
) -> None:
    """Test OAuth client information deletion."""
    client_info = OAuthClientInformationFull(
        client_id="test_client_id_123",
        client_secret="test_client_secret_456",
        client_id_issued_at=int(time.time()),
        client_secret_expires_at=int(time.time()) + 86400,
        redirect_uris=[AnyHttpUrl("https://example.com/callback")],
        grant_types=["authorization_code"],
        response_types=["code"],
        scope="read",
        client_name="Test OAuth Client",
    )
    await storage.set_mcp_oauth_client_info(user_id=sample_user_id, mcp_url=sample_mcp_url, client_info=client_info)

    await storage.delete_mcp_oauth_client_info(user_id=sample_user_id, mcp_url=sample_mcp_url)
    deleted_client_info = await storage.get_mcp_oauth_client_info(
        user_id=sample_user_id, mcp_url=sample_mcp_url, decrypt=False
    )
    assert deleted_client_info is None
