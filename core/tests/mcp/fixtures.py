from __future__ import annotations

import typing
from collections.abc import AsyncGenerator

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.core.oauth.oauth_models import AuthenticationMetadataClientCredentials


async def wait_until_mcp_server_is_ready(url: str, *, timeout: float = 30.0) -> None:
    import time

    import anyio
    import httpx

    start = time.monotonic()
    while True:
        try:
            async with httpx.AsyncClient() as c:
                # We don't care which status, just that a socket is open
                await c.get(
                    url,
                    headers={
                        "accept": "application/json, text/event-stream",
                    },
                    timeout=0.3,
                )
            return
        except httpx.RequestError:
            pass
        if time.monotonic() - start > timeout:
            raise RuntimeError(f"Server route {url!r} never became ready")
        await anyio.sleep(0.1)


@pytest.fixture(scope="session")
async def live_custom_mcp_server_with_auth(unused_tcp_port_factory):
    import io
    import sys

    from core.tests.mcp import custom_mcp

    port = unused_tcp_port_factory()
    from sema4ai.common.process import Process

    custom_mcp_file = custom_mcp.__file__
    process = Process([sys.executable, custom_mcp_file, str(port), "dummy-token"])
    stream = io.StringIO()
    process.stream_to(stream)
    process.start()
    url = f"http://127.0.0.1:{port}"

    # Wait until the server is ready
    timeout = 30.0
    try:
        await wait_until_mcp_server_is_ready(url, timeout=timeout)
    except Exception as e:
        process.stop()
        raise RuntimeError(
            f"Server didn't become ready after {timeout} seconds.\nProcess output:\n{stream.getvalue()}"
        ) from e

    yield url
    process.stop()


@pytest.fixture(scope="session")
async def live_custom_oauth2_client_credentials_server(
    unused_tcp_port_factory,
) -> AsyncGenerator[AuthenticationMetadataClientCredentials, None]:
    import io
    import sys

    from pydantic.types import SecretStr

    from agent_platform.core.oauth.oauth_models import (
        AuthenticationMetadataClientCredentials,
        AuthenticationType,
        OAuthConfig,
        get_client_credentials_oauth_token,
    )
    from core.tests.mcp import custom_oauth2_client_credentials
    from core.tests.mcp.custom_oauth2_client_credentials import DUMMY_CLIENT_ID, DUMMY_CLIENT_SECRET

    port = unused_tcp_port_factory()
    from sema4ai.common.process import Process

    custom_oauth2_client_credentials_file = custom_oauth2_client_credentials.__file__
    process = Process([sys.executable, custom_oauth2_client_credentials_file, str(port)])
    stream = io.StringIO()
    process.stream_to(stream)
    process.start()
    url = f"http://127.0.0.1:{port}"

    # Wait until the server is ready
    timeout = 30.0
    try:
        await wait_until_mcp_server_is_ready(url, timeout=timeout)
    except Exception as e:
        process.stop()
        raise RuntimeError(
            f"Server didn't become ready after {timeout} seconds.\nProcess output:\n{stream.getvalue()}"
        ) from e

    info: AuthenticationMetadataClientCredentials = AuthenticationMetadataClientCredentials(
        endpoint=f"{url}/token",
        client_id=SecretStr(DUMMY_CLIENT_ID),
        client_secret=SecretStr(DUMMY_CLIENT_SECRET),
        scope="openid",
    )

    await get_client_credentials_oauth_token(
        OAuthConfig(authentication_metadata=info, authentication_type=AuthenticationType.OAUTH2_CLIENT_CREDENTIALS),
        mcp_server_url=url,
    )
    yield info
    process.stop()
