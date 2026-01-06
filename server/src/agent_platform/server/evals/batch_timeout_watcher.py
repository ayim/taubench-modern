import asyncio
import logging
from datetime import UTC, datetime, timedelta

from agent_platform.core.evals.types import (
    ScenarioBatchRun,
    ScenarioBatchRunStatistics,
    ScenarioBatchRunStatus,
    Trial,
)
from agent_platform.server.evals.background_worker import TASK_TIMEOUT_ERROR_MESSAGE
from agent_platform.server.storage.base import BaseStorage

logger = logging.getLogger(__name__)


class ScenarioBatchTimeoutWatcher:
    """Background helper that marks stale batch runs as failed."""

    def __init__(self, storage: BaseStorage, *, max_age: timedelta):
        self._storage = storage
        self._max_age = max_age

    async def __call__(self) -> None:
        await self.check_for_timeouts()

    async def check_for_timeouts(self) -> None:
        """Fail batches whose creation date exceeds the allowed duration."""
        now = datetime.now(UTC)
        cutoff = now - self._max_age
        batches = await self._storage.list_active_scenario_batch_runs()

        for batch in batches:
            created_at = self._normalize_datetime(batch.created_at)
            if created_at <= cutoff:
                await self._timeout_batch(batch, now)

    async def _timeout_batch(self, batch: ScenarioBatchRun, completed_at: datetime) -> None:
        statistics, derived_status = await self._compute_batch_statistics(batch)
        if derived_status in TERMINAL_BATCH_STATUSES:
            await self._storage.update_scenario_batch_run(
                batch.batch_run_id,
                status=derived_status,
                statistics=statistics,
                completed_at=batch.completed_at or completed_at,
            )
            logger.info(
                "Scenario batch reached terminal state before watchdog timeout "
                "(batch_run_id=%s agent_id=%s derived_status=%s)",
                batch.batch_run_id,
                batch.agent_id,
                derived_status,
            )
            return

        affected_trials = await self._storage.mark_active_batch_trials_as_failed(
            batch.batch_run_id,
            error=TASK_TIMEOUT_ERROR_MESSAGE,
        )
        updated_stats, _ = await self._compute_batch_statistics(batch)

        await self._storage.update_scenario_batch_run(
            batch.batch_run_id,
            status=ScenarioBatchRunStatus.FAILED,
            statistics=updated_stats,
            completed_at=completed_at,
        )
        logger.warning(
            "Scenario batch exceeded maximum execution duration (batch_run_id=%s agent_id=%s affected_trials=%d)",
            batch.batch_run_id,
            batch.agent_id,
            len(affected_trials),
        )

    async def _compute_batch_statistics(
        self, batch: ScenarioBatchRun
    ) -> tuple[ScenarioBatchRunStatistics, ScenarioBatchRunStatus]:
        """Recompute aggregate statistics after mutating trial statuses."""
        scenario_runs = await self._storage.list_scenario_runs_for_batch(batch.batch_run_id)
        expected_scenarios = len(batch.scenario_ids) or len(scenario_runs)
        if not scenario_runs:
            statistics = ScenarioBatchRunStatistics(total_scenarios=expected_scenarios)
            return statistics, ScenarioBatchRunStatus.PENDING

        trials_per_run: dict[str, list[Trial]] = {}
        trial_lists = await asyncio.gather(
            *(self._storage.list_scenario_run_trials(run.scenario_run_id) for run in scenario_runs)
        )
        for run, trials in zip(scenario_runs, trial_lists, strict=True):
            trials_per_run[run.scenario_run_id] = trials

        return ScenarioBatchRunStatistics.from_trials(
            trials_per_run,
            expected_scenarios=expected_scenarios,
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.min.replace(tzinfo=UTC)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


TERMINAL_BATCH_STATUSES = {
    ScenarioBatchRunStatus.COMPLETED,
    ScenarioBatchRunStatus.CANCELED,
    ScenarioBatchRunStatus.FAILED,
}
