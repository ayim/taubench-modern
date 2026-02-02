from types import SimpleNamespace
from typing import cast

import pytest

from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.evals.types import (
    FlowAdherenceResult,
    ResponseAccuracyResult,
    Scenario,
)
from agent_platform.core.thread.thread import Thread
from agent_platform.core.user import User
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.evals.retry import RetryExceededError


def _patch_common_dependencies(monkeypatch, module):
    class DummyContext:
        pass

    class DummyAgentServerContext:
        @classmethod
        def from_request(cls, *args, **kwargs):
            return DummyContext()

    monkeypatch.setattr(module, "AgentServerContext", DummyAgentServerContext)

    class DummyConverters:
        def set_thread_message_conversion_function(self, fn):
            self.fn = fn

    class DummyKernel:
        def __init__(self):
            self.converters = DummyConverters()

    monkeypatch.setattr(module, "create_minimal_kernel", lambda ctx: DummyKernel())

    async def fake_formatter(*args, **kwargs):
        return "formatted"

    monkeypatch.setattr(module, "format_thread_conversation_for_eval", fake_formatter)


def _make_rate_limit_error():
    return StreamingError(error_code=ErrorCode.TOO_MANY_REQUESTS)


def _build_inputs():
    from unittest.mock import AsyncMock

    from agent_platform.server.storage.errors import ConfigNotFoundError

    thread = cast(Thread, SimpleNamespace(messages=[]))
    scenario = cast(Scenario, SimpleNamespace(messages=[], agent_id="agent"))
    user = cast(User, SimpleNamespace(user_id="user"))
    storage = cast(
        StorageDependency,
        SimpleNamespace(get_config=AsyncMock(side_effect=ConfigNotFoundError())),
    )
    return thread, scenario, user, storage


@pytest.mark.asyncio
async def test_flow_adherence_surfaces_rate_limit_error(monkeypatch):
    from agent_platform.server.evals.evaluations import flow_adherence as module

    _patch_common_dependencies(monkeypatch, module)

    async def failing_retry_async(*args, **kwargs):
        raise RetryExceededError("boom", last_error=_make_rate_limit_error())

    monkeypatch.setattr(module, "retry_async", failing_retry_async)

    thread, scenario, user, storage = _build_inputs()
    result = await module.evaluate_flow_adherence(thread, scenario, user, storage)

    assert isinstance(result, FlowAdherenceResult)
    assert result.passed is False
    assert "rate limited" in result.explanation.lower()


@pytest.mark.asyncio
async def test_response_accuracy_surfaces_rate_limit_error(monkeypatch):
    from agent_platform.server.evals.evaluations import response_accuracy as module

    _patch_common_dependencies(monkeypatch, module)

    async def failing_retry_async(*args, **kwargs):
        raise RetryExceededError("boom", last_error=_make_rate_limit_error())

    monkeypatch.setattr(module, "retry_async", failing_retry_async)

    thread, scenario, user, storage = _build_inputs()
    result = await module.evaluate_response_accuracy(thread, scenario, user, storage, criteria="ok")

    assert isinstance(result, ResponseAccuracyResult)
    assert result.passed is False
    assert "rate limited" in result.explanation.lower()
