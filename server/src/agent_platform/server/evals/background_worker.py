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
import traceback
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable

from agent_platform.server.shutdown_manager import ShutdownManager
from agent_platform.server.storage.errors import TrialAlreadyCanceledError

logger = logging.getLogger(__name__)

# Worker name constant for shutdown manager
WORKER_NAME = "evals"


@runtime_checkable
class Task(Protocol):
    def get_status(self) -> str: ...
    def get_unique_identifier(self) -> str: ...


T = TypeVar("T", bound=Task)


@runtime_checkable
class TaskRepository(Protocol[T]):
    """Abstracts access to tasks and their persistence.

    Implementations should be *idempotent* and resilient. The queue will call
    these methods in the sequences shown below.
    """

    async def get_pending_task_ids(self, max_batch_size: int) -> Sequence[str]: ...

    async def get_tasks_by_ids(self, task_ids: Sequence[str]) -> Sequence[T]: ...

    async def mark_incomplete_tasks_as_error(self, task_ids: Sequence[str]) -> None: ...

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
    max_parallel_in_process: int = 8


class WorkQueue(Generic[T]):
    def __init__(
        self,
        repository: TaskRepository[T],
        runner: TaskRunner[T],
        *,
        settings: QueueSettings | None = None,
        validator: TaskValidator[T] | None = None,
        callbacks: TaskCallbacks[T] | None = None,
    ) -> None:
        self.repo = repository
        self.runner = runner
        self.validator = validator
        self.callbacks = callbacks
        self.settings = settings or QueueSettings()

    async def worker_loop(self) -> None:
        """Continuously polls for work and processes it in batches."""
        while not ShutdownManager.should_worker_shutdown(WORKER_NAME):
            logger.info("searching for tasks to process")
            try:
                await self._worker_iteration()
            except Exception as exc:
                logger.error("Error processing tasks: %s", exc, exc_info=exc)

            await asyncio.sleep(self.settings.worker_interval)

        logger.info("finished worker loop")

    async def _worker_iteration(self) -> None:
        max_batch_size = self.settings.max_parallel_in_process
        task_ids = await self.repo.get_pending_task_ids(max_batch_size)
        logger.info("Found %d tasks to process. %r", len(task_ids), task_ids)

        if not task_ids:
            return

        logger.info("Dispatching tasks %s", task_ids)
        results = await self._run_batch(task_ids, self.settings.batch_timeout)
        logger.info("Completed %d tasks concurrently", len(results))

    async def _run_batch(  # noqa: C901, PLR0912
        self,
        task_ids: Sequence[str],
        batch_timeout: float,
    ) -> Sequence[bool | BaseException]:
        tasks = await self.repo.get_tasks_by_ids(list(task_ids))
        if not tasks:
            return []

        task_map: dict[str, asyncio.Task[bool]] = {}

        for t in tasks:
            status = t.get_status()
            if status in {"CANCELED"}:
                logger.info("Task %s was cancelled during scheduling. Skipping.", t)
                continue
            logger.info("Dispatching task (batch run) %s", t)
            task_id = t.get_unique_identifier()
            task_map[task_id] = asyncio.create_task(self._execute_task(t))

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
            asyncio.wait(
                task_map.values(), timeout=batch_timeout, return_when=asyncio.ALL_COMPLETED
            )
        )

        results: list[bool | BaseException] = []
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
                    logger.info("Task %s completed normally", task_id)
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
            await self.repo.mark_incomplete_tasks_as_error(incomplete_ids)

        return results

    async def _execute_task(self, task_obj: T) -> bool:
        """Run the task, compute final status, persist, and trigger callbacks."""
        ran_ok = False
        try:
            logger.info("Starting execution on task")
            ran_ok = await self.runner(task_obj)
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
            await self.repo.set_status_if_not_canceled(
                refreshed_task, final_status, final_error_message
            )

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


async def _safe_call(fn: Callable[[T, str], Awaitable[None]] | None, task: T, status: str) -> None:
    if not fn:
        return
    try:
        await fn(task, status)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Callback failed: %s", e, exc_info=e)
