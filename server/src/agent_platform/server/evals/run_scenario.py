import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, cast
from uuid import uuid4

from fastapi import Request, UploadFile
from starlette.datastructures import Headers

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.observability_config import ObservabilityConfig
from agent_platform.core.context import AgentServerContext
from agent_platform.core.evals.agent_client import (
    AgentClient,
    ToolExecutionError,
    UnexpectedToolError,
)
from agent_platform.core.evals.live_executor import LiveToolExecutor
from agent_platform.core.evals.replay_executor import (
    DriftEvent,
    ReplayDriftError,
    ReplayToolExecutor,
)
from agent_platform.core.evals.session import Session
from agent_platform.core.evals.types import (
    ActionCallingResult,
    EvaluationResult,
    ExecutionState,
    Scenario,
    Trial,
    TrialStatus,
)
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.runs.run import Run
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.thread import Thread
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.server.agent_architectures.arch_manager import AgentArchManager
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.constants import EVALS_SYSTEM_USER_SUB
from agent_platform.server.evals.errors import (
    TrialRateLimitedError,
    is_rate_limit_error,
    log_and_format_error,
    retry_after_from_exception,
)
from agent_platform.server.evals.evaluations.flow_adherence import evaluate_flow_adherence
from agent_platform.server.evals.evaluations.response_accuracy import evaluate_response_accuracy
from agent_platform.server.file_manager import FileManagerService
from agent_platform.server.kernel.kernel import AgentServerKernel
from agent_platform.server.kernel.tools import AgentServerToolsInterface
from agent_platform.server.storage.option import StorageService

logger = logging.getLogger(__name__)


def _list_scenario_next_user_messages(scenario: Scenario, start_index: int) -> tuple[list[ThreadMessage], int | None]:
    messages = scenario.messages
    n = len(messages)
    if not (0 <= start_index < n):
        raise ValueError(f"start_index={start_index} out of range user message")

    if messages[start_index].role != "user":
        raise ValueError("Start message is not a user message")

    i = start_index
    while i < n and messages[i].role == "user":
        i += 1
    users_block = messages[start_index:i]

    j = i
    while j < n and messages[j].role != "user":
        j += 1

    next_user_index = j if j < n and messages[j].role == "user" else None

    return [message.copy_with_new_ids() for message in users_block], next_user_index


def _list_scenario_next_agent_messages(scenario: Scenario, start_index: int) -> tuple[list[ThreadMessage], int | None]:
    messages = scenario.messages
    n = len(messages)
    if not (0 <= start_index < n):
        raise ValueError(f"start_index={start_index} out of range agent message")

    if messages[start_index].role != "agent":
        raise ValueError("Start message is not an agent message")

    i = start_index
    while i < n and messages[i].role == "agent":
        i += 1
    agents_block = messages[start_index:i]

    j = i
    while j < n and messages[j].role != "agent":
        j += 1

    next_agent_index = j if j < n and messages[j].role == "agent" else None

    return [message.copy_with_new_ids() for message in agents_block], next_agent_index


def _get_observability_config(agent: Agent) -> ObservabilityConfig | None:
    """Return the agent's observability config if available."""

    for config in agent.observability_configs:
        if config.type == "langsmith":
            return config

    logger.info("No langsmith observability config: using default")
    return None


def _get_termination_reason(e: Exception) -> str:
    if isinstance(e, ReplayDriftError):
        return "REPLAY_DRIFT_ERROR"

    if isinstance(e, UnexpectedToolError) or isinstance(e, ToolExecutionError):
        return "UNEXPECTED_TOOL_ERROR"

    return "UNEXPECTED_ERROR"


def _collect_tool_executor_drifts(
    tool_executor: LiveToolExecutor | ReplayToolExecutor,
) -> list[DriftEvent]:
    if hasattr(tool_executor, "drifts"):
        return tool_executor.drifts

    return []


