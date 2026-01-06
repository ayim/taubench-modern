from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from agent_platform.core.evals.types import (
    Scenario,
    ScenarioBatchRun,
    ScenarioBatchRunStatistics,
    ScenarioBatchRunStatus,
    ScenarioRun,
    Trial,
    TrialStatus,
)
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.server.evals.background_worker import TASK_TIMEOUT_ERROR_MESSAGE
from agent_platform.server.evals.batch_timeout_watcher import ScenarioBatchTimeoutWatcher
from server.tests.storage.sample_model_creator import SampleModelCreator

pytest_plugins = ["server.tests.storage_fixtures"]


def _build_trial(
    scenario_run_id: str,
    scenario_id: str,
    *,
    index: int,
    status: TrialStatus,
    created_at: datetime,
) -> Trial:
    return Trial(
        trial_id=str(uuid4()),
        scenario_run_id=scenario_run_id,
        scenario_id=scenario_id,
        index_in_run=index,
        status=status,
        created_at=created_at,
        updated_at=created_at,
        status_updated_at=created_at,
    )


async def _create_scenario(storage, user_id: str, agent_id: str) -> Scenario:
    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Scenario",
        description="",
        thread_id=None,
        agent_id=agent_id,
        user_id=user_id,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hi")],
                complete=True,
            )
        ],
        metadata={},
    )
    await storage.create_scenario(scenario)
    return scenario


@pytest.mark.asyncio
async def test_batch_timeout_watcher_marks_trials(sqlite_storage, tmp_path):
    storage = sqlite_storage
    creator = SampleModelCreator(storage, tmp_path)
    agent = await creator.obtain_sample_agent()
    user_id = await creator.get_user_id()
    scenario = await _create_scenario(storage, user_id, agent.agent_id)

    created_at = datetime.now(UTC) - timedelta(hours=6)
    batch = ScenarioBatchRun(
        batch_run_id=str(uuid4()),
        agent_id=agent.agent_id,
        user_id=user_id,
        metadata={},
        scenario_ids=[scenario.scenario_id],
        status=ScenarioBatchRunStatus.RUNNING,
        statistics=ScenarioBatchRunStatistics(total_scenarios=1),
        created_at=created_at,
        updated_at=created_at,
    )
    created_batch = await storage.create_scenario_batch_run(batch)

    scenario_run = ScenarioRun(
        scenario_run_id=str(uuid4()),
        scenario_id=scenario.scenario_id,
        user_id=user_id,
        batch_run_id=created_batch.batch_run_id,
        num_trials=3,
        configuration={},
        created_at=created_at,
    )
    trials = [
        _build_trial(
            scenario_run.scenario_run_id,
            scenario.scenario_id,
            index=0,
            status=TrialStatus.PENDING,
            created_at=created_at,
        ),
        _build_trial(
            scenario_run.scenario_run_id,
            scenario.scenario_id,
            index=1,
            status=TrialStatus.EXECUTING,
            created_at=created_at,
        ),
        _build_trial(
            scenario_run.scenario_run_id,
            scenario.scenario_id,
            index=2,
            status=TrialStatus.COMPLETED,
            created_at=created_at,
        ),
    ]
    await storage.create_scenario_run(scenario_run.with_trials(trials))

    watcher = ScenarioBatchTimeoutWatcher(storage, max_age=timedelta(hours=5))
    await watcher.check_for_timeouts()

    refreshed_batch = await storage.get_scenario_batch_run(created_batch.batch_run_id)
    assert refreshed_batch is not None
    assert refreshed_batch.status == ScenarioBatchRunStatus.FAILED
    assert refreshed_batch.completed_at is not None
    stats = refreshed_batch.statistics
    assert stats.total_scenarios == 1
    assert stats.failed_scenarios == 1
    assert stats.completed_scenarios == 0
    assert stats.total_trials == 3
    assert stats.failed_trials == 2
    assert stats.completed_trials == 1

    updated_trials = await storage.list_scenario_run_trials(scenario_run.scenario_run_id)
    statuses = {trial.index_in_run: trial.status for trial in updated_trials}
    assert statuses[0] == TrialStatus.ERROR
    assert statuses[1] == TrialStatus.ERROR
    assert statuses[2] == TrialStatus.COMPLETED
    assert all(
        trial.error_message == TASK_TIMEOUT_ERROR_MESSAGE for trial in updated_trials if trial.index_in_run in {0, 1}
    )


