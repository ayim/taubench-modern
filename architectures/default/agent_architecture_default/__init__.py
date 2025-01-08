from typing import Type

from agent_server_types import (
    DEFAULT_ARCHITECTURE,
    AzureGPT,
    OpenAIGPT,
)
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph
from pydantic import Field

from agent_architecture import (
    FINISH_NODE_ACTION,
    FINISH_NODE_KEY,
    AgentArchitectureBase,
    ArchitectureNameConst,
    PredefinedChatPromptTemplateType,
    SupportedModelsConst,
)
from agent_architecture.common.knowledge import format_knowledge_files
from agent_architecture.common.nodes import CallToolNodeMixin
from agent_architecture.common.state import AgentState
from agent_architecture.common.tool_calling import bind_tools
from agent_architecture.common.utilities import (
    current_timestamp_with_iso_week_local,
    is_reasoning,
)

from .prompts import (
    ExecutePromptTemplate,
    ReasoningPromptTemplate,
    ToolsAgentInputSpec,
)

__version__ = "1.0.2"

# Define all possible LLM types
SUPPORTED_MODELS: list[Type] = [OpenAIGPT, AzureGPT]
ARCHITECTURE_NAME = DEFAULT_ARCHITECTURE


class OpenaiToolsAgentArchitecture(CallToolNodeMixin, AgentArchitectureBase):
    """An agent architecture for agents that use tools. This is the
    most basic agent architecture and is bundled with the agent architecture
    framework and is always available to the agent server. It only supports
    OpenAI and Azure OpenAI models.
    """

    supported_models: SupportedModelsConst = SUPPORTED_MODELS

    architecture_name: ArchitectureNameConst = "agent_architecture_openai_tools"

    execute_template: PredefinedChatPromptTemplateType = Field(
        ExecutePromptTemplate,
        description="The chat prompt template used for the execute "
        "nodes in the agent graph.",
    )
    reasoning_template: PredefinedChatPromptTemplateType = Field(
        ReasoningPromptTemplate,
        description="The chat prompt template used for the reasoning nodes "
        "in the agent graph.",
    )

    def create_graph(self, **kwargs) -> StateGraph:
        runbook = self.agent.runbook.get_secret_value()

        if self.tools:
            llm_with_tools = bind_tools(self.chat_model, self.tools)
            llm_with_tools_no_choice = bind_tools(
                self.chat_model, self.tools, tool_choice="none"
            )
        else:
            llm_with_tools = self.chat_model
            llm_with_tools_no_choice = self.chat_model

        executor_agent = self.execute_template(self.agent) | llm_with_tools
        if is_reasoning(self.agent):
            reasoning_agent = (
                self.reasoning_template(self.agent) | llm_with_tools_no_choice
            ).with_config({"metadata": {"reasoning": True}})

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
                last_human_message = state.messages[-1]
                combined_messages = state.combined + [last_human_message]
            else:
                combined_messages = state.combined
            response = await reasoning_agent.ainvoke(
                ToolsAgentInputSpec(
                    agent_name=self.agent.name,
                    current_datetime=current_timestamp_with_iso_week_local(),
                    knowledge_files=format_knowledge_files(self.knowledge_files),
                    runbook=runbook,
                    messages=combined_messages,
                )
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
            if is_reasoning(self.agent):
                associated_reasoning_id = (
                    state.reasoning[-1].id if state.reasoning else None
                )
                response = await executor_agent.with_config(
                    {"metadata": {"associated_reasoning": associated_reasoning_id}}
                ).ainvoke(
                    ToolsAgentInputSpec(
                        agent_name=self.agent.name,
                        current_datetime=current_timestamp_with_iso_week_local(),
                        knowledge_files=format_knowledge_files(self.knowledge_files),
                        runbook=runbook,
                        messages=state.combined,
                    )
                )
            else:
                response = await executor_agent.ainvoke(
                    ToolsAgentInputSpec(
                        agent_name=self.agent.name,
                        current_datetime=current_timestamp_with_iso_week_local(),
                        knowledge_files=format_knowledge_files(self.knowledge_files),
                        runbook=runbook,
                        messages=state.messages,
                    )
                )
            if is_reasoning(self.agent):
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

        workflow = StateGraph(AgentState)

        # Define the two nodes we will cycle between
        workflow.add_node("agent", agent)
        workflow.add_node("action", self.call_tool)
        if is_reasoning(self.agent):
            workflow.add_node("reason", reasoning)
        workflow.add_node(FINISH_NODE_KEY, FINISH_NODE_ACTION)

        # entrypoint and finishpoint
        if is_reasoning(self.agent):
            workflow.set_entry_point("reason")
        else:
            workflow.set_entry_point("agent")
        workflow.set_finish_point(FINISH_NODE_KEY)

        if is_reasoning(self.agent):
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

        if is_reasoning(self.agent):
            workflow.add_edge("action", "reason")
        else:
            workflow.add_edge("action", "agent")

        return workflow


__all__ = ["OpenaiToolsAgentArchitecture", "SUPPORTED_MODELS", "ARCHITECTURE_NAME"]
