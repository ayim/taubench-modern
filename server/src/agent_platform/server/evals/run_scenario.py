import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent
from typing import cast
from uuid import uuid4

from fastapi import Request

from agent_platform.architectures.default.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core.agent.agent import Agent
from agent_platform.core.context import AgentServerContext
from agent_platform.core.evals.agent_client import (
    AgentClient,
    ToolExecutionError,
    UnexpectedToolError,
)
from agent_platform.core.evals.replay_executor import ReplayDriftError, ReplayToolExecutor
from agent_platform.core.evals.session import Session
from agent_platform.core.evals.types import (
    ActionCallingResult,
    EvaluationResult,
    ExecutionState,
    FlowAdherenceResult,
    ResponseAccuracyResult,
    Scenario,
    Trial,
    TrialStatus,
)
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.runs.run import Run
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.thread import Thread
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.user import User
from agent_platform.server.agent_architectures.arch_manager import AgentArchManager
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.prompt import prompt_generate
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.constants import EVALS_SYSTEM_USER_SUB
from agent_platform.server.kernel.kernel import AgentServerKernel
from agent_platform.server.kernel.tools import AgentServerToolsInterface
from agent_platform.server.storage.option import StorageService

logger = logging.getLogger(__name__)


def _extract_evaluation_from_model_response(text: str) -> dict | None:
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.debug(f"Cannot parse JSON: {e}")
        return None


def _list_scenario_next_user_messages(
    scenario: Scenario, start_index: int
) -> tuple[list[ThreadMessage], int | None]:
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


def _list_scenario_next_agent_messages(
    scenario: Scenario, start_index: int
) -> tuple[list[ThreadMessage], int | None]:
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


def _get_termination_reason(e: Exception) -> str:
    if isinstance(e, ReplayDriftError):
        return "REPLAY_DRIFT_ERROR"

    if isinstance(e, UnexpectedToolError) or isinstance(e, ToolExecutionError):
        return "UNEXPECTED_TOOL_ERROR"

    return "UNEXPECTED_ERROR"


@dataclass(frozen=True)
class ToolsBundle:
    action_tools: Sequence[ToolDefinition]
    mcp_tools: Sequence[ToolDefinition]

    @property
    def all(self) -> tuple[ToolDefinition, ...]:
        return (
            *self.action_tools,
            *self.mcp_tools,
        )

    def has_tool(self, tool: ToolDefinition) -> bool:
        return any(t.name == tool.name and t.input_schema == tool.input_schema for t in self.all)


async def _gather_agent_tools(
    agent: Agent, context: AgentServerContext
) -> tuple[ToolsBundle, list[str]]:
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
    ), issues


async def _terminate_and_return_not_ok(
    storage: StorageDependency, task_id: str, state: ExecutionState, reason: str, issues: list[str]
) -> bool:
    state.termination = reason
    state.status = "ERROR"
    state.error_message = "; ".join(issues)
    state.finished_at = datetime.now()
    await storage.update_trial_execution(task_id, state)
    return False


