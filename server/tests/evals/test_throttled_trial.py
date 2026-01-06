import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from agent_platform.core.evals.types import Trial, TrialStatus
from agent_platform.server.evals import background_worker
from agent_platform.server.evals.background_worker import (
    TASK_TIMEOUT_ERROR_MESSAGE,
    QueueSettings,
    WorkQueue,
)
from agent_platform.server.evals.errors import TrialRateLimitedError


class _StubRepository(background_worker.TaskRepository[Trial]):
    def __init__(self) -> None:
        self._get_pending_task_ids = AsyncMock()
        self._get_tasks_by_ids = AsyncMock()
        self._mark_incomplete = AsyncMock()
        self._get_task = AsyncMock()
        self._set_status_if_not_canceled = AsyncMock()
        self._requeue_task = AsyncMock()

    async def get_pending_task_ids(self, max_batch_size: int):
        return await self._get_pending_task_ids(max_batch_size)

    async def get_tasks_by_ids(self, task_ids):
        return await self._get_tasks_by_ids(task_ids)

    async def mark_incomplete_tasks_as_error(self, task_ids, error: str | None = None):
        return await self._mark_incomplete(task_ids, error)

    async def get_task(self, task):
        return await self._get_task(task)

    async def set_status_if_not_canceled(self, task, status: str, error: str | None):
        return await self._set_status_if_not_canceled(task, status, error)

    async def requeue_task(
        self,
        task,
        *,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        retry_after_at: datetime | None = None,
        reschedule_attempts: int | None = None,
    ):
        return await self._requeue_task(
            task,
            reason=reason,
            metadata=metadata,
            retry_after_at=retry_after_at,
            reschedule_attempts=reschedule_attempts,
        )

    @property
    def requeue_task_mock(self) -> AsyncMock:
        return self._requeue_task

    @property
    def get_tasks_by_ids_mock(self) -> AsyncMock:
        return self._get_tasks_by_ids

    @property
    def mark_incomplete_mock(self) -> AsyncMock:
        return self._mark_incomplete

    @property
    def get_task_mock(self) -> AsyncMock:
        return self._get_task

    @property
    def set_status_if_not_canceled_mock(self) -> AsyncMock:
        return self._set_status_if_not_canceled

    @property
    def get_pending_task_ids_mock(self) -> AsyncMock:
        return self._get_pending_task_ids


@pytest.mark.asyncio
async def test_rate_limited_batch_overflow_is_rescheduled(monkeypatch):
    rate_limited_allowed = Trial(
        trial_id="rate-limited-primary",
        scenario_run_id="run-1",
        scenario_id="scenario-1",
        index_in_run=0,
        status=TrialStatus.EXECUTING,
        metadata={"attempt": "primary"},
        reschedule_attempts=1,
    )
    rate_limited_overflow = Trial(
        trial_id="rate-limited-overflow",
        scenario_run_id="run-1",
        scenario_id="scenario-1",
        index_in_run=1,
        status=TrialStatus.EXECUTING,
        metadata={"attempt": "overflow"},
        reschedule_attempts=2,
    )
    fresh_task = Trial(
        trial_id="fresh",
        scenario_run_id="run-1",
        scenario_id="scenario-1",
        index_in_run=2,
        status=TrialStatus.EXECUTING,
    )
    repo = _StubRepository()
    repo.get_tasks_by_ids_mock.return_value = [
        rate_limited_allowed,
        rate_limited_overflow,
        fresh_task,
    ]

    queue = WorkQueue(
        repo,
        runner=AsyncMock(),
        settings=QueueSettings(rate_limited_quota=1),
    )
    sentinel_retry = datetime(2024, 1, 1, tzinfo=UTC)
    queue._compute_retry_after_at = MagicMock(return_value=sentinel_retry)
    queue._execute_task = AsyncMock(return_value=True)

    results = await queue._run_batch(
        [
            rate_limited_allowed.trial_id,
            rate_limited_overflow.trial_id,
            fresh_task.trial_id,
        ],
        batch_timeout=0.1,
    )

    assert results == [True, True]
    executed_ids = [call.args[0].trial_id for call in queue._execute_task.await_args_list]
    assert executed_ids == [rate_limited_allowed.trial_id, fresh_task.trial_id]

    repo.requeue_task_mock.assert_awaited_once()
    requeue_call = repo.requeue_task_mock.await_args
    if requeue_call:
        # Rescheduling overflow tasks keeps their existing attempt count.
        assert requeue_call.kwargs["reschedule_attempts"] == 2
        assert requeue_call.kwargs["metadata"] == {"attempt": "overflow"}
        assert requeue_call.kwargs["retry_after_at"] == sentinel_retry


