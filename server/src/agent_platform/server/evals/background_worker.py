"""
Generic, asyncio-based WorkQueue that can process *any* task type.

Design:
- TaskRepository[T]: abstracts storage/DB operations.
- TaskRunner[T]: executes a task and returns success/failure.
- TaskValidator[T]: optional, determines a domain-specific final status string.
- TaskCallbacks[T]: optional, invoked after final status is determined.
- WorkQueue[T]: orchestrates polling, batching, timeouts, and status updates.

"""

import asyncio
import logging
import random
import traceback
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from agent_platform.server.evals.errors import TrialRateLimitedError
from agent_platform.server.shutdown_manager import ShutdownManager
from agent_platform.server.storage.errors import TrialAlreadyCanceledError

logger = logging.getLogger(__name__)

# Worker name constant for shutdown manager
WORKER_NAME = "evals"
TASK_TIMEOUT_ERROR_MESSAGE = "Trial timed out while executing."


@runtime_checkable
class Task(Protocol):
    def get_status(self) -> str: ...
    def get_unique_identifier(self) -> str: ...
    def get_reschedule_attempts(self) -> int: ...


T = TypeVar("T", bound=Task)


@runtime_checkable
class TaskRepository(Protocol[T]):
    """Abstracts access to tasks and their persistence.

    Implementations should be *idempotent* and resilient. The queue will call
    these methods in the sequences shown below.
    """

    async def get_pending_task_ids(self, max_batch_size: int) -> Sequence[str]: ...

    async def get_tasks_by_ids(self, task_ids: Sequence[str]) -> Sequence[T]: ...

    async def mark_incomplete_tasks_as_error(self, task_ids: Sequence[str], error: str | None = None) -> None: ...

    async def get_task(self, task: T) -> T | None:
        """Return the latest persisted task, if available.
        May return None if unknown/not stored.
        """
        ...

    async def set_status_if_not_canceled(self, task: T, status: str, error: str | None) -> None:
        """
        Set the status if the task has not been cancelled yet
        """
        ...

    async def requeue_task(
        self,
        task: T,
        *,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        retry_after_at: datetime | None = None,
        reschedule_attempts: int | None = None,
    ) -> None: ...


class TaskRunner(Protocol[T]):  # type: ignore
    """Runs a task. Return True on success, False on failure."""

    async def __call__(self, task: T) -> bool:  # pragma: no cover - signature only
        ...


class TaskValidator(Protocol[T]):  # type: ignore
    """Maps a completed task to a final, domain-specific status string.

    If you don't need a validator, pass None and the queue will set
    status to "COMPLETED" on True and "ERROR" on False.
    """

    async def __call__(self, task: T, ran_successfully: bool) -> tuple[str, str | None]: ...


class TaskCallbacks(Protocol[T]):  # type: ignore
    """Optional lifecycle callbacks after status is finalized."""

    async def on_complete(self, task: T, final_status: str) -> None: ...


@dataclass(slots=True)
class QueueSettings:
    worker_interval: float = 5.0
    batch_timeout: float = 300.0
    batch_watchdog_interval: float = 300.0
    batch_run_timeout_seconds: float = 24 * 60 * 60
    max_parallel_in_process: int = 8
    retry_after_seconds: float = 60.0
    retry_attempts_limit: int = 3
    max_retry_after_seconds: float = 900.0
    retry_jitter_ratio: float = 0.2
    rate_limited_quota: int = 1


