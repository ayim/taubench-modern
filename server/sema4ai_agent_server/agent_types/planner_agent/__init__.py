import re
from typing import cast

from langchain.tools import BaseTool
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    FunctionMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langgraph.checkpoint import BaseCheckpointSaver
from langgraph.graph.message import StateGraph
from structlog import get_logger
from structlog.stdlib import BoundLogger

from sema4ai_agent_server.agent_types.constants import (
    FINISH_NODE_ACTION,
    FINISH_NODE_KEY,
)
from sema4ai_agent_server.agent_types.planner_agent.models import (
    AGENT_TYPES,
    AgentType,
    bind_tools,
    get_pydantic_output_parser,
)
from sema4ai_agent_server.agent_types.planner_agent.prompts import (
    PLANNER_PROMPTS,
    REPLANNER_PROMPTS,
    STEP_EXECUTOR_PROMPT,
    STEP_REASONING_PROMPTS,
    STEP_RETRY_REASONING_PROMPTS,
)
from sema4ai_agent_server.agent_types.planner_agent.schemas import (
    CompletedPlan,
    CompletedPlanWithThought,
    ExecutedPlan,
    ExecutedPlanWithThought,
    InitialPlanningResponse,
    InitialThinkingPlanningResponse,
    PastStep,
    Plan,
    PlanExecuteAgentState,
    PlanStep,
    PlanStepWithThought,
    PlanWithThought,
    ReplannerResponse,
    ReplannerThinkerResponse,
)
from sema4ai_agent_server.agent_types.tools_agent import (
    AgentState,
    get_tools_agent_executor,
)
from sema4ai_agent_server.message_types import LiberalToolMessage
from sema4ai_agent_server.utils import current_timestamp_with_iso_week_local

logger: BoundLogger = get_logger(__name__)
STEPS_CONTENT_PATTERN = re.compile(pattern=r"^\[.*\]$")


def _clean_message(m: AnyMessage):
    if isinstance(m, LiberalToolMessage):
        _dict = m.dict()
        _dict["content"] = str(_dict["content"])
        m_c = ToolMessage(**_dict)
        return m_c
    elif isinstance(m, FunctionMessage):
        # anthropic doesn't like function messages
        return HumanMessage(content=str(m.content))
    else:
        return m


def _get_messages(messages: list[AnyMessage]) -> list[AnyMessage]:
    return [_clean_message(m) for m in messages]


def _reformat_step_message(m: AIMessage):
    new_content = f"Plan steps at this point: {m.content}"
    return AIMessage(content=new_content)


def _get_messages_for_replanner(messages: list[AnyMessage]) -> list[AnyMessage]:
    msgs = []
    for m in messages:
        if STEPS_CONTENT_PATTERN.match(m.content):
            msgs.append(_reformat_step_message(m))
        else:
            msgs.append(_clean_message(m))
    return msgs


def _get_executor_outcome_messages(
    executed_plans: list[ExecutedPlan],
) -> list[AnyMessage]:
    messages: list[AnyMessage] = []
    for executed_plan in executed_plans:
        for step in executed_plan.past_steps:
            messages.extend(step.outcome)
    return messages


