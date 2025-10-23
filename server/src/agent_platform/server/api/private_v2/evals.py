import io
import re
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self
from uuid import uuid4

import yaml
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from structlog import get_logger

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.evals.replay_executor import ReplayToolExecutor
from agent_platform.core.evals.types import Scenario, ScenarioRun, Trial, TrialStatus
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
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
from agent_platform.server.file_manager import FileManagerService
from agent_platform.server.file_manager.base import BaseFileManager

router = APIRouter()
logger = get_logger(__name__)


@dataclass(frozen=True)
class ScenarioArchiveEntry:
    path: str
    tools_path: str | None = None


@dataclass(frozen=True)
class ScenarioFileExport:
    file_id: str
    file_ref: str
    archive_path: str
    mime_type: str | None
    size: int
    content: bytes


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


def _scenario_files_dirname(scenario: Scenario, index: int) -> str:
    name_fragment = _safe_filename_fragment(scenario.name, default="scenario")
    identifier = scenario.scenario_id[:8]
    return f"thread_files/{index + 1:03d}_{name_fragment}_{identifier}"


def _sanitize_export_file_name(file_ref: str, used_names: set[str]) -> str:
    original_name = Path(file_ref).name or "file"
    sanitized = _safe_filename_fragment(original_name, default="file")

    base = Path(sanitized).stem or "file"
    suffix = Path(sanitized).suffix

    candidate = sanitized if sanitized not in {"", "."} else "file"
    counter = 1
    while candidate in used_names:
        candidate = f"{base}_{counter}{suffix}"
        counter += 1

    used_names.add(candidate)
    return candidate


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


async def _collect_scenario_files(
    *,
    scenario: Scenario,
    storage: StorageDependency,
    file_manager: BaseFileManager,
    requester_user_id: str,
    index: int,
) -> list[ScenarioFileExport]:
    if not scenario.thread_id:
        return []

    try:
        uploaded_files = await storage.get_thread_files(scenario.thread_id, requester_user_id)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Skipping file export for scenario due to thread files lookup failure",
            scenario_id=scenario.scenario_id,
            thread_id=scenario.thread_id,
            error=str(exc),
        )
        return []

    if not uploaded_files:
        return []

    used_names: set[str] = set()
    directory = _scenario_files_dirname(scenario, index)
    exports: list[ScenarioFileExport] = []

    for uploaded in uploaded_files:
        try:
            file_bytes = await file_manager.read_file_contents(uploaded.file_id, requester_user_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Unable to read thread file for scenario export",
                scenario_id=scenario.scenario_id,
                thread_id=scenario.thread_id,
                file_id=uploaded.file_id,
                error=str(exc),
            )
            continue

        archive_name = _sanitize_export_file_name(uploaded.file_ref, used_names)
        archive_path = f"{directory}/{archive_name}"
        exports.append(
            ScenarioFileExport(
                file_id=uploaded.file_id,
                file_ref=uploaded.file_ref,
                archive_path=archive_path,
                mime_type=uploaded.mime_type,
                size=len(file_bytes),
                content=file_bytes,
            )
        )

    return exports


async def _build_scenarios_archive(
    agent_id: str,
    scenarios: list[Scenario],
    storage: StorageDependency,
    requester_user_id: str,
) -> bytes:
    """Pack all scenarios into an in-memory zip archive ready for download."""

    buffer = io.BytesIO()
    metadata = {
        "exported_at": datetime.now(UTC).isoformat(),
        "files": [],
    }

    def _remove_metadata(data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in {"complete", "content_id", "category"}}

    file_manager = FileManagerService.get_instance(storage)

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

            scenario_files = await _collect_scenario_files(
                scenario=scenario,
                storage=storage,
                file_manager=file_manager,
                requester_user_id=requester_user_id,
                index=index,
            )

            attachments_metadata: list[dict[str, Any]] = []
            for export in scenario_files:
                archive.writestr(export.archive_path, export.content)
                attachments_metadata.append(
                    {
                        "file_ref": export.file_ref,
                        "path": export.archive_path,
                        "mime_type": export.mime_type,
                        "size": export.size,
                    }
                )

            metadata["files"].append(
                {
                    "scenario_name": scenario.name,
                    "path": scenario_path,
                    "tools_path": tools_path,
                    "attachments": attachments_metadata,
                }
            )

        archive.writestr("metadata.yaml", yaml.dump(metadata))

    return buffer.getvalue()


