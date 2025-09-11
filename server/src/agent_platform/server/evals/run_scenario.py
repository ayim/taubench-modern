import logging
from uuid import uuid4

from fastapi import Request

from agent_platform.core.context import AgentServerContext
from agent_platform.core.evals.agent_client import AgentClient
from agent_platform.core.evals.replay_executor import ReplayToolExecutor
from agent_platform.core.evals.session import Session
from agent_platform.core.evals.types import Scenario, Trial, TrialStatus
from agent_platform.core.runs.run import Run
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.thread import Thread
from agent_platform.server.agent_architectures.arch_manager import AgentArchManager
from agent_platform.server.constants import EVALS_SYSTEM_USER_SUB
from agent_platform.server.kernel.kernel import AgentServerKernel
from agent_platform.server.storage.option import StorageService

logger = logging.getLogger(__name__)


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


async def run_scenario(task: Trial) -> bool:  # noqa: PLR0915
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

    # force agent to use client side tools
    agent = agent.copy(mcp_servers=[], action_packages=[])

    server_context = AgentServerContext.from_request(
        request=Request(scope={"type": "http", "method": "POST"}),
        user=system_user,
        version="2.0.0",
        agent_id=agent.agent_id,
    )

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
    while True:
        try:
            logger.info("[turn={next_turn}] starting a new turn")

            if current_user_message_index is None:
                logger.info("No further user messages. Terminating...")

                await storage.complete_trial(task.trial_id, system_user.user_id)
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

            for user_message in user_messages_from_scenario:
                await storage.add_message_to_thread(
                    system_user.user_id, new_thread.thread_id, user_message
                )
            new_thread = await storage.get_thread(system_user.user_id, new_thread.thread_id)

            await storage.add_messages_to_trial(task.trial_id, user_messages_from_scenario)

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
            logger.info("[turn={next_turn}] Waiting for agent response")

            new_agent_messages = await agent_client.run_once()

            await storage.add_messages_to_trial(task.trial_id, new_agent_messages)

            current_turn += 1
            current_user_message_index = next_user_message_index
        except Exception as e:
            logger.error(f"Turn {current_turn}: simulation error {e}. Terminating...")
            messages = [message.copy_with_new_ids() for message in new_thread.messages]
            new_thread.metadata["simulation_error"] = f"{e}"
            new_thread.messages = messages
            await storage.upsert_thread(system_user.user_id, new_thread)

            await storage.mark_trial_as_failed(task.trial_id, f"{e}")

            return False


async def run_evaluations(task: Trial, ran_successfully: bool) -> TrialStatus:
    # TODO here we run the evaluations, for now only simulation
    return task.status
