from dataclasses import dataclass
from typing import Any, Self
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.evals.types import Scenario, ScenarioRun, Trial, TrialStatus
from agent_platform.core.thread.thread import Thread
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth.handlers import AuthedUser
from agent_platform.server.constants import EVALS_SYSTEM_USER_SUB
from agent_platform.server.evals.advisor import (
    ScenarioSuggestion,
)
from agent_platform.server.evals.advisor import (
    suggest_scenario_from_thread as _suggest_scenario_from_thread,
)

router = APIRouter()
logger = get_logger(__name__)


@dataclass(frozen=True)
class CreateScenarioPayload:
    name: str
    description: str
    thread_id: str

    @classmethod
    def to_scenario(cls, payload: Self, user_id: str, thread: Thread) -> Scenario:
        def trim_initial_agents(messages):
            trimmed = []
            skip = True
            for m in messages:
                if skip and m.role == "agent":
                    continue
                skip = False
                trimmed.append(m)
            return trimmed

        # TODO the prompt for LLM judges is required to start with a user message
        # this is a quick fix to skip the initial agent welcome message(s)
        # that would result in an error.
        # more info https://sema4ai.slack.com/archives/C08HF1FADTQ/p1757927280879779
        messages = trim_initial_agents(thread.messages)
        return Scenario(
            scenario_id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            thread_id=thread.thread_id,
            user_id=user_id,
            agent_id=thread.agent_id,
            messages=messages,
        )


@router.post("/scenarios", response_model=Scenario)
async def create_scenario(
    payload: CreateScenarioPayload, user: AuthedUser, storage: StorageDependency
):
    thread = await storage.get_thread(user.user_id, payload.thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    scenario = CreateScenarioPayload.to_scenario(payload, user.user_id, thread)

    return await storage.create_scenario(scenario)


@dataclass(frozen=True)
class SuggestScenarioPayload:
    thread_id: str
    max_options: int = 1


@router.post("/scenarios/suggest", response_model=ScenarioSuggestion)
async def suggest_scenario_from_thread(
    payload: SuggestScenarioPayload, user: AuthedUser, storage: StorageDependency
):
    thread = await storage.get_thread(user.user_id, payload.thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    suggestion = await _suggest_scenario_from_thread(user, thread, storage)

    if suggestion is None:
        raise HTTPException(status_code=500, detail="Unexpected error")

    return suggestion


@router.get("/scenarios", response_model=list[Scenario])
async def list_scenarios(
    user: AuthedUser,
    storage: StorageDependency,
    limit: int | None = None,
    agent_id: str | None = None,
):
    return await storage.list_scenarios(limit=limit, agent_id=agent_id)


@router.get("/scenarios/{scenario_id}", response_model=Scenario)
async def get_scenario(scenario_id: str, user: AuthedUser, storage: StorageDependency):
    return await storage.get_scenario(scenario_id=scenario_id)


@router.delete("/scenarios/{scenario_id}", response_model=Scenario)
async def delete_scenario(scenario_id: str, user: AuthedUser, storage: StorageDependency):
    return await storage.delete_scenario(scenario_id=scenario_id)


@dataclass(frozen=True)
class CreateScenarioRunPayload:
    num_trials: int = 1

    def __post_init__(self) -> None:
        if self.num_trials < 1:
            raise ValueError("'num_trials' must be >= 1")

    @classmethod
    def to_scenario_run(
        cls, payload: Self, user_id: str, scenario_id: str, configuration: dict[str, Any]
    ) -> ScenarioRun:
        scenario_run_id = str(uuid4())
        trials = [
            Trial(
                trial_id=str(uuid4()),
                scenario_run_id=scenario_run_id,
                scenario_id=scenario_id,
                thread_id=None,
                index_in_run=index_in_run,
            )
            for index_in_run in range(payload.num_trials)
        ]
        return ScenarioRun(
            scenario_run_id=scenario_run_id,
            num_trials=payload.num_trials,
            scenario_id=scenario_id,
            trials=trials,
            user_id=user_id,
            configuration=configuration,
        )


@router.post("/scenarios/{scenario_id}/runs", response_model=ScenarioRun)
async def create_scenario_run(
    scenario_id: str,
    payload: CreateScenarioRunPayload,
    user: AuthedUser,
    storage: StorageDependency,
):
    scenario = await storage.get_scenario(scenario_id=scenario_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    agent = await storage.get_agent(user_id=user.user_id, agent_id=scenario.agent_id)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    configuration = {
        "models": agent.get_agent_models(),
        "architecture_version": agent.agent_architecture.version,
        "architecture_name": agent.agent_architecture.name,
        "runbook": agent.runbook_structured.raw_text,
        "agent_updated_at": agent.updated_at.isoformat(),
    }

    scenario_run = CreateScenarioRunPayload.to_scenario_run(
        payload, user.user_id, scenario.scenario_id, configuration
    )

    return await storage.create_scenario_run(scenario_run)


@router.get("/scenarios/{scenario_id}/runs/latest", response_model=ScenarioRun)
async def get_latest_scenario_run(scenario_id: str, user: AuthedUser, storage: StorageDependency):
    scenario = await storage.get_scenario(scenario_id=scenario_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    runs = await storage.list_scenario_runs(scenario_id=scenario_id, limit=1)

    if len(runs) == 0:
        raise HTTPException(status_code=404, detail="Latest run not found")

    run = runs[0]
    trials = await storage.list_scenario_run_trials(scenario_run_id=run.scenario_run_id)

    # TODO run.trials[i].messages could be removed to avoid too big payloads
    return run.with_trials(trials)


@router.get("/scenarios/{scenario_id}/runs/{scenario_run_id}", response_model=ScenarioRun)
async def get_scenario_run(
    scenario_id: str, scenario_run_id: str, user: AuthedUser, storage: StorageDependency
):
    scenario = await storage.get_scenario(scenario_id=scenario_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    run = await storage.get_scenario_run(scenario_run_id=scenario_run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")

    return run


@router.get("/scenarios/{scenario_id}/runs", response_model=list[ScenarioRun])
async def list_scenario_runs(
    scenario_id: str, user: AuthedUser, storage: StorageDependency, limit: int | None = None
):
    scenario = await storage.get_scenario(scenario_id=scenario_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return await storage.list_scenario_runs(scenario_id=scenario_id, limit=limit)


@router.delete("/scenarios/{scenario_id}/runs/{scenario_run_id}")
async def cancel_run(
    scenario_id: str,
    scenario_run_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    run = await storage.get_scenario_run(scenario_run_id)
    if not run:
        raise PlatformHTTPError(ErrorCode.NOT_FOUND, "Scenarion Run not found")

    system_user, _ = await storage.get_or_create_user(EVALS_SYSTEM_USER_SUB)
    for trial in run.trials:
        await storage.update_trial_status(
            trial.trial_id,
            system_user.user_id,
            TrialStatus.CANCELED,
        )
        logger.info(f"Run trial {trial.index_in_run} has been canceled.")

    return {"status": "ok"}