def _rewrite_attachment_handles(
    messages: list[ThreadMessage],
    file_id_map: dict[str, str],
) -> bool:
    """Rewrite attachment URIs in-place using the provided file ID map."""
    if not file_id_map:
        return False

    updated = False
    prefix = "agent-server-file://"

    for message in messages:
        for content in message.content:
            if isinstance(content, ThreadAttachmentContent) and content.uri:
                if content.uri.startswith(prefix):
                    source_id = content.uri[len(prefix) :]
                    new_id = file_id_map.get(source_id)
                    if new_id and new_id != source_id:
                        content.uri = f"{prefix}{new_id}"
                        updated = True

    return updated


@dataclass(frozen=True)
class ToolsBundle:
    action_tools: Sequence[ToolDefinition]
    mcp_tools: Sequence[ToolDefinition]
    issues: tuple[str, ...] = field(default_factory=tuple)

    @property
    def all(self) -> tuple[ToolDefinition, ...]:
        return (
            *self.action_tools,
            *self.mcp_tools,
        )

    def has_tool(self, tool: ToolDefinition) -> bool:
        return any(t.name == tool.name and t.input_schema == tool.input_schema for t in self.all)


@dataclass(frozen=True)
class ScenarioEvaluationPreferences:
    action_calling: bool
    flow_adherence: bool
    response_accuracy: bool
    response_accuracy_expectation: str


def _extract_enabled_flag(value: Any, default: bool) -> tuple[bool, dict[str, Any] | None]:
    if isinstance(value, dict):
        return bool(value.get("enabled", False)), value

    if isinstance(value, bool):
        return value, None

    return default, None


def _resolve_scenario_evaluation_preferences(scenario: Scenario) -> ScenarioEvaluationPreferences:
    default_expectation = scenario.description
    metadata = scenario.metadata if isinstance(scenario.metadata, dict) else {}
    evaluations_metadata = metadata.get("evaluations")

    if isinstance(evaluations_metadata, dict):
        action_calling_enabled, _ = _extract_enabled_flag(evaluations_metadata.get("action_calling"), False)
        if not action_calling_enabled:
            legacy_flag, _ = _extract_enabled_flag(evaluations_metadata.get("live_actions"), False)
            action_calling_enabled = action_calling_enabled or legacy_flag
        flow_adherence_enabled, _ = _extract_enabled_flag(evaluations_metadata.get("flow_adherence"), False)
        response_accuracy_enabled, response_accuracy_config = _extract_enabled_flag(
            evaluations_metadata.get("response_accuracy"), False
        )

        response_accuracy_expectation = default_expectation
        if isinstance(response_accuracy_config, dict):
            expectation = response_accuracy_config.get("expectation")
            if isinstance(expectation, str):
                expectation = expectation.strip()
            if expectation:
                response_accuracy_expectation = expectation
    else:
        action_calling_enabled = True
        flow_adherence_enabled = True
        response_accuracy_enabled = True
        response_accuracy_expectation = default_expectation

    return ScenarioEvaluationPreferences(
        action_calling=action_calling_enabled,
        flow_adherence=flow_adherence_enabled,
        response_accuracy=response_accuracy_enabled,
        response_accuracy_expectation=response_accuracy_expectation,
    )


