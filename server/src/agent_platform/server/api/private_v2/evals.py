import zipfile
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal, Self
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from structlog import get_logger

from agent_platform.core.agent.agent import Agent
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.evals.types import (
    EvaluationAggregate,
    Scenario,
    ScenarioBatchRunStatistics,
    ScenarioBatchRunStatus,
    ScenarioBatchRunTrialStatus,
    ScenarioBatchRunTrialStatusEntry,
    ScenarioRun,
    Trial,
    TrialStatus,
)
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
from agent_platform.server.evals.archive import (
    ScenarioImportError,
    build_scenarios_archive,
    create_scenarios_from_bundles,
    load_scenarios_bundles,
)
from agent_platform.server.storage.base import ScenarioBatchRun

from .evals_files import copy_thread_files_to_scenario

router = APIRouter()
logger = get_logger(__name__)
PROGRESS_SLOW_THRESHOLD_SECONDS = 300
PROGRESS_STALLED_THRESHOLD_SECONDS = 900


def _build_run_configuration(agent: Agent) -> dict[str, Any]:
    """Collect agent metadata that describes how a run was executed."""
    platforms = sorted({cfg.kind for cfg in getattr(agent, "platform_configs", []) if getattr(cfg, "kind", None)})
    runbook_updated_at = agent.runbook_structured.updated_at
    run_metadata: dict[str, Any] = {
        "models": agent.get_agent_models(),
        "architecture_version": agent.agent_architecture.version,
        "architecture_name": agent.agent_architecture.name,
        "agent_updated_at": agent.updated_at.isoformat(),
        "agent_version": agent.version,
        "runbook_version": agent.version,
    }
    if runbook_updated_at is not None:
        run_metadata["runbook_updated_at"] = runbook_updated_at.isoformat()
    if platforms:
        run_metadata["platforms"] = platforms
    return run_metadata


@dataclass(frozen=True)
class ActionCalling:
    assert_all_consumed: bool | None = None
    allow_llm_arg_validation: bool | None = None
    allow_llm_interpolation: bool | None = None
    type: Literal["action_calling"] = "action_calling"


@dataclass(frozen=True)
class FlowAdherence:
    type: Literal["flow_adherence"] = "flow_adherence"


@dataclass(frozen=True)
class ResponseAccuracy:
    expectation: str
    type: Literal["response_accuracy"] = "response_accuracy"


EvaluationCriterion = ActionCalling | FlowAdherence | ResponseAccuracy


@dataclass(frozen=True)
class CreateScenarioPayload:
    name: str
    description: str
    thread_id: str
    tool_execution_mode: Literal["replay", "live"] | None = None
    evaluation_criteria: list[EvaluationCriterion] | None = None

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
        metadata: dict[str, Any] = {}
        drift_policy_overrides: dict[str, Any] = {}

        if payload.tool_execution_mode is not None:
            drift_policy_overrides["tool_execution_mode"] = payload.tool_execution_mode

        criteria = payload.evaluation_criteria or []

        if criteria:
            evaluations_config: dict[str, Any] = {}

            for criterion in criteria:
                if criterion.type == "action_calling":
                    action_config: dict[str, Any] = {"enabled": True}
                    for attr in (
                        "assert_all_consumed",
                        "allow_llm_arg_validation",
                        "allow_llm_interpolation",
                    ):
                        value = getattr(criterion, attr)
                        if value is not None:
                            action_config[attr] = value
                            drift_policy_overrides[attr] = value
                    evaluations_config["action_calling"] = action_config
                elif criterion.type == "flow_adherence":
                    evaluations_config["flow_adherence"] = {"enabled": True}
                elif criterion.type == "response_accuracy":
                    expectation = criterion.expectation.strip()
                    if not expectation:
                        raise ValueError("Response accuracy expectation cannot be empty")
                    evaluations_config["response_accuracy"] = {
                        "enabled": True,
                        "expectation": expectation,
                    }

            if evaluations_config:
                metadata["evaluations"] = evaluations_config

        if drift_policy_overrides:
            metadata["drift_policy"] = drift_policy_overrides

        return Scenario(
            scenario_id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            thread_id=thread.thread_id,
            user_id=user_id,
            agent_id=thread.agent_id,
            messages=messages,
            metadata=metadata,
        )


@router.post("/scenarios", response_model=Scenario)
async def create_scenario(payload: CreateScenarioPayload, user: AuthedUser, storage: StorageDependency):
    thread = await storage.get_thread(user.user_id, payload.thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    try:
        scenario = CreateScenarioPayload.to_scenario(payload, user.user_id, thread)
    except ValueError as exc:  # pragma: no cover - validated via unit tests
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    created_scenario = await storage.create_scenario(scenario)

    try:
        created_scenario = await copy_thread_files_to_scenario(
            storage=storage,
            thread=thread,
            scenario=created_scenario,
            user_id=user.user_id,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Failed to copy thread files during scenario creation",
            thread_id=thread.thread_id,
            scenario_id=created_scenario.scenario_id,
            error=str(exc),
        )

    return created_scenario


@dataclass(frozen=True)
class UpdateScenarioPayload:
    name: str
    description: str
    tool_execution_mode: Literal["replay", "live"] | None = None
    evaluation_criteria: list[EvaluationCriterion] | None = None

    def apply(self, scenario: Scenario) -> Scenario:
        metadata = deepcopy(scenario.metadata) if isinstance(scenario.metadata, dict) else {}
        drift_policy = metadata.get("drift_policy")
        if isinstance(drift_policy, dict):
            drift_policy = deepcopy(drift_policy)
        else:
            drift_policy = {}

        criteria = self.evaluation_criteria or []
        evaluations_config: dict[str, Any] = {}

        for criterion in criteria:
            if criterion.type == "action_calling":
                action_config: dict[str, Any] = {"enabled": True}
                for attr in (
                    "assert_all_consumed",
                    "allow_llm_arg_validation",
                    "allow_llm_interpolation",
                ):
                    value = getattr(criterion, attr)
                    if value is not None:
                        action_config[attr] = value
                        drift_policy[attr] = value
                evaluations_config["action_calling"] = action_config
            elif criterion.type == "flow_adherence":
                evaluations_config["flow_adherence"] = {"enabled": True}
            elif criterion.type == "response_accuracy":
                expectation = criterion.expectation.strip()
                if not expectation:
                    raise ValueError("Response accuracy expectation cannot be empty")
                evaluations_config["response_accuracy"] = {
                    "enabled": True,
                    "expectation": expectation,
                }

        if self.tool_execution_mode is not None:
            drift_policy["tool_execution_mode"] = self.tool_execution_mode
        else:
            drift_policy.pop("tool_execution_mode", None)

        if drift_policy:
            metadata["drift_policy"] = drift_policy
        else:
            metadata.pop("drift_policy", None)

        if evaluations_config:
            metadata["evaluations"] = evaluations_config
        else:
            metadata.pop("evaluations", None)

        return replace(
            scenario,
            name=self.name,
            description=self.description,
            metadata=metadata,
            updated_at=datetime.now(UTC),
        )


@dataclass(frozen=True)
class SuggestScenarioPayload:
    thread_id: str
    max_options: int = 1


@router.post("/scenarios/suggest", response_model=ScenarioSuggestion)
async def suggest_scenario_from_thread(payload: SuggestScenarioPayload, user: AuthedUser, storage: StorageDependency):
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


@router.get("/scenarios/export", response_class=StreamingResponse)
async def export_agent_scenarios(
    agent_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> StreamingResponse:
    await storage.get_agent(user.user_id, agent_id)
    # Export needs full message history
    scenarios = await storage.list_scenarios(limit=None, agent_id=agent_id, include_messages=True)
    archive_bytes, filename = await build_scenarios_archive(
        scenarios,
        storage,
        user.user_id,
        agent_id,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([archive_bytes]), media_type="application/zip", headers=headers)


@router.post("/scenarios/import", response_model=list[Scenario])
async def import_agent_scenarios(
    agent_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    file: UploadFile,
) -> list[Scenario]:
    agent = await storage.get_agent(user.user_id, agent_id)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    content = await file.read()
    await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded archive is empty")

    try:
        bundles = await load_scenarios_bundles(agent_id=agent.agent_id, user_id=user.user_id, content=content)
    except ScenarioImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive") from exc

    return await create_scenarios_from_bundles(user.user_id, bundles, storage)


@router.get("/scenarios/{scenario_id}", response_model=Scenario)
async def get_scenario(scenario_id: str, user: AuthedUser, storage: StorageDependency):
    return await storage.get_scenario(scenario_id=scenario_id)


@router.patch("/scenarios/{scenario_id}", response_model=Scenario)
async def update_scenario(
    scenario_id: str,
    payload: UpdateScenarioPayload,
    user: AuthedUser,
    storage: StorageDependency,
):
    scenario = await storage.get_scenario(scenario_id=scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    try:
        updated = payload.apply(scenario)
    except ValueError as exc:  # pragma: no cover - validated via unit tests
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await storage.update_scenario(updated)


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
        cls,
        payload: Self,
        user_id: str,
        scenario_id: str,
        configuration: dict[str, Any],
        batch_run_id: str | None = None,
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
            batch_run_id=batch_run_id,
        )


@dataclass(frozen=True)
class CreateScenarioBatchRunPayload:
    num_trials: int = 1

    def __post_init__(self) -> None:
        if self.num_trials < 1:
            raise ValueError("'num_trials' must be >= 1")


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

    configuration = _build_run_configuration(agent)
    scenario_run = CreateScenarioRunPayload.to_scenario_run(payload, user.user_id, scenario.scenario_id, configuration)

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
    trials = _annotate_trials_with_progress(list(trials))

    # TODO run.trials[i].messages could be removed to avoid too big payloads
    return run.with_trials(trials)


@router.get("/scenarios/{scenario_id}/runs/{scenario_run_id}", response_model=ScenarioRun)
async def get_scenario_run(scenario_id: str, scenario_run_id: str, user: AuthedUser, storage: StorageDependency):
    scenario = await storage.get_scenario(scenario_id=scenario_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    run = await storage.get_scenario_run(scenario_run_id=scenario_run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")

    trials = _annotate_trials_with_progress(list(run.trials))
    return run.with_trials(trials)


@router.get("/scenarios/{scenario_id}/runs", response_model=list[ScenarioRun])
async def list_scenario_runs(scenario_id: str, user: AuthedUser, storage: StorageDependency, limit: int | None = None):
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


@router.post("/agents/{agent_id}/batches", response_model=ScenarioBatchRun)
async def create_agent_batch_run(
    agent_id: str,
    payload: CreateScenarioBatchRunPayload,
    user: AuthedUser,
    storage: StorageDependency,
):
    agent = await storage.get_agent(user_id=user.user_id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    scenarios = await storage.list_scenarios(limit=None, agent_id=agent_id)
    if not scenarios:
        raise HTTPException(status_code=400, detail="Agent has no scenarios to run")

    existing_batch = await storage.get_active_scenario_batch_run(agent_id=agent_id)
    if existing_batch is not None:
        raise HTTPException(
            status_code=409,
            detail="Another batch run is already in progress for this agent",
        )

    scenario_ids = [scenario.scenario_id for scenario in scenarios]
    configuration = _build_run_configuration(agent)

    batch_run = ScenarioBatchRun(
        batch_run_id=str(uuid4()),
        agent_id=agent_id,
        user_id=user.user_id,
        metadata=deepcopy(configuration),
        scenario_ids=scenario_ids,
        status=ScenarioBatchRunStatus.RUNNING,
        statistics=ScenarioBatchRunStatistics(total_scenarios=len(scenario_ids)),
    )
    created_batch = await storage.create_scenario_batch_run(batch_run)

    scenario_run_payload = CreateScenarioRunPayload(num_trials=payload.num_trials)
    try:
        for scenario in scenarios:
            scenario_run = CreateScenarioRunPayload.to_scenario_run(
                scenario_run_payload,
                user.user_id,
                scenario.scenario_id,
                deepcopy(configuration),
                batch_run_id=created_batch.batch_run_id,
            )
            await storage.create_scenario_run(scenario_run)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception(
            "Failed to enqueue batch scenario runs",
            batch_run_id=created_batch.batch_run_id,
            agent_id=agent_id,
            error=str(exc),
        )
        await storage.update_scenario_batch_run(
            created_batch.batch_run_id,
            status=ScenarioBatchRunStatus.FAILED,
        )
        raise HTTPException(status_code=500, detail="Failed to schedule batch runs") from exc

    return await _refresh_batch_run_statistics(created_batch, storage)


@router.get("/agents/{agent_id}/batches/latest", response_model=ScenarioBatchRun)
async def get_latest_agent_batch_run(
    agent_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    agent = await storage.get_agent(user_id=user.user_id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    batches = await storage.list_scenario_batch_runs(agent_id=agent_id, limit=1)
    if not batches:
        raise HTTPException(status_code=404, detail="Batch run not found")

    return await _refresh_batch_run_statistics(batches[0], storage)


@router.get("/agents/{agent_id}/batches/{batch_run_id}", response_model=ScenarioBatchRun)
async def get_agent_batch_run(
    agent_id: str,
    batch_run_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    agent = await storage.get_agent(user_id=user.user_id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    batch_run = await storage.get_scenario_batch_run(batch_run_id=batch_run_id)
    if batch_run is None or batch_run.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Batch run not found")

    return await _refresh_batch_run_statistics(batch_run, storage)


@router.delete("/agents/{agent_id}/batches/{batch_run_id}", response_model=ScenarioBatchRun)
async def cancel_agent_batch_run(
    agent_id: str,
    batch_run_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    agent = await storage.get_agent(user_id=user.user_id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    batch_run = await storage.get_scenario_batch_run(batch_run_id=batch_run_id)
    if batch_run is None or batch_run.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Batch run not found")

    system_user, _ = await storage.get_or_create_user(EVALS_SYSTEM_USER_SUB)
    scenario_runs = await storage.list_scenario_runs_for_batch(batch_run.batch_run_id)

    for run in scenario_runs:
        trials = await storage.list_scenario_run_trials(run.scenario_run_id)
        for trial in trials:
            if trial.status in {
                TrialStatus.COMPLETED,
                TrialStatus.ERROR,
                TrialStatus.CANCELED,
            }:
                continue
            await storage.update_trial_status(
                trial.trial_id,
                system_user.user_id,
                TrialStatus.CANCELED,
            )
            logger.info(
                "Canceled trial in batch run",
                trial_id=trial.trial_id,
                scenario_run_id=run.scenario_run_id,
                batch_run_id=batch_run.batch_run_id,
            )

    canceled_at = datetime.now(UTC)
    updated_batch = await storage.update_scenario_batch_run(
        batch_run.batch_run_id,
        status=ScenarioBatchRunStatus.CANCELED,
        completed_at=canceled_at,
    )

    return await _refresh_batch_run_statistics(
        updated_batch
        if updated_batch is not None
        else replace(batch_run, status=ScenarioBatchRunStatus.CANCELED, completed_at=canceled_at),
        storage,
    )


TERMINAL_BATCH_STATUSES = {
    ScenarioBatchRunStatus.COMPLETED,
    ScenarioBatchRunStatus.CANCELED,
    ScenarioBatchRunStatus.FAILED,
}


async def _refresh_batch_run_statistics(batch_run: ScenarioBatchRun, storage: StorageDependency) -> ScenarioBatchRun:
    scenario_runs = await storage.list_scenario_runs_for_batch(batch_run.batch_run_id)
    if not scenario_runs:
        return replace(batch_run, trial_statuses=[])

    scenario_runs_by_id = {run.scenario_run_id: run for run in scenario_runs}
    trials_per_run: dict[str, list[Trial]] = {}
    for run in scenario_runs:
        trials = await storage.list_scenario_run_trials(scenario_run_id=run.scenario_run_id)
        trials_per_run[run.scenario_run_id] = trials

    statistics, derived_status = _calculate_batch_statistics(
        trials_per_run,
        expected_scenarios=len(batch_run.scenario_ids) or len(scenario_runs),
    )

    should_update_status = batch_run.status not in {
        derived_status,
        ScenarioBatchRunStatus.CANCELED,
    }
    should_update = (
        statistics != batch_run.statistics
        or should_update_status
        or (batch_run.completed_at is None and derived_status in TERMINAL_BATCH_STATUSES)
    )
    completed_at = (
        datetime.now(UTC) if batch_run.completed_at is None and derived_status in TERMINAL_BATCH_STATUSES else None
    )
    trial_statuses = _build_batch_trial_statuses(trials_per_run, scenario_runs_by_id)

    if not should_update:
        return replace(batch_run, trial_statuses=trial_statuses)

    updated = await storage.update_scenario_batch_run(
        batch_run.batch_run_id,
        status=derived_status if should_update_status else None,
        statistics=statistics if statistics != batch_run.statistics else None,
        completed_at=completed_at,
    )

    target = updated if updated is not None else batch_run
    return replace(target, trial_statuses=trial_statuses)


def _calculate_batch_statistics(
    trials_per_run: dict[str, list[Trial]],
    expected_scenarios: int,
) -> tuple[ScenarioBatchRunStatistics, ScenarioBatchRunStatus]:
    total_scenarios = expected_scenarios or len(trials_per_run)
    completed_scenarios = 0
    failed_scenarios = 0
    total_trials = 0
    completed_trials = 0
    failed_trials = 0
    canceled_trials = 0
    missing_runs = expected_scenarios > len(trials_per_run)
    has_pending_trials = False
    has_executing = False
    evaluation_totals: dict[str, EvaluationAggregate] = {}

    for trials in trials_per_run.values():
        if not trials:
            continue

        scenario_failed = False
        scenario_completed = True
        scenario_canceled = True

        for trial in trials:
            total_trials += 1

            if trial.status == TrialStatus.COMPLETED:
                completed_trials += 1
                scenario_canceled = False
            elif trial.status == TrialStatus.ERROR:
                failed_trials += 1
                scenario_failed = True
                scenario_completed = False
                scenario_canceled = False
            elif trial.status == TrialStatus.CANCELED:
                canceled_trials += 1
                scenario_completed = False
            elif trial.status == TrialStatus.EXECUTING:
                has_executing = True
                scenario_completed = False
                scenario_canceled = False
            elif trial.status == TrialStatus.PENDING:
                has_pending_trials = True
                scenario_completed = False
                scenario_canceled = False

            for result in trial.evaluation_results:
                current = evaluation_totals.get(result.kind)
                if current is None:
                    current = EvaluationAggregate()
                evaluation_totals[result.kind] = EvaluationAggregate(
                    total=current.total + 1,
                    passed=current.passed + (1 if getattr(result, "passed", False) else 0),
                )

        if scenario_failed or scenario_canceled:
            failed_scenarios += 1
        elif scenario_completed:
            completed_scenarios += 1

    if total_trials == 0:
        derived_status = ScenarioBatchRunStatus.PENDING
    elif completed_trials + failed_trials + canceled_trials == total_trials:
        derived_status = (
            ScenarioBatchRunStatus.CANCELED
            if canceled_trials == total_trials and completed_trials == 0
            else ScenarioBatchRunStatus.COMPLETED
        )
    elif has_executing or has_pending_trials:
        derived_status = ScenarioBatchRunStatus.RUNNING
    elif missing_runs:
        derived_status = ScenarioBatchRunStatus.PENDING
    else:
        derived_status = ScenarioBatchRunStatus.RUNNING

    statistics = ScenarioBatchRunStatistics(
        total_scenarios=total_scenarios,
        completed_scenarios=completed_scenarios,
        failed_scenarios=failed_scenarios,
        total_trials=total_trials,
        completed_trials=completed_trials,
        failed_trials=failed_trials,
        evaluation_totals=evaluation_totals,
    )

    return statistics, derived_status


def _ensure_datetime_has_tzinfo(reference: datetime | None) -> datetime | None:
    if reference is None:
        return None
    if reference.tzinfo is None:
        return reference.replace(tzinfo=UTC)
    return reference


def _classify_trial_progress(
    trial: Trial,
) -> tuple[Literal["running", "slow", "stalled"] | None, float | None]:
    if trial.status != TrialStatus.EXECUTING:
        return None, None

    state = trial.execution_state
    reference = _ensure_datetime_has_tzinfo(state.last_progress_at or state.finished_at or state.started_at)
    if reference is None:
        return None, None

    now = datetime.now(reference.tzinfo)
    seconds_since = max((now - reference).total_seconds(), 0.0)

    if seconds_since >= PROGRESS_STALLED_THRESHOLD_SECONDS:
        return "stalled", seconds_since
    if seconds_since >= PROGRESS_SLOW_THRESHOLD_SECONDS:
        return "slow", seconds_since
    return "running", seconds_since


def _annotate_trials_with_progress(trials: list[Trial]) -> list[Trial]:
    annotated: list[Trial] = []
    for trial in trials:
        classification, _ = _classify_trial_progress(trial)
        if classification is None or classification == trial.progress_classification:
            annotated.append(trial)
        else:
            annotated.append(replace(trial, progress_classification=classification))
    return annotated


def _build_batch_trial_statuses(
    trials_per_run: dict[str, list[Trial]],
    scenario_runs_by_id: dict[str, ScenarioRun],
) -> list[ScenarioBatchRunTrialStatus]:
    statuses: list[ScenarioBatchRunTrialStatus] = []
    for scenario_run_id, trials in trials_per_run.items():
        run = scenario_runs_by_id.get(scenario_run_id)
        scenario_id = run.scenario_id if run is not None else (trials[0].scenario_id if trials else "")
        entries: list[ScenarioBatchRunTrialStatusEntry] = []
        for trial in trials:
            classification, seconds_since = _classify_trial_progress(trial)
            execution_state = trial.execution_state
            entries.append(
                ScenarioBatchRunTrialStatusEntry(
                    trial_id=trial.trial_id,
                    index_in_run=trial.index_in_run,
                    status=trial.status,
                    status_updated_at=trial.status_updated_at,
                    execution_started_at=getattr(execution_state, "started_at", None),
                    execution_finished_at=getattr(execution_state, "finished_at", None),
                    last_progress_at=getattr(execution_state, "last_progress_at", None),
                    current_phase=getattr(execution_state, "current_phase", None),
                    worker_id=getattr(execution_state, "current_worker_id", None),
                    progress_classification=classification,
                    seconds_since_progress=seconds_since,
                )
            )
        statuses.append(
            ScenarioBatchRunTrialStatus(
                scenario_id=scenario_id,
                scenario_run_id=scenario_run_id,
                trials=entries,
            )
        )
    return statuses
