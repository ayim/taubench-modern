from typing import Annotated, List, Optional, cast

from langchain.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    FunctionMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langgraph.checkpoint import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolExecutor, ToolInvocation

from sema4ai_agent_server.agent_types.constants import (
    FINISH_NODE_ACTION,
    FINISH_NODE_KEY,
)
from sema4ai_agent_server.message_types import LiberalToolMessage
from sema4ai_agent_server.schema import AgentReasoning
from sema4ai_agent_server.utils import current_timestamp_with_iso_week_local

# Define all possible LLM types
# TODO: Support Fireworks by changing dependency to langchain_fireworks instead of the cummunity version
AGENT_TYPES = (AzureChatOpenAI, ChatOpenAI, ChatAnthropic, ChatVertexAI)

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
EXECUTE_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(BASE_PROMPT_MESSAGES)
# Keys off of the verbose levels in the configurable.
REASONING_PROMPT_TEMPLATES = {
    # Consider adding "Respond with at most 2 sentances." in the level 1 prompt if it's still too verbose
    AgentReasoning.ENABLED: ChatPromptTemplate.from_messages(
        BASE_PROMPT_MESSAGES
        + [
            (
                "system",
                "Think about your next response based on the conversation so far and succinctly "
                "explain why you are thinking to respond in this way. Focus on the most important aspects "
                "of your reasoning. ONLY PROVIDE REASONING.",
            )
        ]
    ),
    AgentReasoning.VERBOSE: ChatPromptTemplate.from_messages(
        BASE_PROMPT_MESSAGES
        + [
            (
                "system",
                "Think about your next response based on the conversation so far and explain "
                "why you are thinking to respond in this way. If you are thinking about calling tools, "
                "also explain what parameters you are thinking of using and why. ONLY PROVIDE REASONING.",
            )
        ]
    ),
}


class AgentState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    reasoning: Annotated[list[BaseMessage], add_messages]
    combined: Annotated[list[BaseMessage], add_messages]