async def _copy_scenario_files_to_run_thread(
    storage: StorageDependency,
    scenario: Scenario,
    destination_thread: Thread,
    destination_user_id: str,
) -> dict[str, str]:
    """Copy files associated with the scenario to the destination thread.

    Returns a mapping from source scenario file IDs to the new thread file IDs.
    """

    try:
        source_files = await storage.get_scenario_files(scenario.scenario_id, scenario.user_id)
        logger.info(
            "Found %s scenario file(s) for scenario %s",
            len(source_files),
            scenario.scenario_id,
        )
        source_context = f"scenario {scenario.scenario_id}"
    except Exception as exc:
        logger.warning(
            "Unable to list files for scenario %s: %s",
            scenario.scenario_id,
            exc,
        )
        source_files = []
        source_context = None

    if not source_files:
        logger.info(
            f"No files to copy for scenario {scenario.scenario_id}",
        )
        return {}

    file_manager = FileManagerService.get_instance(storage)

    uploads: list[tuple[UploadFile, BinaryIO]] = []
    source_ids: list[str] = []
    try:
        for uploaded_file in source_files:
            try:
                file_bytes = await file_manager.read_file_contents(
                    uploaded_file.file_id,
                    scenario.user_id,
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to read filefile_id={uploaded_file.file_id}scenario=_id={scenario.scenario_id}error={exc}",
                )
                continue

            temp_file = SpooledTemporaryFile()
            temp_file.write(file_bytes)
            temp_file.seek(0)

            file = cast(BinaryIO, temp_file)
            upload = UploadFile(
                filename=uploaded_file.file_ref,
                file=file,
                headers=Headers(
                    {
                        "content-type": uploaded_file.mime_type or "application/octet-stream",
                    }
                ),
            )
            uploads.append((upload, file))
            source_ids.append(uploaded_file.file_id)

        if not uploads:
            logger.info(
                f"No readable files found when copying scenario "
                f"attachments for {source_context or f'scenario {scenario.scenario_id}'}",
            )
            return {}

        payloads = [UploadFilePayload(file=upload) for upload, _ in uploads]
        destination_files = await file_manager.upload(payloads, destination_thread, destination_user_id)
        logger.info(
            f"Copied {len(uploads)} scenario files "
            f"from {source_context or f'scenario {scenario.scenario_id}'} to run thread",
        )
        return {
            source_id: dest.file_id
            for source_id, dest in zip(source_ids, destination_files, strict=False)
            if dest is not None
        }
    finally:
        for upload, temp_file in uploads:
            try:
                await upload.close()
            except Exception:
                logger.debug("Error closing upload file during cleanup", exc_info=True)
            try:
                temp_file.close()
            except Exception:
                logger.debug("Error closing temporary file during cleanup", exc_info=True)


async def _gather_agent_tools(agent: Agent, context: AgentServerContext) -> ToolsBundle:
    kernel = create_minimal_kernel(context)
    iface = AgentServerToolsInterface()
    iface.attach_kernel(kernel)

    action_tools, action_issues = await iface.from_action_packages(agent.action_packages)
    mcp_tools, mcp_issues = await iface.from_mcp_servers(agent.mcp_servers)

    issues = [*action_issues, *mcp_issues]

    logger.info(f"Tools gathered: action={len(action_tools)}, mcp={len(mcp_tools)}")
    if issues:
        logger.info(f"Tool issues: {', '.join(issues)}")

    return ToolsBundle(
        action_tools=action_tools,
        mcp_tools=mcp_tools,
        issues=tuple(issues),
    )


async def _terminate_and_return_not_ok(
    storage: StorageDependency, task_id: str, state: ExecutionState, reason: str, issues: list[str]
) -> bool:
    state.termination = reason
    state.status = "ERROR"
    state.error_message = "; ".join(issues)
    state.finished_at = datetime.now()
    await storage.update_trial_execution(task_id, state)
    return False