class WorkQueue(Generic[T]):
    def __init__(
        self,
        repository: TaskRepository[T],
        runner: TaskRunner[T],
        *,
        settings: QueueSettings | None = None,
        validator: TaskValidator[T] | None = None,
        callbacks: TaskCallbacks[T] | None = None,
        batch_watchdog: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.repo = repository
        self.runner = runner
        self.validator = validator
        self.callbacks = callbacks
        self.settings = settings or QueueSettings()
        self._batch_watchdog = batch_watchdog
        self._last_watchdog_run: datetime | None = None

    async def worker_loop(self) -> None:
        """Continuously polls for work and processes it in batches."""
        shutdown_task = ShutdownManager.get_shutdown_task(WORKER_NAME)
        if shutdown_task is None:
            raise RuntimeError(f"Shutdown task not found for {WORKER_NAME} worker")

        while not ShutdownManager.should_worker_shutdown(WORKER_NAME):
            try:
                await self._maybe_run_batch_watchdog()
                await self._worker_iteration()
            except Exception as exc:
                logger.error("Error processing tasks: %s", exc, exc_info=exc)

            await asyncio.wait([shutdown_task], timeout=self.settings.worker_interval)

        logger.debug("finished eval worker loop")

    async def _worker_iteration(self) -> None:
        max_batch_size = self.settings.max_parallel_in_process
        task_ids = await self.repo.get_pending_task_ids(max_batch_size)

        if not task_ids:
            return

        logger.info("Dispatching eval tasks %s", task_ids)
        results = await self._run_batch(task_ids, self.settings.batch_timeout)
        if results:
            summary = self._summarize_batch_results(results)
            logger.info(
                ("Completed batch: total=%d succeeded=%d failed=%d rescheduled=%d canceled=%d timeouts=%d"),
                summary["total"],
                summary["succeeded"],
                summary["failed"],
                summary["rescheduled"],
                summary["canceled"],
                summary["timeouts"],
            )
        else:
            logger.info("Completed 0 eval tasks")

    async def _run_batch(
        self,
        task_ids: Sequence[str],
        batch_timeout: float,
    ) -> Sequence[bool | str | BaseException]:
        tasks = await self.repo.get_tasks_by_ids(list(task_ids))
        if not tasks:
            return []

        tasks, overflow_rate_limited = self._filter_rate_limited_tasks(tasks)
        if overflow_rate_limited:
            await self._reschedule_overflow_rate_limited_tasks(overflow_rate_limited)

        if not tasks:
            return []

        task_map: dict[str, asyncio.Task[bool | str]] = {}

        for t in tasks:
            status = t.get_status()
            if status in {"CANCELED"}:
                logger.info("Task %s was cancelled during scheduling. Skipping.", t)
                continue
            logger.info("Dispatching task (batch run) %s", t)
            task_id = t.get_unique_identifier()
            task_map[task_id] = asyncio.create_task(self._execute_task(t), name=f"eval-task-{task_id}")

        stop_event = asyncio.Event()
        canceled_by_db: set[str] = set()
        watcher = asyncio.create_task(
            self._batch_cancel_watcher(
                task_map=task_map,
                stop_event=stop_event,
                poll_interval=30,  # 30 seconds
                canceled_by_db=canceled_by_db,
            ),
            name="batch:cancel-watcher",
        )

        done, pending = await asyncio.shield(
            asyncio.wait(task_map.values(), timeout=batch_timeout, return_when=asyncio.ALL_COMPLETED)
        )

        results: list[bool | str | BaseException] = []
        incomplete_ids: list[str] = []

        if pending:
            logger.warning(
                "Batch timeout (%.2fs) exceeded for %d of %d tasks",
                batch_timeout,
                len(pending),
                len(task_map),
            )
            for task in pending:
                task.cancel()

        stop_event.set()
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)

        # Preserve order alongside underlying tasks sequence
        for t_obj, async_task in zip(tasks, task_map.values(), strict=True):
            task_id = t_obj.get_unique_identifier()
            if async_task in done or async_task.done():
                try:
                    res = await asyncio.shield(async_task)
                    results.append(res)
                    if res == "rescheduled":
                        logger.info("Task %s rescheduled after rate limit", task_id)
                    elif res is True:
                        logger.info("Task %s completed normally", task_id)
                    else:
                        logger.info("Task %s completed with result=%s", task_id, res)
                except asyncio.CancelledError:
                    if task_id in canceled_by_db:
                        results.append(asyncio.CancelledError())
                        logger.info("Task %s canceled via DB status", task_id)
                    else:
                        incomplete_ids.append(task_id)
                        results.append(TimeoutError("Task timeout exceeded"))
                        logger.error("Task %s timed out, marking as ERROR", task_id)
                except Exception as e:
                    results.append(e)
                    logger.warning("Task %s failed with error: %s", task_id, e, exc_info=e)
            else:
                incomplete_ids.append(task_id)
                results.append(TimeoutError("Task timeout exceeded"))
                logger.error("Task %s timed out, marking as ERROR", task_id)

        if len(incomplete_ids) > 0:
            await self.repo.mark_incomplete_tasks_as_error(incomplete_ids, TASK_TIMEOUT_ERROR_MESSAGE)

        return results

    def _filter_rate_limited_tasks(self, tasks: Sequence[T]) -> tuple[list[T], list[T]]:
        remaining: list[T] = []
        overflow: list[T] = []
        rate_limited_quota = self.settings.rate_limited_quota

        for task in tasks:
            if self._is_rate_limited_task(task):
                if rate_limited_quota > 0:
                    remaining.append(task)
                    rate_limited_quota -= 1
                else:
                    overflow.append(task)
            else:
                remaining.append(task)

        return remaining, overflow

    async def _reschedule_overflow_rate_limited_tasks(self, tasks: Sequence[T]) -> None:
        for task in tasks:
            metadata = getattr(task, "metadata", {})
            current_attempts = task.get_reschedule_attempts()
            # attempts is not incremented because
            # in this case we didn't hit a rate limit
            # but we are enforcing rate-limited tasks per batch
            next_attempt = current_attempts if current_attempts > 0 else 1
            delay = self.settings.retry_after_seconds

            try:
                retry_after_at = self._compute_retry_after_at(base_delay=delay, next_attempt=next_attempt)
                logger.info(
                    "Task %s requeued immediately, delay %.2fs (next run at %s)",
                    task.get_unique_identifier(),
                    delay,
                    retry_after_at.isoformat(),
                )
                await self.repo.requeue_task(
                    task,
                    reason="Rescheduled to enforce rate-limited tasks per batch",
                    metadata=metadata,
                    retry_after_at=retry_after_at,
                    reschedule_attempts=current_attempts,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "Failed to requeue rate-limited task %s: %s",
                    task.get_unique_identifier(),
                    exc,
                    exc_info=exc,
                )
            else:
                logger.info(
                    "Rate-limited task %s rescheduled for later batch",
                    task.get_unique_identifier(),
                )

    def _is_rate_limited_task(self, task: T) -> bool:
        return task.get_reschedule_attempts() > 0

    def _summarize_batch_results(self, results: Sequence[bool | str | BaseException]) -> dict[str, int]:
        summary = {
            "total": len(results),
            "succeeded": 0,
            "failed": 0,
            "rescheduled": 0,
            "canceled": 0,
            "timeouts": 0,
        }

        for result in results:
            if result is True:
                summary["succeeded"] += 1
            elif result is False:
                summary["failed"] += 1
            elif result == "rescheduled":
                summary["rescheduled"] += 1
            elif isinstance(result, asyncio.CancelledError):
                summary["canceled"] += 1
            elif isinstance(result, TimeoutError):
                summary["timeouts"] += 1
            else:
                summary["failed"] += 1

        return summary

    async def _execute_task(self, task_obj: T) -> bool | str:
        """Run the task, compute final status, persist, and trigger callbacks."""
        ran_ok = False
        rate_limited_error: TrialRateLimitedError | None = None
        try:
            logger.info("Starting execution on task")
            ran_ok = await self.runner(task_obj)
        except TrialRateLimitedError as rate_exc:
            logger.warning(
                "Task %s hit rate limits; scheduling retry.",
                task_obj.get_unique_identifier(),
            )
            rate_limited_error = rate_exc
            ran_ok = False
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Error executing task: %s", e, exc_info=e)
            # fall through; we'll set ERROR below
            ran_ok = False

        # Check current status to avoid overwriting terminal states (e.g., CANCELLED)
        refreshed_task = await self.repo.get_task(task_obj)

        if refreshed_task is None:
            logger.error("Failed to get current task")
            return False

        current_status = refreshed_task.get_status()
        logger.info(f"after a run, the task status is {current_status}")
        # If user/system moved it to a terminal state, don't overwrite
        if current_status in {"CANCELED"}:
            logger.info("Task was cancelled during execution: leaving status as CANCELED")
            if self.callbacks:
                await _safe_call(self.callbacks.on_complete, refreshed_task, "CANCELED")
            return ran_ok

        if rate_limited_error is not None:
            metadata_source = getattr(refreshed_task, "metadata", {}) or {}
            if not isinstance(metadata_source, dict):
                metadata_source = {}
            metadata = dict(metadata_source)
            current_attempts = refreshed_task.get_reschedule_attempts()
            next_attempt = current_attempts + 1
            max_attempts = self.settings.retry_attempts_limit
            if max_attempts > 0 and next_attempt > max_attempts:
                message = f"Rate limit retries exceeded after {next_attempt - 1} attempts"
                await self.repo.set_status_if_not_canceled(
                    refreshed_task,
                    "ERROR",
                    message,
                )
                logger.error(
                    "Task %s exceeded rate-limit reschedule cap (%d)",
                    refreshed_task.get_unique_identifier(),
                    max_attempts,
                )
                return False

            custom_delay = rate_limited_error.retry_after_seconds
            delay = custom_delay if custom_delay is not None else self.settings.retry_after_seconds
            retry_after_at = self._compute_retry_after_at(base_delay=delay, next_attempt=next_attempt)

            try:
                await self.repo.requeue_task(
                    refreshed_task,
                    reason=str(rate_limited_error) if str(rate_limited_error) else None,
                    metadata=metadata,
                    retry_after_at=retry_after_at,
                    reschedule_attempts=next_attempt,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "Failed to requeue rate-limited task %s: %s",
                    refreshed_task.get_unique_identifier(),
                    exc,
                    exc_info=exc,
                )
                # fallback: mark as error so it won't loop forever
            else:
                logger.info(
                    "Task %s requeued after rate limit (%d/%s), delay %.2fs (next run at %s)",
                    refreshed_task.get_unique_identifier(),
                    next_attempt,
                    max_attempts if max_attempts > 0 else "∞",
                    delay,
                    retry_after_at.isoformat(),
                )
                return "rescheduled"

        # Determine final status
        if self.validator is not None:
            try:
                final_status, final_error_message = await self.validator(refreshed_task, ran_ok)
            except Exception as e:  # pragma: no cover - defensive
                traceback.print_exc()
                logger.error("Validator failed: %s; falling back to default", e)
                final_status = "COMPLETED" if ran_ok else "ERROR"
                final_error_message = "Unexpected error"
        else:
            final_status = "COMPLETED" if ran_ok else "ERROR"

        # Persist final status
        try:
            await self.repo.set_status_if_not_canceled(refreshed_task, final_status, final_error_message)

            logger.info("Finalized task with status: %s", final_status)

            # Callbacks
            if self.callbacks:
                await _safe_call(self.callbacks.on_complete, refreshed_task, final_status)
        except TrialAlreadyCanceledError:  # pragma: no cover - defensive
            logger.info("Task was cancelled during validation: validation result is ignored.")
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Failed to persist status '%s': %s", final_status, e, exc_info=e)

        return ran_ok

    async def _batch_cancel_watcher(
        self,
        *,
        task_map: dict[str, asyncio.Task],
        stop_event: asyncio.Event,
        poll_interval: float,
        canceled_by_db: set[str],
    ) -> None:
        """Single watcher that polls DB for statuses of all still-pending tasks."""
        try:
            while not stop_event.is_set():
                logger.info("Checking statuses of still-pending tasks.")
                pending_ids = [tid for tid, at in task_map.items() if not at.done()]
                if not pending_ids:
                    break

                try:
                    pending_tasks = await self.repo.get_tasks_by_ids(pending_ids)
                except Exception as e:
                    logger.warning("Batch watcher: status poll failed: %s", e, exc_info=e)
                    pending_tasks = []

                for task in pending_tasks:
                    status = task.get_status()
                    if status == "CANCELED":
                        task_id = task.get_unique_identifier()
                        at = task_map.get(task_id)
                        if at is not None and not at.done():
                            logger.info("DB status CANCELED -> canceling task %s", task_id)
                            canceled_by_db.add(task_id)
                            at.cancel()

                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
                except TimeoutError:
                    # normal: wake up to poll again
                    pass
        except asyncio.CancelledError:
            # shutting down watcher
            pass

    def _compute_retry_after_at(self, base_delay: float, next_attempt: int):
        """Compute retry after date"""
        backoff_multiplier = 2 ** max(next_attempt - 1, 0)
        delay = base_delay * backoff_multiplier
        max_delay = self.settings.max_retry_after_seconds
        if max_delay:
            delay = min(delay, max_delay)
        jitter_ratio = max(self.settings.retry_jitter_ratio, 0)
        if jitter_ratio > 0:
            jitter = random.uniform(1 - jitter_ratio, 1 + jitter_ratio)
            delay = delay * jitter
        if max_delay:
            delay = min(delay, max_delay)
        return datetime.now(UTC) + timedelta(seconds=delay)

    async def _maybe_run_batch_watchdog(self) -> None:
        """Periodically run an optional batch watchdog."""
        if not self._batch_watchdog:
            return

        now = datetime.now(UTC)
        last_run = self._last_watchdog_run
        interval = self.settings.batch_watchdog_interval

        if last_run and (now - last_run).total_seconds() < interval:
            return

        try:
            await self._batch_watchdog()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Batch watchdog failed: %s", exc, exc_info=exc)
        finally:
            self._last_watchdog_run = now


async def _safe_call(fn: Callable[[T, str], Awaitable[None]] | None, task: T, status: str) -> None:
    if not fn:
        return
    try:
        await fn(task, status)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Callback failed: %s", e, exc_info=e)