def get_tools_agent_executor(
    tools: list[BaseTool],
    llm: BaseChatModel,
    name: str,
    runbook: str,
    reasoning_level: AgentReasoning,
    interrupt_before_action: bool,
    checkpoint: BaseCheckpointSaver,
    knowledge_files: Optional[List[str]],
    *,
    execute_template: ChatPromptTemplate = EXECUTE_PROMPT_TEMPLATE,
    reasoning_templates: dict[
        AgentReasoning, ChatPromptTemplate
    ] = REASONING_PROMPT_TEMPLATES,
):
    if not isinstance(llm, AGENT_TYPES):
        raise ValueError(
            f"Expected an LLM with one of type {AGENT_TYPES}, got {type(llm)}."
        )

    def _get_messages(messages):
        msgs = []
        for m in messages:
            if isinstance(m, LiberalToolMessage):
                _dict = m.dict()
                _dict["content"] = str(_dict["content"])
                m_c = ToolMessage(**_dict)
                msgs.append(m_c)
            elif isinstance(m, FunctionMessage):
                # anthropic doesn't like function messages
                msgs.append(HumanMessage(content=str(m.content)))
            else:
                msgs.append(m)

        return msgs

    def format_knowledge_files(files):
        if files:
            file_list = "\n".join(f"- {file}" for file in files)
            return f"You have access to the following knowledge files:\n{file_list}"
        return ""

    if tools:
        llm_with_tools = llm.bind_tools(tools)
        llm_with_tools_no_choice = llm.bind_tools(tools, tool_choice="none")
    else:
        llm_with_tools = llm
        llm_with_tools_no_choice = llm
    tool_executor = ToolExecutor(tools)

    executor_agent = execute_template | llm_with_tools
    if reasoning_level != AgentReasoning.DISABLED:
        reasoning_agent = (
            reasoning_templates[reasoning_level] | llm_with_tools_no_choice
        )

    async def reasoning(state: AgentState):
        # setup combined message thread:
        fresh_state = False
        last_human_message = None
        if not state.combined:
            fresh_state = True
            combined_messages = state.messages
        elif len(state.messages) > 0 and isinstance(state.messages[-1], HumanMessage):
            # Add the last human message to the combined thread before calling LLM. This won't work
            # with Anthropic if function messages were involved as the _get_messages function will
            # convert them to HumanMessages.
            last_human_message = state.messages[-1]
            combined_messages = state.combined + [last_human_message]
        else:
            combined_messages = state.combined
        response = await reasoning_agent.with_config(
            {"metadata": {"reasoning": True}}
        ).ainvoke(
            {
                "agent_name": name,
                "current_datetime": current_timestamp_with_iso_week_local(),
                "knowledge_files": format_knowledge_files(knowledge_files),
                "runbook": runbook,
                "messages": _get_messages(combined_messages),
            }
        )
        if fresh_state:
            return {"reasoning": [response], "combined": combined_messages + [response]}
        elif last_human_message:
            return {"reasoning": [response], "combined": [last_human_message, response]}
        else:
            return {"reasoning": [response], "combined": [response]}

    async def agent(state: AgentState):
        if reasoning_level != AgentReasoning.DISABLED:
            associated_reasoning_id = (
                state.reasoning[-1].id if state.reasoning else None
            )
            response = await executor_agent.with_config(
                {"metadata": {"associated_reasoning": associated_reasoning_id}}
            ).ainvoke(
                {
                    "agent_name": name,
                    "current_datetime": current_timestamp_with_iso_week_local(),
                    "knowledge_files": format_knowledge_files(knowledge_files),
                    "runbook": runbook,
                    "messages": _get_messages(state.combined),
                }
            )
        else:
            response = await executor_agent.ainvoke(
                {
                    "agent_name": name,
                    "current_datetime": current_timestamp_with_iso_week_local(),
                    "knowledge_files": format_knowledge_files(knowledge_files),
                    "runbook": runbook,
                    "messages": _get_messages(state.messages),
                }
            )
        if reasoning_level != AgentReasoning.DISABLED:
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
        responses = await tool_executor.abatch(actions)
        # We use the response to create a ToolMessage
        tool_messages = [
            LiberalToolMessage(
                tool_call_id=tool_call["id"],
                name=tool_call["name"],
                content=response,
            )
            for tool_call, response in zip(last_message.tool_calls, responses)
        ]
        if reasoning_level != AgentReasoning.DISABLED:
            return {"messages": tool_messages, "combined": tool_messages}
        else:
            return {"messages": tool_messages}

    workflow = StateGraph(AgentState)

    # Define the two nodes we will cycle between
    workflow.add_node("agent", agent)
    workflow.add_node("action", call_tool)
    if reasoning_level != AgentReasoning.DISABLED:
        workflow.add_node("reason", reasoning)
    workflow.add_node(FINISH_NODE_KEY, FINISH_NODE_ACTION)

    # Set the entrypoint as `agent`
    # This means that this node is the first one called
    if reasoning_level != AgentReasoning.DISABLED:
        workflow.set_entry_point("reason")
    else:
        workflow.set_entry_point("agent")
    workflow.set_finish_point(FINISH_NODE_KEY)

    if reasoning_level != AgentReasoning.DISABLED:
        workflow.add_edge("reason", "agent")
    # We now add a conditional edge
    workflow.add_conditional_edges(
        # First, we define the start node. We use `agent`.
        # This means these are the edges taken after the `agent` node is called.
        "agent",
        # Next, we pass in the function that will determine which node is called next.
        should_continue,
        # Finally we pass in a mapping.
        # The keys are strings, and the values are other nodes.
        # END is a special node marking that the graph should finish.
        # What will happen is we will call `should_continue`, and then the output of that
        # will be matched against the keys in this mapping.
        # Based on which one it matches, that node will then be called.
        {
            # If `tools`, then we call the tool node.
            "continue": "action",
            # Otherwise we finish.
            "end": FINISH_NODE_KEY,
        },
    )

    # We now add a normal edge from `tools` to `agent`.
    # This means that after `tools` is called, `agent` node is called next.
    if reasoning_level != AgentReasoning.DISABLED:
        workflow.add_edge("action", "reason")
    else:
        workflow.add_edge("action", "agent")

    # Finally, we compile it!
    # This compiles it into a LangChain Runnable,
    # meaning you can use it as you would any other runnable
    return workflow.compile(
        checkpointer=checkpoint,
        interrupt_before=["action"] if interrupt_before_action else None,
    )