async def run_scenario(task: Trial) -> bool:
    if task.status != TrialStatus.EXECUTING:
        raise RuntimeError(f"Trial {task.trial_id} is not being executing.")

    storage = StorageService.get_instance()

    system_user, _ = await storage.get_or_create_user(EVALS_SYSTEM_USER_SUB)

    scenario = await storage.get_scenario(task.scenario_id)
    if scenario is None:
        raise RuntimeError(f"Cannot find scenario {task.scenario_id}")

    scenario_run = await storage.get_scenario_run(task.scenario_run_id)
    if scenario_run is None:
        raise RuntimeError(f"Cannot find scenario run {task.scenario_run_id}")

    agent = await storage.get_agent(system_user.user_id, scenario.agent_id)
    if agent is None:
        raise RuntimeError(f"Cannot find agent {scenario.agent_id}")

    drift_policy_overrides: dict[str, Any] | None = None
    execution_mode = "replay"
    if isinstance(scenario.metadata, dict):
        raw_policy = scenario.metadata.get("drift_policy")
        if isinstance(raw_policy, dict):
            execution_mode = raw_policy.get("tool_execution_mode", execution_mode)
            filtered_policy = {
                key: raw_policy[key]
                for key in (
                    "assert_all_consumed",
                    "allow_llm_arg_validation",
                    "allow_llm_interpolation",
                )
                if key in raw_policy
            }
            if filtered_policy:
                drift_policy_overrides = filtered_policy

    state = ExecutionState(execution_mode)

    runbook_updated_at = scenario_run.configuration.get("runbook_updated_at", None)
    architecture_version = scenario_run.configuration.get("architecture_version", None)
    architecture_name = scenario_run.configuration.get("architecture_name", None)
    models = scenario_run.configuration.get("models", None)

    configuration_issues = []
    for label, expected, found in [
        ("architecture version", architecture_version, agent.agent_architecture.version),
        ("architecture name", architecture_name, agent.agent_architecture.name),
        ("runbook updated at", runbook_updated_at, agent.runbook_structured.updated_at.isoformat()),
        ("models", models, agent.get_agent_models()),
    ]:
        if expected != found:
            configuration_issues.append(f"expected {label} {expected}, found {found}")

    if configuration_issues:
        logger.info(f"Agent configuration is invalid: {configuration_issues}")
        # this is a very edge case
        # it can happen only if an agent is updated between a run and its execution
        return await _terminate_and_return_not_ok(
            storage, task.trial_id, state, "INVALID_AGENT_CONFIGURATION", configuration_issues
        )

    observability_config = _get_observability_config(agent)

    server_context = AgentServerContext.from_request(
        request=Request(scope={"type": "http", "method": "POST"}),
        user=system_user,
        version="2.0.0",
        observability_config=observability_config,
        agent_id=agent.agent_id,
    )

    agent_tools = await _gather_agent_tools(agent, server_context)
    if agent_tools.issues:
        logger.warning(
            f"One or more agent tools failed to initialize; continuing anyway: {'; '.join(agent_tools.issues)}",
        )

    agent_tool_names = [tool.name for tool in agent_tools.all]
    logger.info(f"agent has the following tools available: {', '.join(agent_tool_names)}")
    # force agent to use client side tools
    agent = agent.copy(mcp_servers=[], action_packages=[])

    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    start_with_agent = len(scenario.messages) > 0 and scenario.messages[0].role == "agent"
    initial_agent_messages, _ = _list_scenario_next_agent_messages(scenario, 0) if start_with_agent else ([], None)

    thread_metadata = {
        "scenario_id": scenario.scenario_id,
        "scenario_run_id": scenario_run.scenario_run_id,
        "trial_index": task.index_in_run,
        "trial_id": task.trial_id,
    }
    if agent_tools.issues:
        thread_metadata["tool_gathering_issues"] = list(agent_tools.issues)

    new_thread = Thread(
        name=(
            f'"{scenario.name}" - '
            f"Run {scenario_run.scenario_run_id[:8]}: "
            f"{task.index_in_run + 1} out of {scenario_run.num_trials}"
        ),
        user_id=system_user.user_id,
        agent_id=agent.agent_id,
        thread_id=str(uuid4()),
        messages=initial_agent_messages,
        metadata=thread_metadata,
    )
    await storage.upsert_thread(system_user.user_id, new_thread)

    await storage.set_trial_thread(trial_id=task.trial_id, thread_id=new_thread.thread_id)

    # files are scoped by thread, so we need to copy them over
    scenario_file_id_map = await _copy_scenario_files_to_run_thread(
        storage=storage,
        scenario=scenario,
        destination_thread=new_thread,
        destination_user_id=system_user.user_id,
    )
    if scenario_file_id_map:
        if _rewrite_attachment_handles(new_thread.messages, scenario_file_id_map):
            await storage.overwrite_thread_messages(new_thread.thread_id, new_thread.messages)
        new_thread = await storage.get_thread(system_user.user_id, new_thread.thread_id)

    current_user_message_index = len(initial_agent_messages)
    current_turn = 1
    drifts = []
    try:
        while True:
            logger.info(f"[turn={current_turn}] starting a new turn")

            if current_user_message_index is None:
                logger.info("No further user messages. Terminating...")
                state.termination = "END_OF_CONVERSATION"
                state.status = "COMPLETED"
                state.drift_events = drifts
                state.finished_at = datetime.now()

                return True

            offset = current_user_message_index
            user_messages_from_scenario, next_user_message_index = _list_scenario_next_user_messages(
                scenario=scenario, start_index=current_user_message_index
            )
            agent_messages_from_scenario, _ = _list_scenario_next_agent_messages(
                scenario=scenario, start_index=len(user_messages_from_scenario) + offset
            )

            if scenario_file_id_map:
                _rewrite_attachment_handles(user_messages_from_scenario, scenario_file_id_map)
                _rewrite_attachment_handles(agent_messages_from_scenario, scenario_file_id_map)

            tool_executor = None

            if execution_mode == "live":
                tool_executor = LiveToolExecutor(
                    list(agent_tools.all),
                    issues=list(agent_tools.issues),
                )
            elif execution_mode == "replay":
                tool_executor = ReplayToolExecutor.from_conversation(
                    agent_messages_from_scenario,
                    policy_overrides=drift_policy_overrides,
                )
                missing_tools_in_agent = [tool for tool in tool_executor.tools if not agent_tools.has_tool(tool)]

                if len(missing_tools_in_agent) > 0:
                    message = (
                        f"The following tools used in the conversation "
                        f"are missing from agent or have different input schema "
                        f"in the selected agent: "
                        f"{', '.join([tool.name for tool in missing_tools_in_agent])}"
                    )
                    if agent_tools.issues:
                        message = f"{message}. We had some issues in gathering tools: {'; '.join(agent_tools.issues)}"
                    logger.info(f"Agent tools don't match the conversation: {message}")
                    state.termination = "AGENT_TOOL_MISMATCH"
                    state.status = "ERROR"
                    state.error_message = message
                    additional_drifts = (
                        _collect_tool_executor_drifts(tool_executor) if tool_executor is not None else []
                    )
                    state.drift_events = [*drifts, *additional_drifts]
                    state.finished_at = datetime.now()

                    return False
            else:
                raise RuntimeError(f"Unknown execution mode {execution_mode}")

            for user_message in user_messages_from_scenario:
                await storage.add_message_to_thread(system_user.user_id, new_thread.thread_id, user_message)
            new_thread = await storage.get_thread(system_user.user_id, new_thread.thread_id)

            run = Run(
                run_id=str(uuid4()),
                agent_id=agent.agent_id,
                thread_id=new_thread.thread_id,
                status="running",
                run_type="stream",
                metadata={"turn": current_turn},
            )
            await storage.upsert_run(run)

            runner = await agent_arch_manager.get_runner(
                agent.agent_architecture.name,
                agent.agent_architecture.version,
                new_thread.thread_id,
            )
            kernel = AgentServerKernel(
                server_context,
                new_thread,
                agent,
                run,
                tool_executor.tools,
            )
            tool_executor.attach_kernel(kernel)

            agent_client = AgentClient(session=Session(runner=runner, kernel=kernel), tool_executor=tool_executor)
            logger.info(f"[turn={current_turn}] Waiting for agent response")

            try:
                await agent_client.run_once()
                tool_executor.finalize()
            except Exception as e:
                if is_rate_limit_error(e):
                    retry_after = retry_after_from_exception(e)
                    logger.warning(
                        "Trial %s turn=%s rate limited; scheduling retry.",
                        task.trial_id,
                        current_turn,
                    )
                    raise TrialRateLimitedError(
                        "Trial rate limited; will retry later.",
                        retry_after_seconds=retry_after,
                    ) from e

                logger.info(f"Turn {current_turn}: {e}.")
                state.termination = _get_termination_reason(e)
                state.status = "ERROR"
                state.error_message = log_and_format_error(
                    log_message=(f"Unexpected error during scenario turn {current_turn} for trial {task.trial_id}"),
                    user_message=(f"An unexpected error occurred while executing turn {current_turn} of the scenario."),
                )
                additional_drifts = _collect_tool_executor_drifts(tool_executor) if tool_executor is not None else []
                state.drift_events = [*drifts, *additional_drifts]
                state.finished_at = datetime.now()

                return False

            current_turn += 1
            current_user_message_index = next_user_message_index
            if tool_executor is not None:
                drifts.extend(_collect_tool_executor_drifts(tool_executor))
    except TrialRateLimitedError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error when processing evals: {e}.")
        state.termination = _get_termination_reason(e)
        state.error_message = log_and_format_error(
            log_message=(f"Unexpected error when processing scenario run for trial {task.trial_id}"),
            user_message="An unexpected error occurred while running the evaluation scenario.",
        )
        state.drift_events = drifts
        state.status = "ERROR"
        state.finished_at = datetime.now()

        return False
    finally:
        logger.info("Updating states and terminating")

        await storage.update_trial_execution(task.trial_id, state)

        # TODO we want to save metadata, but we need to
        # recreate messages with new ids
        if state.error_message:
            messages = [message.copy_with_new_ids() for message in new_thread.messages]
            new_thread.metadata["evaluation_error"] = state.error_message
            new_thread.messages = messages
            await storage.upsert_thread(system_user.user_id, new_thread)


