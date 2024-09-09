import time
from typing import Annotated, Callable, List, Optional, cast

from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolExecutor, ToolInvocation
from opentelemetry import metrics
from pydantic import BaseModel, Field

from sema4ai_agent_server.agent_types.constants import (
    FINISH_NODE_ACTION,
    FINISH_NODE_KEY,
)
from sema4ai_agent_server.agent_types.factory import (
    AgentFactory,
    PredefinedChatPromptTemplate,
)
from sema4ai_agent_server.agent_types.utils import (
    bind_tools,
    format_knowledge_files,
    get_messages,
    is_claude,
)
from sema4ai_agent_server.message_types import ToolMessage
from sema4ai_agent_server.otel import otel_is_enabled
from sema4ai_agent_server.schema import (
    Agent,
    AgentArchitecture,
    AgentReasoning,
)
from sema4ai_agent_server.utils import current_timestamp_with_iso_week_local

# Define all possible LLM types
# TODO: Support Fireworks by changing dependency to langchain_fireworks instead of the cummunity version
SUPPORTED_MODELS = (
    AzureChatOpenAI,
    ChatOpenAI,
    ChatAnthropic,
    ChatVertexAI,
    ChatBedrockConverse,
)

BASE_PROMPT_MESSAGES = [
    (
        "system",
        """You are an assistant with the following name: {agent_name}.
The current date and time is: {current_datetime}.
{knowledge_files}
Your instructions are:
{runbook}""",
    ),
    ("placeholder", "{messages}"),
]


class ExecutePromptTemplate(PredefinedChatPromptTemplate):
    """The base prompt template used for the execute nodes in the agent graph.

    Invocation requires the following input dict:

    ```python
    {
        "agent_name": str,
        "current_datetime": str,
        "knowledge_files": str,
        "runbook": str,
        "messages": list[BaseMessage],
    }
    ```
    """

    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        return BASE_PROMPT_MESSAGES


class ReasoningPromptTemplate(PredefinedChatPromptTemplate):
    """The base prompt template used for the reasoning nodes in the agent graph.

    Invocation requires the following input dict:

    ```python
    {
        "agent_name": str,
        "current_datetime": str,
        "knowledge_files": str,
        "runbook": str,
        "messages": list[BaseMessage],
    }
    ```
    """

    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        reasoning_level = agent.reasoning or AgentReasoning.ENABLED

        match reasoning_level:
            case AgentReasoning.ENABLED:
                reasoning_addendum = """
Focus on the most important aspects of your reasoning.
""".strip()
            case AgentReasoning.VERBOSE:
                reasoning_addendum = """
If you are thinking about calling tools, also explain what parameters you are \
thinking of using and why.
        """.strip()

        prompt = f"""
Think about your next response based on the conversation so far and \
{"succinctly " if reasoning_level == AgentReasoning.ENABLED else ""}explain why you are thinking \
to respond in this way. {reasoning_addendum} ONLY PROVIDE REASONING.
        """.strip()

        return BASE_PROMPT_MESSAGES + [
            ("human" if is_claude(agent.model) else "system", prompt)
        ]


CONTINUE = "Continue"

if otel_is_enabled():
    meter = metrics.get_meter(__name__)
    action_success_counter = meter.create_counter(
        name="sema4ai.agent_server.action_server.success",
        description="Number of successful action server calls",
    )
    action_failure_counter = meter.create_counter(
        name="sema4ai.agent_server.action_server.failure",
        description="Number of failed action server calls",
    )
    action_latency_histogram = meter.create_histogram(
        name="sema4ai.agent_server.action_server.response_duration",
        description="The duration of action server requests in milliseconds",
        unit="ms",
    )


class AgentState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    reasoning: Annotated[list[BaseMessage], add_messages]
    combined: Annotated[list[BaseMessage], add_messages]