@pytest.mark.asyncio
async def test_execute_task_requeues_after_rate_limit(monkeypatch):
    trial = Trial(
        trial_id="trial-1",
        scenario_run_id="run-1",
        scenario_id="scenario-1",
        index_in_run=0,
        status=TrialStatus.EXECUTING,
        metadata={"existing": True},
    )
    runner = AsyncMock(side_effect=TrialRateLimitedError("throttled", retry_after_seconds=7))
    repo = _StubRepository()
    repo.get_task_mock.return_value = trial
    queue = WorkQueue(
        repo,
        runner=runner,
        settings=QueueSettings(retry_after_seconds=5, retry_attempts_limit=3),
    )
    sentinel_retry = datetime(2024, 5, 20, tzinfo=UTC)
    queue._compute_retry_after_at = MagicMock(return_value=sentinel_retry)

    result = await queue._execute_task(trial)

    assert result == "rescheduled"
    repo.requeue_task_mock.assert_awaited_once()
    if repo.requeue_task_mock.await_args:
        call_kwargs = repo.requeue_task_mock.await_args.kwargs
        assert call_kwargs["retry_after_at"] == sentinel_retry
        assert call_kwargs["reschedule_attempts"] == 1
        assert call_kwargs["metadata"] == {"existing": True}
    repo.set_status_if_not_canceled_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_task_honors_zero_retry_after(monkeypatch):
    trial = Trial(
        trial_id="trial-zero-delay",
        scenario_run_id="run-1",
        scenario_id="scenario-1",
        index_in_run=0,
        status=TrialStatus.EXECUTING,
    )
    runner = AsyncMock(side_effect=TrialRateLimitedError("throttled", retry_after_seconds=0))
    repo = _StubRepository()
    repo.get_task_mock.return_value = trial
    queue = WorkQueue(
        repo,
        runner=runner,
        settings=QueueSettings(retry_after_seconds=5, retry_attempts_limit=3),
    )
    sentinel_retry = datetime(2024, 5, 20, tzinfo=UTC)
    queue._compute_retry_after_at = MagicMock(return_value=sentinel_retry)

    result = await queue._execute_task(trial)

    assert result == "rescheduled"
    call_kwargs = queue._compute_retry_after_at.call_args.kwargs
    assert call_kwargs["base_delay"] == 0
    assert call_kwargs["next_attempt"] == 1


@pytest.mark.asyncio
async def test_run_batch_sets_timeout_error_message():
    import asyncio

    trial = Trial(
        trial_id="timeout-trial",
        scenario_run_id="run-1",
        scenario_id="scenario-1",
        index_in_run=0,
        status=TrialStatus.EXECUTING,
    )
    repo = _StubRepository()
    repo.get_tasks_by_ids_mock.return_value = [trial]

    queue = WorkQueue(
        repo,
        runner=AsyncMock(),
        settings=QueueSettings(),
    )

    async def _blocking(self, task_obj: Trial) -> bool:
        await asyncio.sleep(3600)
        return True

    queue._execute_task = _blocking.__get__(queue, WorkQueue)

    results = await queue._run_batch([trial.trial_id], batch_timeout=0.01)

    assert len(results) == 1
    assert isinstance(results[0], TimeoutError)
    repo.mark_incomplete_mock.assert_awaited_once_with([trial.trial_id], TASK_TIMEOUT_ERROR_MESSAGE)


@freeze_time("2024-01-01T00:00:00Z")
def test_compute_retry_after_applies_backoff_and_jitter(monkeypatch):
    queue = WorkQueue(
        _StubRepository(),
        runner=MagicMock(),
        settings=QueueSettings(max_retry_after_seconds=50, retry_jitter_ratio=0.5),
    )
    monkeypatch.setattr(
        background_worker.random,
        "uniform",
        lambda _min, _max: 1.5,
    )

    result = queue._compute_retry_after_at(base_delay=10, next_attempt=3)

    # base_delay=10 * 2**(next_attempt-1)=40; jitter=1.5 -> 60; clamped to max=50
    assert result == datetime(2024, 1, 1, tzinfo=UTC) + timedelta(seconds=50)


@pytest.mark.asyncio
async def test_worker_loop_triggers_batch_watchdog(monkeypatch):
    repo = _StubRepository()
    repo.get_pending_task_ids_mock.return_value = []

    loop = asyncio.get_running_loop()
    shutdown_future = loop.create_future()

    class _FakeShutdown:
        @classmethod
        def get_shutdown_task(cls, worker_name: str):
            return shutdown_future

        @classmethod
        def should_worker_shutdown(cls, worker_name: str) -> bool:
            return shutdown_future.done()

    monkeypatch.setattr(background_worker, "ShutdownManager", _FakeShutdown)

    watchdog_called = asyncio.Event()
    watchdog_runs = 0

    async def _watchdog():
        nonlocal watchdog_runs
        watchdog_runs += 1
        watchdog_called.set()

    queue = WorkQueue(
        repo,
        runner=AsyncMock(),
        settings=QueueSettings(worker_interval=0.01, batch_watchdog_interval=0.0),
        batch_watchdog=_watchdog,
    )

    worker_task = asyncio.create_task(queue.worker_loop())
    await asyncio.wait_for(watchdog_called.wait(), timeout=1)

    if not shutdown_future.done():
        shutdown_future.set_result(None)

    await asyncio.wait_for(worker_task, timeout=1)
    assert watchdog_runs >= 1