@pytest.mark.asyncio
async def test_batch_timeout_watcher_ignores_recent_batches(sqlite_storage, tmp_path):
    storage = sqlite_storage
    creator = SampleModelCreator(storage, tmp_path)
    agent = await creator.obtain_sample_agent()
    user_id = await creator.get_user_id()
    scenario = await _create_scenario(storage, user_id, agent.agent_id)

    now = datetime.now(UTC)
    batch = ScenarioBatchRun(
        batch_run_id=str(uuid4()),
        agent_id=agent.agent_id,
        user_id=user_id,
        metadata={},
        scenario_ids=[scenario.scenario_id],
        status=ScenarioBatchRunStatus.RUNNING,
        statistics=ScenarioBatchRunStatistics(total_scenarios=1),
        created_at=now,
        updated_at=now,
    )
    created_batch = await storage.create_scenario_batch_run(batch)

    scenario_run = ScenarioRun(
        scenario_run_id=str(uuid4()),
        scenario_id=scenario.scenario_id,
        user_id=user_id,
        batch_run_id=created_batch.batch_run_id,
        num_trials=1,
        configuration={},
        created_at=now,
    )
    trial = _build_trial(
        scenario_run.scenario_run_id,
        scenario.scenario_id,
        index=0,
        status=TrialStatus.PENDING,
        created_at=now,
    )
    await storage.create_scenario_run(scenario_run.with_trials([trial]))

    watcher = ScenarioBatchTimeoutWatcher(storage, max_age=timedelta(hours=5))
    await watcher.check_for_timeouts()

    refreshed_batch = await storage.get_scenario_batch_run(created_batch.batch_run_id)
    assert refreshed_batch is not None
    assert refreshed_batch.status == ScenarioBatchRunStatus.RUNNING
    assert refreshed_batch.completed_at is None

    updated_trials = await storage.list_scenario_run_trials(scenario_run.scenario_run_id)
    assert updated_trials[0].status == TrialStatus.PENDING


@pytest.mark.asyncio
async def test_batch_timeout_watcher_marks_completed_batches(sqlite_storage, tmp_path):
    storage = sqlite_storage
    creator = SampleModelCreator(storage, tmp_path)
    agent = await creator.obtain_sample_agent()
    user_id = await creator.get_user_id()
    scenario = await _create_scenario(storage, user_id, agent.agent_id)

    created_at = datetime.now(UTC) - timedelta(hours=6)
    batch = ScenarioBatchRun(
        batch_run_id=str(uuid4()),
        agent_id=agent.agent_id,
        user_id=user_id,
        metadata={},
        scenario_ids=[scenario.scenario_id],
        status=ScenarioBatchRunStatus.RUNNING,
        statistics=ScenarioBatchRunStatistics(total_scenarios=1),
        created_at=created_at,
        updated_at=created_at,
    )
    created_batch = await storage.create_scenario_batch_run(batch)

    scenario_run = ScenarioRun(
        scenario_run_id=str(uuid4()),
        scenario_id=scenario.scenario_id,
        user_id=user_id,
        batch_run_id=created_batch.batch_run_id,
        num_trials=1,
        configuration={},
        created_at=created_at,
    )
    trial = _build_trial(
        scenario_run.scenario_run_id,
        scenario.scenario_id,
        index=0,
        status=TrialStatus.COMPLETED,
        created_at=created_at,
    )
    await storage.create_scenario_run(scenario_run.with_trials([trial]))

    watcher = ScenarioBatchTimeoutWatcher(storage, max_age=timedelta(hours=5))
    await watcher.check_for_timeouts()

    refreshed_batch = await storage.get_scenario_batch_run(created_batch.batch_run_id)
    assert refreshed_batch is not None
    assert refreshed_batch.status == ScenarioBatchRunStatus.COMPLETED
    assert refreshed_batch.completed_at is not None
    stats = refreshed_batch.statistics
    assert stats.total_trials == 1
    assert stats.completed_trials == 1
    assert stats.failed_trials == 0
