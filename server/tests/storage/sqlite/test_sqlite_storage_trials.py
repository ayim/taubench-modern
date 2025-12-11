from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_get_pending_trial_ids_returns_rate_limited_trials(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
    sample_thread,
) -> None:
    from agent_platform.core.evals.types import Scenario, ScenarioRun, Trial, TrialStatus

    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Scenario",
        description="Sample scenario",
        thread_id=sample_thread.thread_id,
        agent_id=sample_agent.agent_id,
        user_id=sample_user_id,
        messages=sample_thread.messages,
    )
    await storage.create_scenario(scenario)

    scenario_run_id = str(uuid4())
    ready_trial = Trial(
        trial_id=str(uuid4()),
        scenario_run_id=scenario_run_id,
        scenario_id=scenario.scenario_id,
        thread_id=sample_thread.thread_id,
        index_in_run=0,
        status=TrialStatus.EXECUTING,
    )
    throttled_trial = Trial(
        trial_id=str(uuid4()),
        scenario_run_id=scenario_run_id,
        scenario_id=scenario.scenario_id,
        thread_id=sample_thread.thread_id,
        index_in_run=1,
        status=TrialStatus.EXECUTING,
    )
    scenario_run = ScenarioRun(
        scenario_run_id=scenario_run_id,
        scenario_id=scenario.scenario_id,
        user_id=sample_user_id,
        batch_run_id=None,
        num_trials=2,
        configuration={},
        trials=[ready_trial, throttled_trial],
    )
    await storage.create_scenario_run(scenario_run)

    ready_time = datetime.now(UTC) - timedelta(minutes=1)
    future_time = datetime.now(UTC) + timedelta(hours=1)
    await storage.requeue_trial(
        ready_trial.trial_id,
        reason="rate limited",
        retry_after_at=ready_time,
        reschedule_attempts=1,
    )
    await storage.requeue_trial(
        throttled_trial.trial_id,
        reason="rate limited",
        retry_after_at=future_time,
        reschedule_attempts=1,
    )

    claimed_ids = await storage.get_pending_trial_ids(limit=5)

    assert ready_trial.trial_id in claimed_ids
    assert throttled_trial.trial_id not in claimed_ids

    claimed_trial = await storage.get_trial(ready_trial.trial_id)
    assert claimed_trial is not None
    assert claimed_trial.status == TrialStatus.EXECUTING

    still_pending_trial = await storage.get_trial(throttled_trial.trial_id)
    assert still_pending_trial is not None
    assert still_pending_trial.status == TrialStatus.PENDING