def _scenarios_export_filename(agent_id: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"agent_{_safe_filename_fragment(agent_id)}_scenarios_{timestamp}.zip"


class ScenarioImportError(Exception):
    """Raised when a scenario archive cannot be imported."""


def _load_archive_metadata(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        metadata_bytes = archive.read("metadata.yaml")
    except KeyError as exc:
        raise ScenarioImportError("Missing metadata.yaml in archive") from exc

    try:
        metadata = yaml.safe_load(metadata_bytes) or {}
    except yaml.YAMLError as exc:
        raise ScenarioImportError("Unable to parse metadata.yaml") from exc

    if not isinstance(metadata, dict):
        raise ScenarioImportError("metadata.yaml must define a mapping")

    return metadata


def _list_scenario_entries(metadata: dict[str, Any]) -> list[ScenarioArchiveEntry]:
    entries: list[ScenarioArchiveEntry] = []
    files_entry = metadata.get("files")

    if isinstance(files_entry, list):
        seen_paths: set[str] = set()
        for entry in files_entry:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if not isinstance(path, str) or path in seen_paths:
                continue
            tools_path = entry.get("tools_path")
            if not isinstance(tools_path, str):
                tools_path = None
            entries.append(ScenarioArchiveEntry(path=path, tools_path=tools_path))
            seen_paths.add(path)

    if not entries:
        raise ScenarioImportError("No scenario definitions found in archive")

    return entries


def _load_scenario_payload(archive: zipfile.ZipFile, path: str) -> dict[str, Any]:
    try:
        payload_bytes = archive.read(path)
    except KeyError as exc:
        raise ScenarioImportError(f"Scenario file '{path}' is missing from archive") from exc

    try:
        payload = yaml.safe_load(payload_bytes) or {}
    except yaml.YAMLError as exc:
        raise ScenarioImportError(f"Unable to parse scenario file '{path}'") from exc

    if not isinstance(payload, dict):
        raise ScenarioImportError(f"Scenario file '{path}' must define a mapping")

    return payload


def _load_used_tools(
    archive: zipfile.ZipFile, tools_path: str, scenario_path: str
) -> list[dict[str, Any]]:
    try:
        payload_bytes = archive.read(tools_path)
    except KeyError as exc:
        error_message = (
            f"Used tools file '{tools_path}' referenced by {scenario_path}' is missing from archive"
        )
        raise ScenarioImportError(error_message) from exc

    try:
        payload = yaml.safe_load(payload_bytes) or []
    except yaml.YAMLError as exc:
        raise ScenarioImportError(
            f"Unable to parse used tools file '{tools_path}' referenced by '{scenario_path}'"
        ) from exc

    if not isinstance(payload, list):
        raise ScenarioImportError(f"Used tools file '{tools_path}' must define a list of tools")

    tools: list[dict[str, Any]] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ScenarioImportError(
                f"Used tools file '{tools_path}' entry at index {index} must be a mapping"
            )
        tool_name = entry.get("name")
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ScenarioImportError(
                f"Used tools file '{tools_path}' entry at index {index} is missing a valid name"
            )
        tools.append(entry)

    return tools


def _extract_tool_categories(messages: list[ThreadMessage]) -> dict[str, str]:
    categories: dict[str, str] = {}

    for message in messages:
        for content in message.content:
            if isinstance(content, ThreadToolUsageContent):
                if content.sub_type == "mcp-external":
                    categories.setdefault(content.name, "mcp-tool")
                elif content.sub_type == "action-external":
                    categories.setdefault(content.name, "action-tool")

    return categories


def _apply_used_tools_to_messages(
    messages: list[ThreadMessage], used_tools: list[dict[str, Any]] | None
) -> None:
    if not used_tools:
        return

    categories = _extract_tool_categories(messages)
    normalized_tools: list[dict[str, Any]] = []

    for entry in used_tools:
        tool_copy = deepcopy(entry)
        tool_name = tool_copy.get("name")
        if isinstance(tool_name, str):
            category = tool_copy.get("category")
            if not isinstance(category, str) or not category:
                inferred_category = categories.get(tool_name)
                tool_copy["category"] = inferred_category or "action-tool"
        normalized_tools.append(tool_copy)

    for message in messages:
        if message.role != "agent":
            continue
        message.agent_metadata["tools"] = [deepcopy(tool) for tool in normalized_tools]


def _build_metadata_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    evaluations = payload.get("evaluations")
    if isinstance(evaluations, list):
        evaluations_config: dict[str, Any] = {}
        for entry in evaluations:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("kind")
            if not isinstance(kind, str):
                continue
            config = {k: v for k, v in entry.items() if k != "kind"}
            if not config:
                config = {"enabled": True}
            evaluations_config[kind] = config

        if evaluations_config:
            metadata["evaluations"] = evaluations_config

    tool_execution_mode = payload.get("tool_execution_mode")
    if isinstance(tool_execution_mode, str) and tool_execution_mode:
        metadata.setdefault("drift_policy", {})["tool_execution_mode"] = tool_execution_mode

    return metadata


def _scenario_from_payload(
    *,
    payload: dict[str, Any],
    path: str,
    user_id: str,
    agent_id: str,
    used_tools: list[dict[str, Any]] | None = None,
) -> Scenario:
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ScenarioImportError(f"Scenario '{path}' is missing a valid name")

    description = payload.get("description", "")
    if not isinstance(description, str):
        raise ScenarioImportError(f"Scenario '{path}' has an invalid description")

    thread_payload = payload.get("thread")
    if not isinstance(thread_payload, dict):
        raise ScenarioImportError(f"Scenario '{path}' is missing thread data")

    raw_messages = thread_payload.get("messages")
    if not isinstance(raw_messages, list):
        raise ScenarioImportError(f"Scenario '{path}' thread messages must be a list")

    messages: list[ThreadMessage] = []
    for index, raw_message in enumerate(raw_messages):
        if not isinstance(raw_message, dict):
            raise ScenarioImportError(
                f"Scenario '{path}' message at index {index} must be a mapping"
            )
        try:
            message = ThreadMessage.model_validate(raw_message)
        except Exception as exc:
            raise ScenarioImportError(
                f"Scenario '{path}' message at index {index} is invalid: {exc}"
            ) from exc
        message.mark_complete()
        messages.append(message)

    _apply_used_tools_to_messages(messages, used_tools)

    metadata = _build_metadata_from_payload(payload)

    return Scenario(
        scenario_id=str(uuid4()),
        name=name,
        description=description,
        thread_id=None,
        agent_id=agent_id,
        user_id=user_id,
        messages=messages,
        metadata=metadata,
    )


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
    archive_bytes = await _build_scenarios_archive(
        agent_id,
        scenarios,
        storage,
        user.user_id,
    )
    headers = {
        "Content-Disposition": f'attachment; filename="{_scenarios_export_filename(agent_id)}"'
    }
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
        scenarios_to_create: list[Scenario] = []

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            metadata = _load_archive_metadata(archive)

            for entry in _list_scenario_entries(metadata):
                payload = _load_scenario_payload(archive, entry.path)
                used_tools = (
                    _load_used_tools(archive, entry.tools_path, entry.path)
                    if entry.tools_path is not None
                    else None
                )
                scenarios_to_create.append(
                    _scenario_from_payload(
                        payload=payload,
                        path=entry.path,
                        user_id=user.user_id,
                        agent_id=agent_id,
                        used_tools=used_tools,
                    )
                )
    except ScenarioImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=400, detail="Uploaded file is not a valid ZIP archive"
        ) from exc

    created: list[Scenario] = []
    for scenario in scenarios_to_create:
        created.append(await storage.create_scenario(scenario))

    return created


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