def get_plan_execute_agent(
    tools: list[BaseTool],
    llm: AgentType,
    name: str,
    runbook: str,
    interrupt_before_action: bool,
    reasoning_level: int,
    checkpoint: BaseCheckpointSaver,
):
    """Create a plan and execute agent graph that uses a planner, executor, and replanner.

    The final agent is a Pregel type graph that uses a StateGraph to manage the
    state of the agent.
    """
    if not isinstance(llm, AGENT_TYPES):
        raise ValueError(
            f"Expected an LLM with one of type {AGENT_TYPES}, got {type(llm)}."
        )

    async def objective_parser_and_state_reset(state: PlanExecuteAgentState):
        """Entry node to read the objective and clear the state."""
        logger.debug(
            f"objective_parser_and_state_reset:state at start of node: {state.dict()}"
        )
        last_message = state.messages[-1]
        if state.response_type == "edge-case":
            # Do not clear state as the current plan is likely still valid
            out = {
                "response": None,
                "response_type": None,
            }
        else:
            # state needs to be reset for new plans
            out = {
                "plan_needed": False,
                "objective": last_message.content,
                "original_plan": None,
                "current_plan": None,
                "executed_plan": None,
                "response": None,
            }
        if reasoning_level > 0:
            # Add the last human message to combined messages
            if state.combined:
                if isinstance(last_message, HumanMessage):
                    out["combined"] = [last_message]
            else:
                out["combined"] = state.messages
            return out
        else:
            return out

    async def offramper(state: PlanExecuteAgentState):
        """Decides if a plan is needed and writes the plan if so.
        This node assumes reasoning_level == 0"""
        logger.debug(f"offramper:state at start of node: {state.dict()}")
        prompt = PLANNER_PROMPTS[reasoning_level]
        messages = _get_messages(state.combined)
        input = {
            "name": name,
            "datetime": current_timestamp_with_iso_week_local(),
            "runbook": runbook,
            "messages": messages,
        }
        offramper_agent: Runnable[LanguageModelInput, InitialPlanningResponse] = (
            prompt
            | bind_tools(
                llm,
                [*tools, InitialPlanningResponse],
                tool_choice="InitialPlanningResponse",
            )
            | get_pydantic_output_parser(llm, InitialPlanningResponse)
        )
        initial_thinking_response: InitialPlanningResponse = (
            offramper_agent.with_config(
                {
                    "metadata": {
                        "structured_response_config": {
                            "model_name": "InitialPlanningResponse",
                            "fields": [
                                ("steps", "message", "json"),
                            ],
                        }
                    }
                }
            ).invoke(input)
        )
        is_plannig = initial_thinking_response.plan_needed_response == "plan"
        if is_plannig:
            plan_steps = [
                PlanStep(step=step) for step in initial_thinking_response.steps
            ]
            plan = Plan(
                objective=state.objective,
                steps=plan_steps,
            )
            steps_message = AIMessage(content=plan.steps_as_string())
        else:
            plan = None
        return {
            "plan_needed": initial_thinking_response.plan_needed_response == "plan",
            "original_plan": plan,
            "current_plan": plan,
            "messages": [steps_message],
        }

    async def offramper_thinker(state: PlanExecuteAgentState):
        """Decides if a plan is needed and writes the plan if so.
        This node assumes reasoning_level > 0"""
        logger.debug(f"offramper_thinker: {state.dict()}")
        prompt = PLANNER_PROMPTS[reasoning_level]
        messages = _get_messages(state.combined)
        input = {
            "name": name,
            "datetime": current_timestamp_with_iso_week_local(),
            "runbook": runbook,
            "messages": messages,
        }
        offramper_agent: Runnable[
            LanguageModelInput, InitialThinkingPlanningResponse
        ] = (
            prompt
            | bind_tools(
                llm,
                [*tools, InitialThinkingPlanningResponse],
                tool_choice="InitialThinkingPlanningResponse",
            )
            | get_pydantic_output_parser(llm, InitialThinkingPlanningResponse)
        )
        initial_thinking_response: InitialThinkingPlanningResponse = (
            offramper_agent.with_config(
                {
                    "metadata": {
                        "structured_response_config": {
                            "model_name": "InitialThinkingPlanningResponse",
                            "fields": [
                                ("reasoning", "reasoning"),
                                ("steps", "reasoning", "json"),
                            ],
                        }
                    }
                }
            ).invoke(input)
        )
        reasoning_messages = [
            AIMessage(
                content=initial_thinking_response.reasoning,
            )
        ]
        is_plannig = initial_thinking_response.plan_needed_response == "plan"
        if is_plannig:
            plan_steps = [
                PlanStepWithThought(step=step, reasoning=thought)
                for thought, step in initial_thinking_response.steps
            ]
            plan = PlanWithThought(
                thought=initial_thinking_response.reasoning,
                objective=state.objective,
                steps=plan_steps,
            )
            steps_message = AIMessage(
                content=plan.steps_as_string(),
            )
            reasoning_messages.append(steps_message)
        else:
            plan = None
        return {
            "plan_needed": initial_thinking_response.plan_needed_response == "plan",
            "original_plan": plan,
            "current_plan": plan,
            "reasoning": reasoning_messages,
            "combined": reasoning_messages,
        }

    async def direct_response(state: PlanExecuteAgentState):
        """Directly respond to the user as we have decided not to plan."""
        agent = get_tools_agent_executor(
            tools,
            llm,
            name,
            runbook,
            reasoning_level,
            interrupt_before_action,
            None,  # Subagent should not have a checkpointer
            None,
        )
        output = await agent.ainvoke(
            {
                "messages": state.messages,
                "reasoning": state.reasoning,
                "combined": state.combined,
            }
        )
        output_agent_state = AgentState(**output)
        return {
            "response": output_agent_state.messages[-1].content,
            "messages": output_agent_state.messages,
            "reasoning": output_agent_state.reasoning,
            "combined": output_agent_state.combined,
        }

    async def step_executor(state: PlanExecuteAgentState):
        """This node executes the next step and updates the executed plan with results.
        This node assumes reasoning_level == 0"""
        executor_agent = get_tools_agent_executor(
            tools,
            llm,
            name,
            runbook,
            reasoning_level,
            interrupt_before_action,
            None,  # Subagent should not have a checkpointer
            None,
            execute_template=STEP_EXECUTOR_PROMPT,
            reasoning_templates=STEP_REASONING_PROMPTS,
            retry_reasoning_templates=STEP_RETRY_REASONING_PROMPTS,
        )
        current_step = cast(PlanStep, state.current_plan.steps[0])

        # Isolate step executor from plan
        completed_plans = state.completed_plans or []
        if state.executed_plan:
            completed_plans.append(state.executed_plan)
        messages_for_executor = _get_executor_outcome_messages(completed_plans)
        messages_for_executor.append(AIMessage(content=current_step.step))
        output = await executor_agent.ainvoke({"messages": messages_for_executor})
        output_agent_state = AgentState(**output)

        new_messages = [
            m for m in output_agent_state.messages if m not in state.messages
        ]

        ## Update executed plan
        newly_completed_step = PastStep(
            original_step=current_step,
            outcome=new_messages,
        )
        executed_plan = state.executed_plan or ExecutedPlan(
            original_plan=state.original_plan, past_steps=[]
        )
        executed_plan.past_steps.append(newly_completed_step)

        return {
            "executed_plan": executed_plan,
            "messages": new_messages,
        }

    async def step_executor_thinker(state: PlanExecuteAgentState):
        """This node executes the next step and updates the executed plan with results.
        This node assumes reasoning_level > 0"""
        executor_agent = get_tools_agent_executor(
            tools,
            llm,
            name,
            runbook,
            reasoning_level,
            interrupt_before_action,
            None,  # Subagent should not have a checkpointer
            None,
            execute_template=STEP_EXECUTOR_PROMPT,
            reasoning_templates=STEP_REASONING_PROMPTS,
            retry_reasoning_templates=STEP_RETRY_REASONING_PROMPTS,
        )
        current_step = cast(PlanStepWithThought, state.current_plan.steps[0])

        # Isolate step executor from plan
        completed_plans = state.completed_plans or []
        if state.executed_plan:
            completed_plans.append(state.executed_plan)
        messages_for_executor = _get_executor_outcome_messages(completed_plans)
        combined_message = f"{current_step.reasoning} {current_step.step}"
        messages_for_executor.append(AIMessage(content=combined_message))

        output = await executor_agent.ainvoke({"combined": messages_for_executor})
        output_agent_state = AgentState(**output)

        new_combined_messages = [
            m for m in output_agent_state.combined if m not in state.combined
        ]
        new_messages = [
            m for m in output_agent_state.messages if m not in state.messages
        ]

        ## Update executed plan
        newly_completed_step = PastStep(
            original_step=current_step,
            outcome=new_combined_messages,
        )
        executed_plan = state.executed_plan or ExecutedPlanWithThought(
            original_plan=state.original_plan, past_steps=[]
        )
        executed_plan.past_steps.append(newly_completed_step)

        return {
            "executed_plan": executed_plan,
            "messages": new_messages,
            "reasoning": output_agent_state.reasoning,
            "combined": new_combined_messages,
        }

    async def replanner(state: PlanExecuteAgentState):
        """This node reviews the executed plan so far, compares it to the original plan,
        and updates the current plan with the next steps. This node assumes reasoning_level == 0"""
        prompt = REPLANNER_PROMPTS[reasoning_level]
        messages = _get_messages_for_replanner(state.messages)
        replanner_agent: Runnable[LanguageModelInput, ReplannerResponse] = (
            prompt
            | bind_tools(
                llm,
                [*tools, ReplannerResponse],
                tool_choice="ReplannerResponse",
            )
            | get_pydantic_output_parser(llm, ReplannerResponse)
        )
        last_step = state.current_plan.steps[0]
        remaining_steps = Plan(
            objective="", steps=state.current_plan.steps[1:]
        ).steps_as_string()

        replanner_input = {
            "name": name,
            "datetime": current_timestamp_with_iso_week_local(),
            "runbook": runbook,
            "messages": messages,
            "last_step": last_step.step,
            "remaining_steps": remaining_steps,
            "objective": state.objective,
        }
        replanner_response: ReplannerResponse = await replanner_agent.with_config(
            {
                "metadata": {
                    "structured_response_config": {
                        "model_name": "ReplannerResponse",
                        "fields": [
                            ("response", "message"),
                            ("new_steps", "message", "json"),
                            ("edge_case_reply", "message"),
                        ],
                    }
                }
            }
        ).ainvoke(replanner_input)

        if replanner_response.response_type == "update":
            plan_steps = [PlanStep(step=step) for step in replanner_response.new_steps]
            plan = Plan(objective=state.objective, steps=plan_steps)
            steps_message = AIMessage(content=plan.steps_as_string())
            return {
                "response_type": "update",
                "current_plan": plan,
                "messages": [steps_message],
            }
        elif replanner_response.response_type == "response-needed":
            completed_plan = CompletedPlan(
                original_plan=state.original_plan,
                past_steps=state.executed_plan.past_steps,
                output=replanner_response.response,
            )
            return {
                "completed_plans": [completed_plan],
                "response_type": replanner_response.response_type,
                "response": replanner_response.response,
                "messages": [AIMessage(content=replanner_response.response)],
            }
        elif replanner_response.response_type == "complete-as-is":
            completed_plan = CompletedPlan(
                original_plan=state.original_plan,
                past_steps=state.executed_plan.past_steps,
                output=state.messages[-1].content,
            )
            return {
                "completed_plans": [completed_plan],
                "response_type": replanner_response.response_type,
                "response": state.messages[-1].content,
            }
        elif replanner_response.response_type == "edge-case":
            response_messages = [
                AIMessage(content=replanner_response.edge_case_reply),
            ]
            return {
                "response_type": replanner_response.response_type,
                "response": replanner_response.edge_case_reply,
                "messages": response_messages,
            }

    async def replanner_thinker(state: PlanExecuteAgentState):
        """This node reviews the executed plan so far, compares it to the original plan,
        and updates the current plan with the next steps. This node assumes reasoning_level > 0"""
        prompt = REPLANNER_PROMPTS[reasoning_level]
        messages = _get_messages_for_replanner(state.combined)
        replanner_agent: Runnable[LanguageModelInput, ReplannerThinkerResponse] = (
            prompt
            | bind_tools(
                llm,
                [*tools, ReplannerThinkerResponse],
                tool_choice="ReplannerThinkerResponse",
            )
            | get_pydantic_output_parser(llm, ReplannerThinkerResponse)
        )
        last_step = state.current_plan.steps[0]
        remaining_steps = PlanWithThought(
            objective="", steps=state.current_plan.steps[1:], thought=""
        )

        replanner_input = {
            "name": name,
            "datetime": current_timestamp_with_iso_week_local(),
            "runbook": runbook,
            "messages": messages,
            "last_step": last_step.step,
            "remaining_steps": remaining_steps.steps_as_string(),
            "objective": state.objective,
        }
        replanner_response: ReplannerThinkerResponse = (
            await replanner_agent.with_config(
                {
                    "metadata": {
                        "structured_response_config": {
                            "model_name": "ReplannerThinkerResponse",
                            "fields": [
                                ("reasoning", "reasoning"),
                                ("response", "message", "string", "reasoning"),
                                ("new_steps", "reasoning", "json"),
                                ("edge_case_reply", "message", "string", "reasoning"),
                            ],
                        }
                    }
                }
            ).ainvoke(replanner_input)
        )

        reasoning_messages = [
            AIMessage(
                content=replanner_response.reasoning,
            )
        ]
        if replanner_response.response_type == "update":
            plan_steps = [
                PlanStepWithThought(step=step, reasoning=thought)
                for thought, step in replanner_response.new_steps
            ]
            plan = PlanWithThought(
                thought=replanner_response.reasoning,
                objective=state.objective,
                steps=plan_steps,
            )
            reasoning_messages.append(
                AIMessage(
                    content=plan.steps_as_string(),
                )
            )
            return {
                "response_type": replanner_response.response_type,
                "current_plan": plan,
                "reasoning": reasoning_messages,
                "combined": reasoning_messages,
            }
        elif replanner_response.response_type == "response-needed":
            completed_plan = CompletedPlanWithThought(
                original_plan=state.original_plan,
                past_steps=state.executed_plan.past_steps,
                thought=replanner_response.reasoning,
                output=replanner_response.response,
            )
            response_messages = [
                AIMessage(content=replanner_response.response),
            ]
            return {
                "completed_plans": [completed_plan],
                "response_type": replanner_response.response_type,
                "response": replanner_response.response,
                "messages": response_messages,
                "reasoning": reasoning_messages,
                "combined": reasoning_messages + response_messages,
            }
        elif replanner_response.response_type == "complete-as-is":
            completed_plan = CompletedPlanWithThought(
                original_plan=state.original_plan,
                past_steps=state.executed_plan.past_steps,
                thought=replanner_response.reasoning,
                output=state.messages[-1].content,
            )
            return {
                "completed_plans": [completed_plan],
                "response_type": replanner_response.response_type,
                "response": None,
                "reasoning": reasoning_messages,
                "combined": reasoning_messages,
            }
        elif replanner_response.response_type == "edge-case":
            response_messages = [
                AIMessage(content=replanner_response.edge_case_reply),
            ]
            return {
                "response_type": replanner_response.response_type,
                "response": replanner_response.edge_case_reply,
                "messages": response_messages,
                "reasoning": reasoning_messages,
                "combined": reasoning_messages + response_messages,
            }

    def should_offramp(state: PlanExecuteAgentState):
        if state.plan_needed:
            return "plan"
        else:
            return "direct-response"

    def should_end(state: PlanExecuteAgentState):
        if state.response_type != "update":
            return True
        else:
            return False

    ### Create the graph
    # Create a new workflow
    workflow = StateGraph(PlanExecuteAgentState)

    # add nodes
    workflow.add_node("start_node", objective_parser_and_state_reset)
    if reasoning_level > 0:
        workflow.add_node("offramper", offramper_thinker)
        workflow.add_node("step_executor", step_executor_thinker)
        workflow.add_node("replanner", replanner_thinker)
    else:
        workflow.add_node("offramper", offramper)
        workflow.add_node("step_executor", step_executor)
        workflow.add_node("replanner", replanner)
    workflow.add_node("direct_response", direct_response)
    workflow.add_node(FINISH_NODE_KEY, FINISH_NODE_ACTION)

    # Set entry
    workflow.set_entry_point("start_node")
    workflow.set_finish_point(FINISH_NODE_KEY)

    # Create edges
    workflow.add_edge("start_node", "offramper")
    workflow.add_conditional_edges(
        "offramper",
        should_offramp,
        {
            "direct-response": "direct_response",
            "plan": "step_executor",
        },
    )
    workflow.add_edge("direct_response", FINISH_NODE_KEY)
    workflow.add_edge("step_executor", "replanner")
    workflow.add_conditional_edges(
        "replanner", should_end, {True: FINISH_NODE_KEY, False: "step_executor"}
    )

    return workflow.compile(checkpointer=checkpoint)