async def run_evaluations(task: Trial, ran_successfully: bool) -> tuple[str, str | None]:
    storage = StorageService.get_instance()

    if task.execution_state.status == "ERROR" and task.execution_state.termination != "REPLAY_DRIFT_ERROR":
        return TrialStatus.ERROR.value, task.execution_state.error_message

    system_user, _ = await storage.get_or_create_user(EVALS_SYSTEM_USER_SUB)

    scenario = await storage.get_scenario(task.scenario_id)
    if scenario is None:
        raise RuntimeError(f"Cannot find scenario {task.scenario_id}")

    if task.thread_id is None:
        raise RuntimeError(f"No thread for {task.trial_id}")

    thread = await storage.get_thread(system_user.user_id, task.thread_id)

    if thread is None:
        raise RuntimeError(f"Cannot find thread {task.thread_id}")

    preferences = _resolve_scenario_evaluation_preferences(scenario)

    action_calling: ActionCallingResult | None = None
    if preferences.action_calling:
        action_calling = ActionCallingResult(
            issues=[event.message for event in task.execution_state.drift_events],
            passed=task.execution_state.status == "COMPLETED",
        )

    # if simulation is terminated because of drift
    # no need to run LLM judges: return error
    if task.execution_state.termination == "REPLAY_DRIFT_ERROR":
        evaluations_to_persist = [result for result in (action_calling,) if result is not None]
        await storage.update_trial_evaluation_results(task.trial_id, evaluations_to_persist)
        return TrialStatus.ERROR.value, None

    evaluations: list[EvaluationResult] = []

    if action_calling is not None:
        evaluations.append(action_calling)

    if preferences.flow_adherence:
        flow_adherence = await evaluate_flow_adherence(thread, scenario, system_user, storage)
        evaluations.append(flow_adherence)

    if preferences.response_accuracy:
        response_accuracy = await evaluate_response_accuracy(
            thread,
            scenario,
            system_user,
            storage,
            preferences.response_accuracy_expectation,
        )
        evaluations.append(response_accuracy)

    await storage.update_trial_evaluation_results(task.trial_id, evaluations)

    status = TrialStatus.COMPLETED.value if all(e.passed for e in evaluations) else TrialStatus.ERROR.value

    return status, None
