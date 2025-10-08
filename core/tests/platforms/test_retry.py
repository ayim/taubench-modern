import logging

import pytest
from httpx import HTTPStatusError, Request, Response

from agent_platform.core.platforms.retry import build_httpx_retry_decorator


@pytest.mark.asyncio
async def test_httpx_retry_decorator_retries_on_429() -> None:
    """Ensure 429 responses trigger retry logic in HTTPX retry helper."""

    decorator = build_httpx_retry_decorator(
        logger=logging.getLogger("test"),
        provider_name="TestProvider",
        context="unit-test",
        max_attempts=3,
        base_backoff_s=0.0,
        max_backoff_s=0.0,
        retryable_status={429},
    )

    attempts = 0

    @decorator
    async def flaky_call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            request = Request("GET", "https://example.com")
            response = Response(status_code=429, request=request)
            raise HTTPStatusError("rate limited", request=request, response=response)
        return "ok"

    result = await flaky_call()

    assert result == "ok"
    assert attempts == 2
