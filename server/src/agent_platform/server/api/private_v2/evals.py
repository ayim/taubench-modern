import io
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Self
from uuid import uuid4

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from structlog import get_logger

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.evals.replay_executor import ReplayToolExecutor
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


def _safe_filename_fragment(value: str, default: str = "agent") -> str:
    """Return a filesystem-safe fragment derived from the provided value."""

    fragment = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return fragment or default


def _scenario_entry_filename(scenario: Scenario, index: int) -> str:
    name_fragment = _safe_filename_fragment(scenario.name, default="scenario")
    identifier = scenario.scenario_id[:8]
    return f"evals/{index + 1:03d}_{name_fragment}_{identifier}.yaml"


def _tools_entry_filename(scenario: Scenario, index: int) -> str:
    name_fragment = _safe_filename_fragment(scenario.name, default="scenario")
    identifier = scenario.scenario_id[:8]
    return f"used_tools/{index + 1:03d}_{name_fragment}_{identifier}.yaml"


def _extract_evaluations_from_metadata(metadata: Any) -> list[dict[str, Any]]:
    if not isinstance(metadata, dict):
        return []

    raw_evaluations = metadata.get("evaluations")
    if not isinstance(raw_evaluations, dict):
        return []

    evaluations: list[dict[str, Any]] = []

    for key, value in raw_evaluations.items():
        entry: dict[str, Any] = {"kind": key}

        if isinstance(value, dict):
            for prop, prop_value in value.items():
                entry[prop] = prop_value

        evaluations.append(entry)

    return evaluations


def _build_scenarios_archive(agent_id: str, scenarios: list[Scenario]) -> bytes:
    """Pack all scenarios into an in-memory zip archive ready for download."""

    buffer = io.BytesIO()
    metadata = {
        "agent_id": agent_id,
        "exported_at": datetime.now(UTC).isoformat(),
        "files": [],
    }

    def _remove_metadata(data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in {"complete", "content_id", "category"}}

    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, scenario in enumerate(scenarios):
            scenario_path = _scenario_entry_filename(scenario, index)
            tools_path = _tools_entry_filename(scenario, index)
            metadata_dict = scenario.metadata if isinstance(scenario.metadata, dict) else {}
            drift_policy = (
                metadata_dict.get("drift_policy", {}) if isinstance(metadata_dict, dict) else {}
            )
            tool_execution_mode = (
                drift_policy.get("tool_execution_mode") if isinstance(drift_policy, dict) else None
            )

            scenario_payload = {
                "name": scenario.name,
                "description": scenario.description,
                "tool_execution_mode": tool_execution_mode or "replay",
                "evaluations": _extract_evaluations_from_metadata(metadata_dict),
                "thread": {
                    "messages": [
                        {
                            "role": message.role,
                            "content": [
                                _remove_metadata(content.model_dump())
                                for content in message.content
                            ],
                        }
                        for message in scenario.messages
                    ],
                },
            }

            conversation_analysis = ReplayToolExecutor.from_conversation(scenario.messages)
            tool_defs = [
                _remove_metadata(tool.model_dump()) for tool in conversation_analysis.tools
            ]

            archive.writestr(tools_path, yaml.safe_dump(tool_defs, sort_keys=False))
            archive.writestr(scenario_path, yaml.safe_dump(scenario_payload, sort_keys=False))
            metadata["files"].append(
                {
                    "scenario_id": scenario.scenario_id,
                    "scenario_name": scenario.name,
                    "path": scenario_path,
                    "tools_path": tools_path,
                }
            )

        archive.writestr("metadata.yaml", yaml.dump(metadata))

    return buffer.getvalue()


def _scenarios_export_filename(agent_id: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"agent_{_safe_filename_fragment(agent_id)}_scenarios_{timestamp}.zip"


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
    def to_scenario(cls, payload: Self, user_id: str, thread: Thread) -> Scenario:  # noqa: C901
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
async def create_scenario(
    payload: CreateScenarioPayload, user: AuthedUser, storage: StorageDependency
):
    thread = await storage.get_thread(user.user_id, payload.thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    try:
        scenario = CreateScenarioPayload.to_scenario(payload, user.user_id, thread)
    except ValueError as exc:  # pragma: no cover - validated via unit tests
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@router.get("/scenarios/export", response_class=StreamingResponse)
async def export_agent_scenarios(
    agent_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> StreamingResponse:
    await storage.get_agent(user.user_id, agent_id)
    scenarios = await storage.list_scenarios(limit=None, agent_id=agent_id)
    archive_bytes = _build_scenarios_archive(agent_id, scenarios)
    headers = {
        "Content-Disposition": f'attachment; filename="{_scenarios_export_filename(agent_id)}"'
    }
    return StreamingResponse(iter([archive_bytes]), media_type="application/zip", headers=headers)


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
        "agent_updated_at": agent.updated_at.isoformat(),
        "runbook_updated_at": agent.runbook_structured.updated_at.isoformat(),
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
