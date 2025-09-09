from dataclasses import dataclass
from typing import Self
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from structlog import get_logger

from agent_platform.core.agent.agent import Agent
from agent_platform.core.context import AgentServerContext
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.evals.agent_client import AgentClient
from agent_platform.core.evals.replay_executor import ReplayToolExecutor
from agent_platform.core.evals.session import Session
from agent_platform.core.evals.types import Scenario, ScenarioRun, Trial, TrialStatus
from agent_platform.core.runs.run import Run
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.thread import Thread
from agent_platform.server.agent_architectures.arch_manager import AgentArchManager
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth.handlers import AuthedUser
from agent_platform.server.constants import WORK_ITEMS_SYSTEM_USER_SUB, SystemConfig
from agent_platform.server.kernel.kernel import AgentServerKernel


def _require_evals_enabled():
    """Raise an error if evals are disabled in configuration."""
    if not SystemConfig.enable_evals:
        raise PlatformHTTPError(ErrorCode.FORBIDDEN, "Evals feature is disabled")


router = APIRouter(dependencies=[Depends(_require_evals_enabled)])
logger = get_logger(__name__)


@dataclass(frozen=True)
class CreateScenarioPayload:
    name: str
    description: str
    thread_id: str

    @classmethod
    def to_scenario(cls, payload: Self, user_id: str, thread: Thread) -> Scenario:
        return Scenario(
            scenario_id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            thread_id=thread.thread_id,
            user_id=user_id,
            agent_id=thread.agent_id,
            messages=thread.messages,
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
    def to_scenario_run(cls, payload: Self, user_id: str, scenario_id: str) -> ScenarioRun:
        scenario_run_id = str(uuid4())
        trials = [
            Trial(
                trial_id=str(uuid4()),
                scenario_run_id=scenario_run_id,
                scenario_id=scenario_id,
                thread_id=None,
                index_in_run=index_in_run,
                messages=[],
            )
            for index_in_run in range(payload.num_trials)
        ]
        return ScenarioRun(
            scenario_run_id=scenario_run_id,
            num_trials=payload.num_trials,
            scenario_id=scenario_id,
            trials=trials,
            user_id=user_id,
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

    scenario_run = CreateScenarioRunPayload.to_scenario_run(
        payload, user.user_id, scenario.scenario_id
    )

    return await storage.create_scenario_run(scenario_run)


@router.get("/scenarios/{scenario_id}/runs/latest", response_model=ScenarioRun)
async def get_latest_scenario_run(scenario_id: str, user: AuthedUser, storage: StorageDependency):
    scenario = await storage.get_scenario(scenario_id=scenario_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    runs = await storage.list_scenario_runs(limit=1)

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

    return await storage.list_scenario_runs(limit=limit)


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
        raise ValueError("Start message is not a user message")

    i = start_index
    while i < n and messages[i].role == "agent":
        i += 1
    agents_block = messages[start_index:i]

    j = i
    while j < n and messages[j].role != "agent":
        j += 1

    next_user_index = j if j < n and messages[j].role == "agent" else None

    return [message.copy_with_new_ids() for message in agents_block], next_user_index


async def _run_scenario_run_trial(  # noqa: PLR0913
    scenario: Scenario,
    scenario_run: ScenarioRun,
    trial: Trial,
    agent: Agent,
    storage: StorageDependency,
    server_context: AgentServerContext,
):
    if trial.status != TrialStatus.PENDING:
        raise HTTPException(status_code=419, detail="Trial already executed")

    # force agent to use client side tools
    agent = agent.copy(mcp_servers=[], action_packages=[])

    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    system_user, _ = await storage.get_or_create_user(WORK_ITEMS_SYSTEM_USER_SUB)

    new_thread = Thread(
        name=(
            f'Simulation "{scenario.name}" - '
            f"Run {scenario_run.scenario_run_id}: "
            f"{trial.index_in_run + 1} out of {scenario_run.num_trials}"
        ),
        user_id=system_user.user_id,
        agent_id=agent.agent_id,
        thread_id=str(uuid4()),
        messages=[],
        metadata={
            "scenario_id": scenario.scenario_id,
            "scenario_run_id": scenario_run.scenario_run_id,
            "trial_index": trial.index_in_run,
            "trial_id": trial.trial_id,
        },
    )
    await storage.upsert_thread(system_user.user_id, new_thread)

    await storage.set_trial_thread(trial_id=trial.trial_id, thread_id=new_thread.thread_id)

    current_turn = 1
    current_user_message_index = 0
    # TODO we assume that the first message is by user
    #      but the agent usually sends a "welcome" message
    while True:
        try:
            logger.info("[turn={next_turn}] starting a new turn")

            if current_user_message_index is None:
                logger.info("No further user messages. Terminating...")
                return await storage.mark_trial_as_completed(trial)

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

            await storage.add_messages_to_trial(trial.trial_id, user_messages_from_scenario)

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

            await storage.add_messages_to_trial(trial.trial_id, new_agent_messages)

            current_turn += 1
            current_user_message_index = next_user_message_index
        except Exception as e:
            logger.error(f"Turn {current_turn}: simulation error {e}. Terminating...")
            messages = [message.copy_with_new_ids() for message in new_thread.messages]
            new_thread.metadata["simulation_error"] = f"{e}"
            new_thread.messages = messages
            await storage.upsert_thread(system_user.user_id, new_thread)
            return await storage.mark_trial_as_failed(trial, f"{e}")


# TODO just for testing purposes until we don't have the background job
@router.post(
    "/scenarios/{scenario_id}/runs/{scenario_run_id}/execute/{trial_index}/sync",
    response_model=Trial,
)
async def execute_scenario_run_trial(  # noqa: PLR0913
    scenario_id: str,
    scenario_run_id: str,
    trial_index: int,
    user: AuthedUser,
    storage: StorageDependency,
    request: Request,
):
    scenario = await storage.get_scenario(scenario_id=scenario_id)

    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    scenario_run = await storage.get_scenario_run(scenario_run_id=scenario_run_id)

    if scenario_run is None:
        raise HTTPException(status_code=404, detail="Scenario Run not found")

    trial = await storage.get_scenario_run_trial(
        trial_index=trial_index, scenario_run_id=scenario_run_id
    )

    if trial is None:
        raise HTTPException(status_code=404, detail="Trial not found")

    agent = await storage.get_agent(user.user_id, scenario.agent_id)

    if agent is None:
        raise HTTPException(status_code=404, detail=f"Cannot find agent {scenario.agent_id}")

    server_context = AgentServerContext.from_request(
        request=request,
        user=user,
        version="2.0.0",
        agent_id=agent.agent_id,
    )

    return await _run_scenario_run_trial(
        scenario=scenario,
        scenario_run=scenario_run,
        trial=trial,
        agent=agent,
        server_context=server_context,
        storage=storage,
    )
