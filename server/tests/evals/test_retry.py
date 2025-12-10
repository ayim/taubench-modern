import pytest

from agent_platform.server.evals.retry import RetryExceededError, retry_async


@pytest.mark.asyncio
async def test_retry_async_exposes_last_error():
    async def failing_op():
        raise ValueError("boom")

    with pytest.raises(RetryExceededError) as excinfo:
        await retry_async(failing_op)

    assert isinstance(excinfo.value.last_error, ValueError)