async def run_scenario(task: Trial) -> bool:  # noqa: PLR0915, C901, PLR0912
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

    state = ExecutionState()

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

    server_context = AgentServerContext.from_request(
        request=Request(scope={"type": "http", "method": "POST"}),
        user=system_user,
        version="2.0.0",
        agent_id=agent.agent_id,
    )

    agent_tools, issues = await _gather_agent_tools(agent, server_context)

    if len(issues) > 0:
        logger.info(f"Cannot upload some agent tools: {issues}")
        return await _terminate_and_return_not_ok(
            storage, task.trial_id, state, "TOOL_GATHERING_ISSUES", issues
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
    initial_agent_messages, _ = (
        _list_scenario_next_agent_messages(scenario, 0) if start_with_agent else ([], None)
    )

    new_thread = Thread(
        name=(
            f'Simulation "{scenario.name}" - '
            f"Run {scenario_run.scenario_run_id[:8]}: "
            f"{task.index_in_run + 1} out of {scenario_run.num_trials}"
        ),
        user_id=system_user.user_id,
        agent_id=agent.agent_id,
        thread_id=str(uuid4()),
        messages=initial_agent_messages,
        metadata={
            "scenario_id": scenario.scenario_id,
            "scenario_run_id": scenario_run.scenario_run_id,
            "trial_index": task.index_in_run,
            "trial_id": task.trial_id,
        },
    )
    await storage.upsert_thread(system_user.user_id, new_thread)

    await storage.set_trial_thread(trial_id=task.trial_id, thread_id=new_thread.thread_id)

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
            user_messages_from_scenario, next_user_message_index = (
                _list_scenario_next_user_messages(
                    scenario=scenario, start_index=current_user_message_index
                )
            )
            agent_messages_from_scenario, _ = _list_scenario_next_agent_messages(
                scenario=scenario, start_index=len(user_messages_from_scenario) + offset
            )

            tool_executor = ReplayToolExecutor.from_conversation(agent_messages_from_scenario)
            missing_tools_in_agent = [
                tool for tool in tool_executor.tools if not agent_tools.has_tool(tool)
            ]

            if len(missing_tools_in_agent) > 0:
                message = (
                    f"The following tools used in the conversation "
                    f"are missing from agent or have different input schema "
                    f"in the selected agent: "
                    f"{', '.join([tool.name for tool in missing_tools_in_agent])}"
                )
                logger.info(f"Agent tools don't match the conversation: {message}")
                state.termination = "AGENT_TOOL_MISMATCH"
                state.status = "ERROR"
                state.error_message = message
                state.drift_events = drifts + tool_executor.drifts
                state.finished_at = datetime.now()

                return False

            for user_message in user_messages_from_scenario:
                await storage.add_message_to_thread(
                    system_user.user_id, new_thread.thread_id, user_message
                )
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

            agent_client = AgentClient(
                session=Session(runner=runner, kernel=kernel), tool_executor=tool_executor
            )
            logger.info(f"[turn={current_turn}] Waiting for agent response")

            try:
                await agent_client.run_once()
                tool_executor.finalize()
            except Exception as e:
                logger.info(f"Turn {current_turn}: {e}.")
                state.termination = _get_termination_reason(e)
                state.status = "ERROR"
                state.error_message = str(e)
                state.drift_events = drifts + tool_executor.drifts
                state.finished_at = datetime.now()

                return False

            current_turn += 1
            current_user_message_index = next_user_message_index
            drifts.extend(tool_executor.drifts)
    except Exception as e:
        logger.error(f"Unexpected error when processing evals: {e}.")
        state.termination = _get_termination_reason(e)
        state.error_message = str(e)
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


async def _evaluate_flow_adherence(
    thread: Thread, scenario: Scenario, user: User, storage: StorageDependency
) -> EvaluationResult | None:
    logger.info("evaluating flow adherence")
    system_message = dedent("""
        You are an expert evaluator of LLM conversations. \
        Your role is to analyse the conversation history between the agent and user. \
        Provide accurate, objective evaluations.
    """)

    judge_prompt_msg = dedent("""
        Please evaluate if the target conversation is CONSISTENT with the. \
        benchmark according to the given criteria. \
        CRITERIA: \
        - Allow natural variation in wording, but not in intent or outcomes.
        TARGET CONVERSATION: \
        {target_conversation} \
        BENCHMARK CONVERSATION: \
        {benchmark_conversation} \
        Please respond with a JSON object containing (in this order): \
        - "explanation": a brief explanation of your thoughts/evaluation \
        - "score": a number from 0-10 indicating quality (10 = perfect match) \
        - "passed": true/false indicating if the response meets the criteria (score >= 6) \
        Output RAW JSON only. Do not use code fences, markdown, or language tags. \
        The first character must be "{{" and the last must be "}}".
    """)

    mock_request = Request(scope={"type": "http", "method": "POST"})
    ctx = AgentServerContext.from_request(
        request=mock_request,
        user=user,
        version="2.0.0",
    )
    kernel = create_minimal_kernel(ctx)
    kernel.converters.set_thread_message_conversion_function(
        thread_messages_to_prompt_messages,
    )

    async def format_conversation(messages: list[ThreadMessage]):
        converted_messages = await kernel.converters.thread_messages_to_prompt_messages(messages)
        temp_prompt = Prompt(messages=cast(list, converted_messages))
        return temp_prompt.to_pretty_yaml(include=["messages"])

    formatted_target_conversation_thread = await format_conversation(thread.messages)
    formatted_benchmark_conversation = await format_conversation(scenario.messages)

    judge_prompt_msg = judge_prompt_msg.format(
        target_conversation=formatted_target_conversation_thread,
        benchmark_conversation=formatted_benchmark_conversation,
    )

    prompt = Prompt(
        system_instruction=system_message,
        messages=[PromptUserMessage(content=[PromptTextContent(text=judge_prompt_msg)])],
        temperature=0.0,
    )
    response = await prompt_generate(
        prompt,
        user=user,
        storage=storage,
        request=Request(scope={"type": "http", "method": "POST"}),
        agent_id=scenario.agent_id,
    )

    if content := response.content:
        if text_content := [c.text for c in content if isinstance(c, ResponseTextContent)]:
            response_text = text_content[-1]
            logger.debug(f"Flow Adherence response: {response_text}")

            parsed_result = _extract_evaluation_from_model_response(response_text)
            if parsed_result is None:
                logger.error("Flow adherence cannot be parsed from agent response")
                return FlowAdherenceResult(
                    passed=False,
                    explanation="Unexpected error: cannot evaluate flow adherence",
                    score=0,
                )

            try:
                return FlowAdherenceResult(**parsed_result)
            except Exception as e:
                if isinstance(e, TypeError):
                    logger.error("Parsed JSON is not Flow Adherence")
                    return FlowAdherenceResult(
                        passed=False,
                        explanation="Unexpected error: cannot evaluate flow adherence",
                        score=0,
                    )

                raise

    logger.error("Flow Adherence is not in agent response")
    return FlowAdherenceResult(
        passed=False, explanation="Unexpected error: cannot evaluate flow adherence", score=0
    )


async def _evaluate_response_accuracy(
    thread: Thread, scenario: Scenario, user: User, storage: StorageDependency
) -> EvaluationResult | None:
    system_message = dedent("""
        You are an expert evaluator of LLM conversations. \
        Your role is to analyse the conversation history between the agent and user. \
        Provide accurate, objective evaluations.
    """)

    judge_prompt_msg = dedent("""
        Please evaluate if the target conversation is accurate based on CRITERIA. \
        CRITERIA: \
        {criteria} \
        CONVERSATION: \
        {target_conversation} \
        Please respond with a JSON object containing (in this order): \
        - "explanation": a brief explanation of your thoughts/evaluation \
        - "score": a number from 0-10 indicating quality (10 = perfect match) \
        - "passed": true/false indicating if the response meets the criteria (score >= 6) \
        Output RAW JSON only. Do not use code fences, markdown, or language tags. \
        The first character must be "{{" and the last must be "}}".
    """)

    mock_request = Request(scope={"type": "http", "method": "POST"})
    ctx = AgentServerContext.from_request(
        request=mock_request,
        user=user,
        version="2.0.0",
    )
    kernel = create_minimal_kernel(ctx)
    kernel.converters.set_thread_message_conversion_function(
        thread_messages_to_prompt_messages,
    )

    async def format_conversation(messages: list[ThreadMessage]):
        converted_messages = await kernel.converters.thread_messages_to_prompt_messages(messages)
        temp_prompt = Prompt(messages=cast(list, converted_messages))
        return temp_prompt.to_pretty_yaml(include=["messages"])

    formatted_target_conversation_thread = await format_conversation(thread.messages)

    judge_prompt_msg = judge_prompt_msg.format(
        target_conversation=formatted_target_conversation_thread,
        criteria=scenario.description,
    )

    prompt = Prompt(
        system_instruction=system_message,
        messages=[PromptUserMessage(content=[PromptTextContent(text=judge_prompt_msg)])],
        temperature=0.0,
    )
    response = await prompt_generate(
        prompt,
        user=user,
        storage=storage,
        request=Request(scope={"type": "http", "method": "POST"}),
        agent_id=scenario.agent_id,
    )

    if content := response.content:
        if text_content := [c.text for c in content if isinstance(c, ResponseTextContent)]:
            response_text = text_content[-1]
            logger.debug(f"Response accuracy response: {response_text}")

            parsed_result = _extract_evaluation_from_model_response(response_text)
            if parsed_result is None:
                logger.error("Response accuracy cannot be parsed from agent response")
                return ResponseAccuracyResult(
                    passed=False, explanation="Unexpected error: cannot evaluate accuracy", score=0
                )

            try:
                return ResponseAccuracyResult(**parsed_result)
            except Exception as e:
                if isinstance(e, TypeError):
                    logger.error("Parsed JSON is not Response accuracy")
                    return ResponseAccuracyResult(
                        passed=False,
                        explanation="Unexpected error: cannot evaluate accuracy",
                        score=0,
                    )

                raise

    logger.error("Response accuracy is not in agent response")
    return ResponseAccuracyResult(
        passed=False, explanation="Unexpected error: cannot evaluate accuracy", score=0
    )


async def run_evaluations(task: Trial, ran_successfully: bool) -> tuple[str, str | None]:
    storage = StorageService.get_instance()

    if (
        task.execution_state.status == "ERROR"
        and task.execution_state.termination != "REPLAY_DRIFT_ERROR"
    ):
        return TrialStatus.ERROR.value, task.execution_state.error_message

    action_calling = ActionCallingResult(
        issues=[event.message for event in task.execution_state.drift_events],
        passed=task.execution_state.status == "COMPLETED",
    )

    # if simulation is terminated because of drift
    # no need to run LLM judges: return error
    if task.execution_state.termination == "REPLAY_DRIFT_ERROR":
        await storage.update_trial_evaluation_results(task.trial_id, [action_calling])
        return TrialStatus.ERROR.value, None

    system_user, _ = await storage.get_or_create_user(EVALS_SYSTEM_USER_SUB)

    scenario = await storage.get_scenario(task.scenario_id)
    if scenario is None:
        raise RuntimeError(f"Cannot find scenario {task.scenario_id}")

    if task.thread_id is None:
        raise RuntimeError(f"No thread for {task.trial_id}")

    thread = await storage.get_thread(system_user.user_id, task.thread_id)

    if thread is None:
        raise RuntimeError(f"Cannot find thread {task.thread_id}")

    flow_adherence = await _evaluate_flow_adherence(thread, scenario, system_user, storage)
    response_accuracy = await _evaluate_response_accuracy(thread, scenario, system_user, storage)
    evaluations = [flow_adherence, response_accuracy, action_calling]

    await storage.update_trial_evaluation_results(task.trial_id, evaluations)

    status = (
        TrialStatus.COMPLETED.value
        if all(e.passed for e in evaluations)
        else TrialStatus.ERROR.value
    )

    return status, None
