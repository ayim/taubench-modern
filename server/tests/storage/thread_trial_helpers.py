from __future__ import annotations

from uuid import uuid4

from agent_platform.core.agent.agent import Agent
from agent_platform.core.evals.types import Scenario, ScenarioRun, Trial
from agent_platform.core.thread import Thread
from agent_platform.server.storage.postgres import PostgresStorage
from agent_platform.server.storage.sqlite import SQLiteStorage

StorageLike = PostgresStorage | SQLiteStorage


async def create_trial_with_thread(
    storage: StorageLike,
    user_id: str,
    agent: Agent,
) -> tuple[Scenario, ScenarioRun, Trial, Thread]:
    """
    Helper to seed a scenario/trial pair with a backing thread for storage tests.
    """
    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Evaluation scenario",
        description="Seeded for thread cleanup tests",
        thread_id=None,
        agent_id=agent.agent_id,
        user_id=user_id,
        messages=[],
    )
    await storage.create_scenario(scenario)

    scenario_run_id = str(uuid4())
    trial = Trial(
        trial_id=str(uuid4()),
        scenario_run_id=scenario_run_id,
        scenario_id=scenario.scenario_id,
        index_in_run=0,
    )
    scenario_run = ScenarioRun(
        scenario_run_id=scenario_run_id,
        scenario_id=scenario.scenario_id,
        user_id=user_id,
        num_trials=1,
        configuration={},
        trials=[trial],
    )
    await storage.create_scenario_run(scenario_run)

    trial_thread = Thread(
        user_id=user_id,
        agent_id=agent.agent_id,
        name="Trial Thread",
        thread_id=str(uuid4()),
        messages=[],
        metadata={"trial_id": trial.trial_id},
        trial_id=trial.trial_id,
    )
    await storage.upsert_thread(user_id, trial_thread)
    await storage.set_trial_thread(trial.trial_id, trial_thread.thread_id)

    return scenario, scenario_run, trial, trial_thread