class ToolsAgentFactory(AgentFactory):
    """A factory used to create agents that can call tools.

    This factory is used to create agents that can call tools and reason
    about their responses.
    """

    architecture = AgentArchitecture.AGENT
    supported_models = SUPPORTED_MODELS

    execute_template: type[ChatPromptTemplate] = Field(
        ExecutePromptTemplate,
        description="The chat prompt template used for the execute "
        "nodes in the agent graph.",
    )
    reasoning_template: type[ChatPromptTemplate] = Field(
        ReasoningPromptTemplate,
        description="The chat prompt template used for the reasoning nodes "
        "in the agent graph.",
    )

    def create_agent(
        self,
    ) -> CompiledGraph:
        tools = self.get_tools()
        llm = self.get_chat_model()
        if tools:
            llm_with_tools = bind_tools(llm, tools)
            llm_with_tools_no_choice = bind_tools(llm, tools, tool_choice="none")
        else:
            llm_with_tools = llm
            llm_with_tools_no_choice = llm
        tool_executor = ToolExecutor(tools)

        executor_agent = self.execute_template(self.agent) | llm_with_tools
        if self.agent.advanced_config.reasoning != AgentReasoning.DISABLED:
            reasoning_agent = (
                self.reasoning_template(self.agent) | llm_with_tools_no_choice
            )

        async def reasoning(state: AgentState):
            # setup combined message thread:
            fresh_state = False
            last_human_message = None
            if not state.combined:
                fresh_state = True
                combined_messages = state.messages
            elif len(state.messages) > 0 and isinstance(
                state.messages[-1], HumanMessage
            ):
                # Add the last human message to the combined thread before calling LLM. This won't work
                # with Anthropic if function messages were involved as the _get_messages function will
                # convert them to HumanMessages.
                last_human_message = state.messages[-1]
                combined_messages = state.combined + [last_human_message]
            else:
                combined_messages = state.combined
            if is_claude(self.agent.model) and isinstance(
                combined_messages[-1], ToolMessage
            ):
                # If the last message is a tool message, we need to inject an AI message.
                combined_messages += [AIMessage(content="Acknowledged")]
            response = await reasoning_agent.with_config(
                {"metadata": {"reasoning": True}}
            ).ainvoke(
                {
                    "agent_name": self.agent.name,
                    "current_datetime": current_timestamp_with_iso_week_local(),
                    "knowledge_files": format_knowledge_files(self.knowledge_files),
                    "runbook": self.agent.runbook,
                    "messages": get_messages(combined_messages),
                }
            )
            if fresh_state:
                return {
                    "reasoning": [response],
                    "combined": combined_messages + [response],
                }
            elif last_human_message:
                return {
                    "reasoning": [response],
                    "combined": [last_human_message, response],
                }
            else:
                return {"reasoning": [response], "combined": [response]}

        async def agent(state: AgentState):
            if self.agent.advanced_config.reasoning != AgentReasoning.DISABLED:
                associated_reasoning_id = (
                    state.reasoning[-1].id if state.reasoning else None
                )
                if (
                    is_claude(self.agent.model)
                    and state.combined[-1].id == associated_reasoning_id
                ):
                    # If the last message in the combined thread is the last reasoning message, then we
                    # must inject a Human message to adhere to the Claude mode requirement.
                    state.combined += [HumanMessage(content=CONTINUE)]
                response = await executor_agent.with_config(
                    {"metadata": {"associated_reasoning": associated_reasoning_id}}
                ).ainvoke(
                    {
                        "agent_name": self.agent.name,
                        "current_datetime": current_timestamp_with_iso_week_local(),
                        "knowledge_files": format_knowledge_files(self.knowledge_files),
                        "runbook": self.agent.runbook,
                        "messages": get_messages(state.combined),
                    }
                )
            else:
                response = await executor_agent.ainvoke(
                    {
                        "agent_name": self.agent.name,
                        "current_datetime": current_timestamp_with_iso_week_local(),
                        "knowledge_files": format_knowledge_files(self.knowledge_files),
                        "runbook": self.agent.runbook,
                        "messages": get_messages(state.messages),
                    }
                )
            if self.agent.advanced_config.reasoning != AgentReasoning.DISABLED:
                return {"messages": [response], "combined": [response]}
            else:
                return {"messages": [response]}

        # Define the function that determines whether to continue or not
        def should_continue(state: AgentState):
            last_message = state.messages[-1]
            # If there is no function call, then we finish
            if not last_message.tool_calls:
                return "end"
            # Otherwise if there is, we continue
            else:
                return "continue"

        # Define the function to execute tools
        async def call_tool(state: AgentState):
            actions: list[ToolInvocation] = []
            # Based on the continue condition
            # we know the last message involves a function call
            last_message = cast(AIMessage, state.messages[-1])
            for tool_call in last_message.tool_calls:
                # We construct a ToolInvocation from the function_call
                actions.append(
                    ToolInvocation(
                        tool=tool_call["name"],
                        tool_input=tool_call["args"],
                    )
                )
            # We call the tool_executor and get back a response
            start_time = time.time()
            responses = await tool_executor.abatch(actions)
            end_time = time.time()
            if otel_is_enabled():
                # Since actions are batched, we approximate the latency per action
                action_latency_histogram.record(
                    round((end_time - start_time) * 1000 / len(actions))
                )
            # We use the response to create a ToolMessage
            tool_messages = []
            for tool_call, response in zip(last_message.tool_calls, responses):
                tool_messages.append(
                    ToolMessage(
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"],
                        content=str(response),
                    )
                )
                if otel_is_enabled():
                    if response == '"This action failed."':
                        action_failure_counter.add(1)
                    else:
                        action_success_counter.add(1)
            if self.agent.advanced_config.reasoning != AgentReasoning.DISABLED:
                return {"messages": tool_messages, "combined": tool_messages}
            else:
                return {"messages": tool_messages}

        workflow = StateGraph(AgentState)

        # Define the two nodes we will cycle between
        workflow.add_node("agent", agent)
        workflow.add_node("action", call_tool)
        if self.agent.advanced_config.reasoning != AgentReasoning.DISABLED:
            workflow.add_node("reason", reasoning)
        workflow.add_node(FINISH_NODE_KEY, FINISH_NODE_ACTION)

        # entrypoint and finishpoint
        if self.agent.advanced_config.reasoning != AgentReasoning.DISABLED:
            workflow.set_entry_point("reason")
        else:
            workflow.set_entry_point("agent")
        workflow.set_finish_point(FINISH_NODE_KEY)

        if self.agent.advanced_config.reasoning != AgentReasoning.DISABLED:
            workflow.add_edge("reason", "agent")

        # Conditional edges
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "continue": "action",
                "end": FINISH_NODE_KEY,
            },
        )

        if self.agent.advanced_config.reasoning != AgentReasoning.DISABLED:
            workflow.add_edge("action", "reason")
        else:
            workflow.add_edge("action", "agent")

        return workflow.compile(
            checkpointer=self.checkpoint,
            interrupt_before=["action"] if self.interrupt_before_action else None,
        ).with_config({"recursion_limit": self.agent.advanced_config.recursion_limit})
