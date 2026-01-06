import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from agent_platform.core.thread.base import ThreadMessage


class DriftType(str, Enum):
    ORDER_MISMATCH = "ORDER_MISMATCH"
    NAME_MISMATCH = "NAME_MISMATCH"
    ARG_MISMATCH = "ARG_MISMATCH"
    EXTRA_ACTUAL_CALL = "EXTRA_ACTUAL_CALL"
    MISSING_ACTUAL_CALL = "MISSING_ACTUAL_CALL"
    LEFTOVER_RECORDED_CALLS = "LEFTOVER_RECORDED_CALLS"


@dataclass
class DriftEvent:
    index_before: int
    drift_type: DriftType
    message: str
    expected_tool: str | None = None
    actual_tool: str | None = None
    expected_args: dict[str, Any] | None = None
    actual_args: dict[str, Any] | None = None
    repair_action: str | None = None
    llm_reason: str | None = None
    llm_raw_response: str | None = None
    llm_proposed_output: Any | None = None
    llm_proposed_error: str | None = None

    @classmethod
    def model_validate(cls, data: dict) -> "DriftEvent":
        if data.get("drift_type"):
            data["drift_type"] = DriftType(data["drift_type"])
        return cls(**data)

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Scenario:
    """
    Replayable conversation blueprint.
    Store everything needed to re-execute.
    """

    scenario_id: str
    name: str
    description: str
    # it is None when thread is deleted
    thread_id: str | None
    agent_id: str
    user_id: str

    # store a copy of thread messages
    # because the original thread can be updated or deleted
    messages: list[ThreadMessage] = field(
        metadata={"description": "All messages in the original thread."},
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def model_validate(cls, data: dict) -> "Scenario":
        """Create a scenario from a dictionary."""
        data = data.copy()

        if "thread_id" in data and isinstance(data["thread_id"], UUID):
            data["thread_id"] = str(data["thread_id"])
        if "scenario_id" in data and isinstance(data["scenario_id"], UUID):
            data["scenario_id"] = str(data["scenario_id"])
        if "user_id" in data and isinstance(data["user_id"], UUID):
            data["user_id"] = str(data["user_id"])
        if "agent_id" in data and isinstance(data["agent_id"], UUID):
            data["agent_id"] = str(data["agent_id"])

        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "messages" in data and isinstance(data["messages"], list):
            data["messages"] = [ThreadMessage.model_validate(message) for message in data["messages"]]

        metadata = data.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        elif metadata is None:
            metadata = {}
        data["metadata"] = metadata

        return cls(
            **data,
        )

    def model_dump(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "messages": [message.model_dump() for message in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class TrialStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELED = "CANCELED"


class ScenarioBatchRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


@dataclass(frozen=True)
class EvaluationAggregate:
    total: int = 0
    passed: int = 0

    def model_dump(self) -> dict[str, int]:
        return {"total": self.total, "passed": self.passed}

    @classmethod
    def model_validate(cls, data: dict | None) -> "EvaluationAggregate":
        if not data:
            return cls()
        return cls(total=int(data.get("total", 0)), passed=int(data.get("passed", 0)))


def parse_evaluation_result(data: dict) -> "EvaluationResult":
    kind = data.get("kind")
    if kind == "flow_adherence":
        return FlowAdherenceResult(**data)
    elif kind == "response_accuracy":
        return ResponseAccuracyResult(**data)
    elif kind == "action_calling":
        return ActionCallingResult(**data)
    else:
        raise ValueError(f"Unknown evaluation kind: {kind!r}")


def parse_execution_state(data: dict) -> "ExecutionState":
    if "drift_events" in data and isinstance(data["drift_events"], list):
        data["drift_events"] = [DriftEvent.model_validate(event) for event in data["drift_events"]]
    else:
        data["drift_events"] = []

    if "started_at" in data and isinstance(data["started_at"], str):
        data["started_at"] = datetime.fromisoformat(data["started_at"])

    if "finished_at" in data and isinstance(data["finished_at"], str):
        data["finished_at"] = datetime.fromisoformat(data["finished_at"])

    if "last_progress_at" in data and isinstance(data["last_progress_at"], str):
        data["last_progress_at"] = datetime.fromisoformat(data["last_progress_at"])

    return ExecutionState(**data)


@dataclass(frozen=True)
class FlowAdherenceResult:
    """
    tells if the conversation is consistent with the golden run
    """

    explanation: str
    score: int
    passed: bool
    kind: Literal["flow_adherence"] = "flow_adherence"

    def model_dump(self) -> dict:
        return asdict(self)

    @classmethod
    def model_validate(cls, data: dict) -> "FlowAdherenceResult":
        return cls(**data)


@dataclass(frozen=True)
class ResponseAccuracyResult:
    """
    tells if the conversation is accurate wrt the scenario description
    """

    explanation: str
    score: int
    passed: bool
    kind: Literal["response_accuracy"] = "response_accuracy"

    def model_dump(self) -> dict:
        return asdict(self)

    @classmethod
    def model_validate(cls, data: dict) -> "ResponseAccuracyResult":
        return cls(**data)


@dataclass(frozen=True)
class ActionCallingResult:
    """
    tells if the conversation tool calls match the golden run
    """

    issues: list[str]
    passed: bool
    kind: Literal["action_calling"] = "action_calling"

    def model_dump(self) -> dict:
        return asdict(self)

    @classmethod
    def model_validate(cls, data: dict) -> "ActionCallingResult":
        return cls(**data)


EvaluationResult = ResponseAccuracyResult | FlowAdherenceResult | ActionCallingResult


@dataclass
class ExecutionState:
    execution_mode: str = "replay"
    status: str = "STARTED"
    termination: str | None = None
    drift_events: list[DriftEvent] = field(default_factory=list)
    error_message: str | None = None

    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None
    last_progress_at: datetime | None = None
    current_phase: str | None = None
    current_worker_id: str | None = None

    def model_dump(self) -> dict:
        return {
            "execution_mode": self.execution_mode,
            "status": self.status,
            "termination": self.termination,
            "drift_events": [event.model_dump() for event in self.drift_events],
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "last_progress_at": self.last_progress_at.isoformat() if self.last_progress_at else None,
            "current_phase": self.current_phase,
            "current_worker_id": self.current_worker_id,
        }


@dataclass(frozen=True)
class Trial:
    trial_id: str
    scenario_run_id: str
    scenario_id: str
    # 0..num_trials-1 within the run
    index_in_run: int

    evaluation_results: list[EvaluationResult] = field(default_factory=list)
    execution_state: ExecutionState = field(default_factory=ExecutionState)

    thread_id: str | None = None
    status: TrialStatus = TrialStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status_updated_at: datetime = field(default_factory=datetime.now)
    status_updated_by: str = "SYSTEM"

    # error if status is failed
    error_message: str | None = None

    metadata: dict = field(
        default_factory=dict,
        metadata={"description": "Arbitrary trial metadata."},
    )
    retry_after_at: datetime | None = None
    reschedule_attempts: int = 0
    progress_classification: Literal["running", "slow", "stalled"] | None = None

    def __repr__(self) -> str:
        base = (
            f"<Trial id={self.trial_id[:8]}, "
            f"status={self.status}, "
            f"index_in_run={self.index_in_run}, "
            f"scenario_id={self.scenario_id[:8]}, "
            f"scenario_run_id={self.scenario_run_id[:8]}, "
            f"thread_id={self.thread_id[:8] if self.thread_id else None}"
            f"scenario_run_id={self.scenario_run_id[:8]}"
        )
        if self.status == TrialStatus.ERROR and self.error_message:
            base += f", error={self.error_message!r}"
        base += ">"
        return base

    def get_unique_identifier(self):
        return str(self.trial_id)

    def get_status(self):
        return str(self.status.value)

    def get_reschedule_attempts(self):
        return self.reschedule_attempts

    @classmethod
    def model_validate(cls, data: dict) -> "Trial":
        """Create a trial from a dictionary."""
        data = data.copy()

        if "trial_id" in data and isinstance(data["trial_id"], UUID):
            data["trial_id"] = str(data["trial_id"])
        if "scenario_run_id" in data and isinstance(data["scenario_run_id"], UUID):
            data["scenario_run_id"] = str(data["scenario_run_id"])
        if "scenario_id" in data and isinstance(data["scenario_id"], UUID):
            data["scenario_id"] = str(data["scenario_id"])
        if "thread_id" in data and isinstance(data["thread_id"], UUID):
            data["thread_id"] = str(data["thread_id"])

        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "status_updated_at" in data and isinstance(data["status_updated_at"], str):
            data["status_updated_at"] = datetime.fromisoformat(data["status_updated_at"])
        if "retry_after_at" in data and isinstance(data["retry_after_at"], str):
            data["retry_after_at"] = datetime.fromisoformat(data["retry_after_at"])

        if "messages" in data and isinstance(data["messages"], list):
            data["messages"] = [ThreadMessage.model_validate(message) for message in data["messages"]]
        if "evaluation_results" in data and isinstance(data["evaluation_results"], list):
            data["evaluation_results"] = [parse_evaluation_result(result) for result in data["evaluation_results"]]
        if "execution_state" in data and isinstance(data["execution_state"], dict):
            data["execution_state"] = parse_execution_state(data["execution_state"])
        metadata = data.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        elif metadata is None:
            metadata = {}
        data["metadata"] = metadata

        reschedule_attempts = data.get("reschedule_attempts", 0)
        try:
            data["reschedule_attempts"] = int(reschedule_attempts)
        except (TypeError, ValueError):
            data["reschedule_attempts"] = 0

        if "status" in data and isinstance(data["status"], str):
            data["status"] = TrialStatus(data["status"])

        progress_classification = data.get("progress_classification")
        if progress_classification is not None and not isinstance(progress_classification, str):
            progress_classification = str(progress_classification)
        data["progress_classification"] = progress_classification

        return cls(
            **data,
        )

    def model_dump(self) -> dict:
        return {
            "trial_id": self.trial_id,
            "scenario_run_id": self.scenario_run_id,
            "scenario_id": self.scenario_id,
            "index_in_run": self.index_in_run,
            "thread_id": self.thread_id,
            "evaluation_results": [result.model_dump() for result in self.evaluation_results],
            "execution_state": {
                "drift_events": [event.model_dump() for event in self.execution_state.drift_events],
            },
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status_updated_at": self.status_updated_at,
            "status_updated_by": self.status_updated_by,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "retry_after_at": self.retry_after_at.isoformat() if self.retry_after_at else None,
            "reschedule_attempts": self.reschedule_attempts,
        }


@dataclass(frozen=True)
class ScenarioRun:
    scenario_run_id: str
    scenario_id: str
    user_id: str
    batch_run_id: str | None = None
    num_trials: int = 1
    configuration: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    trials: list[Trial] = field(
        default_factory=list,
        metadata={"description": "All trials in this run."},
    )

    @classmethod
    def model_validate(cls, data: dict) -> "ScenarioRun":
        """Create a scenario run from a dictionary."""
        data = data.copy()

        if "scenario_run_id" in data and isinstance(data["scenario_run_id"], UUID):
            data["scenario_run_id"] = str(data["scenario_run_id"])
        if "scenario_id" in data and isinstance(data["scenario_id"], UUID):
            data["scenario_id"] = str(data["scenario_id"])
        if "user_id" in data and isinstance(data["user_id"], UUID):
            data["user_id"] = str(data["user_id"])
        if "batch_run_id" in data and isinstance(data["batch_run_id"], UUID):
            data["batch_run_id"] = str(data["batch_run_id"])

        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])

        if "trials" in data and isinstance(data["trials"], list):
            data["trials"] = [Trial.model_validate(trial) for trial in data["trials"]]

        return cls(
            **data,
        )

    def model_dump(self) -> dict:
        return {
            "scenario_run_id": self.scenario_run_id,
            "scenario_id": self.scenario_id,
            "user_id": self.user_id,
            "batch_run_id": self.batch_run_id,
            "num_trials": self.num_trials,
            "configuration": self.configuration,
            "created_at": self.created_at,
        }

    def with_trials(self, trials: list[Trial]) -> "ScenarioRun":
        return replace(self, trials=trials)


@dataclass(frozen=True)
class ScenarioBatchRunStatistics:
    total_scenarios: int = 0
    completed_scenarios: int = 0
    failed_scenarios: int = 0
    total_trials: int = 0
    completed_trials: int = 0
    failed_trials: int = 0
    evaluation_totals: dict[str, EvaluationAggregate] = field(default_factory=dict)

    def model_dump(self) -> dict:
        return {
            "total_scenarios": self.total_scenarios,
            "completed_scenarios": self.completed_scenarios,
            "failed_scenarios": self.failed_scenarios,
            "total_trials": self.total_trials,
            "completed_trials": self.completed_trials,
            "failed_trials": self.failed_trials,
            "evaluation_totals": {key: value.model_dump() for key, value in self.evaluation_totals.items()},
        }

    @classmethod
    def model_validate(cls, data: dict | None) -> "ScenarioBatchRunStatistics":
        if not data:
            return cls()
        evaluation_totals = data.get("evaluation_totals") or {}
        parsed_totals = {key: EvaluationAggregate.model_validate(value) for key, value in evaluation_totals.items()}
        return cls(
            total_scenarios=int(data.get("total_scenarios", 0)),
            completed_scenarios=int(data.get("completed_scenarios", 0)),
            failed_scenarios=int(data.get("failed_scenarios", 0)),
            total_trials=int(data.get("total_trials", 0)),
            completed_trials=int(data.get("completed_trials", 0)),
            failed_trials=int(data.get("failed_trials", 0)),
            evaluation_totals=parsed_totals,
        )

    @classmethod
    def from_trials(
        cls,
        trials_per_run: dict[str, list[Trial]],
        *,
        expected_scenarios: int,
    ) -> tuple["ScenarioBatchRunStatistics", "ScenarioBatchRunStatus"]:
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

        statistics = cls(
            total_scenarios=total_scenarios,
            completed_scenarios=completed_scenarios,
            failed_scenarios=failed_scenarios,
            total_trials=total_trials,
            completed_trials=completed_trials,
            failed_trials=failed_trials,
            evaluation_totals=evaluation_totals,
        )

        return statistics, derived_status


@dataclass(frozen=True)
class ScenarioBatchRunTrialStatusEntry:
    trial_id: str
    index_in_run: int
    status: TrialStatus
    status_updated_at: datetime | None = None
    execution_started_at: datetime | None = None
    execution_finished_at: datetime | None = None
    last_progress_at: datetime | None = None
    current_phase: str | None = None
    worker_id: str | None = None
    progress_classification: Literal["running", "slow", "stalled"] | None = None
    seconds_since_progress: float | None = None

    def model_dump(self) -> dict:
        return {
            "trial_id": self.trial_id,
            "index_in_run": self.index_in_run,
            "status": self.status.value,
            "status_updated_at": self.status_updated_at,
            "execution_started_at": self.execution_started_at,
            "execution_finished_at": self.execution_finished_at,
            "last_progress_at": self.last_progress_at,
            "current_phase": self.current_phase,
            "worker_id": self.worker_id,
            "progress_classification": self.progress_classification,
            "seconds_since_progress": self.seconds_since_progress,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ScenarioBatchRunTrialStatusEntry":
        parsed = data.copy()
        if "status_updated_at" in parsed and isinstance(parsed["status_updated_at"], str):
            parsed["status_updated_at"] = datetime.fromisoformat(parsed["status_updated_at"])
        if "execution_started_at" in parsed and isinstance(parsed["execution_started_at"], str):
            parsed["execution_started_at"] = datetime.fromisoformat(parsed["execution_started_at"])
        if "execution_finished_at" in parsed and isinstance(parsed["execution_finished_at"], str):
            parsed["execution_finished_at"] = datetime.fromisoformat(parsed["execution_finished_at"])
        if "last_progress_at" in parsed and isinstance(parsed["last_progress_at"], str):
            parsed["last_progress_at"] = datetime.fromisoformat(parsed["last_progress_at"])
        status = parsed.get("status")
        if isinstance(status, str):
            parsed["status"] = TrialStatus(status)
        return cls(
            trial_id=str(parsed.get("trial_id", "")),
            index_in_run=int(parsed.get("index_in_run", 0)),
            status=parsed.get("status", TrialStatus.PENDING),
            status_updated_at=parsed.get("status_updated_at"),
            execution_started_at=parsed.get("execution_started_at"),
            execution_finished_at=parsed.get("execution_finished_at"),
            last_progress_at=parsed.get("last_progress_at"),
            current_phase=parsed.get("current_phase"),
            worker_id=parsed.get("worker_id"),
            progress_classification=parsed.get("progress_classification"),
            seconds_since_progress=parsed.get("seconds_since_progress"),
        )


@dataclass(frozen=True)
class ScenarioBatchRunTrialStatus:
    scenario_id: str
    scenario_run_id: str
    trials: list[ScenarioBatchRunTrialStatusEntry] = field(default_factory=list)

    def model_dump(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "scenario_run_id": self.scenario_run_id,
            "trials": [trial.model_dump() for trial in self.trials],
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ScenarioBatchRunTrialStatus":
        parsed = data.copy()
        parsed["scenario_id"] = str(parsed.get("scenario_id", ""))
        parsed["scenario_run_id"] = str(parsed.get("scenario_run_id", ""))
        trials = parsed.get("trials") or []
        parsed["trials"] = [ScenarioBatchRunTrialStatusEntry.model_validate(trial) for trial in trials]
        return cls(**parsed)


@dataclass(frozen=True)
class ScenarioBatchRun:
    batch_run_id: str
    agent_id: str
    user_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    scenario_ids: list[str] = field(default_factory=list)
    status: ScenarioBatchRunStatus = ScenarioBatchRunStatus.PENDING
    statistics: ScenarioBatchRunStatistics = field(default_factory=ScenarioBatchRunStatistics)
    trial_statuses: list[ScenarioBatchRunTrialStatus] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @classmethod
    def model_validate(cls, data: dict) -> "ScenarioBatchRun":
        data = data.copy()

        if "batch_run_id" in data and isinstance(data["batch_run_id"], UUID):
            data["batch_run_id"] = str(data["batch_run_id"])
        if "agent_id" in data and isinstance(data["agent_id"], UUID):
            data["agent_id"] = str(data["agent_id"])
        if "user_id" in data and isinstance(data["user_id"], UUID):
            data["user_id"] = str(data["user_id"])

        for key in ("created_at", "updated_at", "completed_at"):
            value = data.get(key)
            if isinstance(value, str):
                data[key] = datetime.fromisoformat(value)

        scenario_ids = data.get("scenario_ids")
        if isinstance(scenario_ids, str):
            try:
                scenario_ids = json.loads(scenario_ids)
            except json.JSONDecodeError:
                scenario_ids = []
        if scenario_ids is None:
            scenario_ids = []
        data["scenario_ids"] = [str(sid) for sid in scenario_ids]

        statistics = data.get("statistics")
        if isinstance(statistics, str):
            try:
                statistics = json.loads(statistics)
            except json.JSONDecodeError:
                statistics = {}
        data["statistics"] = ScenarioBatchRunStatistics.model_validate(statistics)

        trial_statuses = data.get("trial_statuses")
        if isinstance(trial_statuses, str):
            try:
                trial_statuses = json.loads(trial_statuses)
            except json.JSONDecodeError:
                trial_statuses = []
        if trial_statuses is None:
            trial_statuses = []
        data["trial_statuses"] = [ScenarioBatchRunTrialStatus.model_validate(status) for status in trial_statuses]
        metadata = data.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        if metadata is None:
            metadata = {}
        data["metadata"] = metadata

        status = data.get("status")
        if isinstance(status, str):
            data["status"] = ScenarioBatchRunStatus(status)

        return cls(**data)

    def model_dump(self) -> dict:
        return {
            "batch_run_id": self.batch_run_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "scenario_ids": self.scenario_ids,
            "status": self.status.value,
            "statistics": self.statistics.model_dump(),
            "trial_statuses": [status.model_dump() for status in self.trial_statuses],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }
