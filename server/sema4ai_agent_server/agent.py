from typing import Any, Dict, List, Mapping, Optional, Sequence

from langchain_core.messages import AnyMessage
from langchain_core.runnables import (
    ConfigurableField,
    RunnableBinding,
)
from langgraph.graph.message import Messages
from langgraph.pregel import Pregel

from sema4ai_agent_server.agent_types.planner_agent import get_plan_execute_agent
from sema4ai_agent_server.agent_types.tools_agent import get_tools_agent_executor
from sema4ai_agent_server.agent_types.vitality_ai_multi_agent import (
    vitality_ai_new as vitality_ai,
)
from sema4ai_agent_server.llms import get_chat_model
from sema4ai_agent_server.schema import (
    MODEL,
    ActionPackage,
    AgentReasoning,
    AzureGPT,
    OpenAIGPT,
    dummy_model,
)
from sema4ai_agent_server.storage.checkpoint import get_checkpointer
from sema4ai_agent_server.tools import (
    get_action_server,
    get_retrieval_tool,
)

DEFAULT_RUNBOOK = "You are a helpful agent."
DEFAULT_NAME = "Agent"


CHECKPOINTER = get_checkpointer()


def get_agent_executor(
    tools: list,
    model: MODEL,
    name: str,
    runbook: str,
    interrupt_before_action: bool,
    reasoning_level: AgentReasoning,
    knowledge_files: Optional[List[str]],
):
    llm = get_chat_model(model)
    return get_tools_agent_executor(
        tools,
        llm,
        name,
        runbook,
        reasoning_level,
        interrupt_before_action,
        CHECKPOINTER,
        knowledge_files,
    )


class ConfigurableAgent(RunnableBinding):
    action_packages: Sequence[ActionPackage]
    use_retrieval: bool = False
    model: Optional[MODEL] = None
    name: str = DEFAULT_NAME
    runbook: str = DEFAULT_RUNBOOK
    interrupt_before_action: bool = False
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    reasoning_level: AgentReasoning = AgentReasoning.DISABLED
    knowledge_files: Optional[List[str]] = None

    def __init__(
        self,
        *,
        action_packages: Sequence[ActionPackage],
        use_retrieval: bool = False,
        model: Optional[MODEL] = None,
        name: str = DEFAULT_NAME,
        runbook: str = DEFAULT_RUNBOOK,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        interrupt_before_action: bool = False,
        reasoning_level: AgentReasoning = AgentReasoning.DISABLED,
        knowledge_files: Optional[List[str]] = None,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        dynamic_headers = (
            {
                "x-invoked_by_assistant_id": agent_id,
                "x-invoked_on_behalf_of_user_id": user_id,
            }
            if agent_id and user_id
            else {}
        )
        tools = []
        for action_package in action_packages:
            action_package.additional_headers.update(dynamic_headers)
            tools.extend(get_action_server(action_package))
        if use_retrieval:
            if agent_id is None and thread_id is None:
                raise ValueError("agent_id or thread_id must be provided.")
            tools.append(get_retrieval_tool(agent_id, thread_id, model))

        _agent = get_agent_executor(
            tools,
            model,
            name,
            runbook,
            interrupt_before_action,
            reasoning_level,
            knowledge_files,
        )
        agent_executor = _agent.with_config({"recursion_limit": 50})
        super().__init__(
            action_packages=action_packages,
            use_retrieval=use_retrieval,
            model=model,
            runbook=runbook,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


class ConfigurablePlanExecute(RunnableBinding):
    action_packages: Sequence[ActionPackage]
    use_retrieval: bool = False
    model: Optional[MODEL] = None
    name: str = DEFAULT_NAME
    runbook: str = DEFAULT_RUNBOOK
    interrupt_before_action: bool = False
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    reasoning_level: AgentReasoning = AgentReasoning.DISABLED

    def __init__(
        self,
        *,
        action_packages: Sequence[ActionPackage],
        use_retrieval: bool = False,
        model: Optional[MODEL] = None,
        name: str = DEFAULT_NAME,
        runbook: str = DEFAULT_RUNBOOK,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        interrupt_before_action: bool = False,
        reasoning_level: AgentReasoning = AgentReasoning.DISABLED,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        dynamic_headers = (
            {
                "x-invoked_by_assistant_id": agent_id,
                "x-invoked_on_behalf_of_user_id": user_id,
            }
            if agent_id and user_id
            else {}
        )
        tools = []
        for action_package in action_packages:
            action_package.additional_headers.update(dynamic_headers)
            tools.extend(get_action_server(action_package))
        if use_retrieval:
            if agent_id is None and thread_id is None:
                raise ValueError("agent_id or thread_id must be provided.")
            tools.append(get_retrieval_tool(agent_id, thread_id, model))

        if type(model) not in (OpenAIGPT, AzureGPT):
            raise ValueError(f"Model {model} is not supported for PlanExecute.")
        llm = get_chat_model(model)
        _agent = get_plan_execute_agent(
            tools,
            llm,
            name,
            runbook,
            interrupt_before_action,
            reasoning_level,
            CHECKPOINTER,
        )
        agent_executor = _agent.with_config({"recursion_limit": 50})
        super().__init__(
            action_packages=action_packages,
            use_retrieval=use_retrieval,
            model=model,
            runbook=runbook,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


class ConfigurableVitalityMultiAgentPlanningHierarchicalArchitecture(RunnableBinding):
    action_packages: Sequence[ActionPackage]
    use_retrieval: bool = False
    model: Optional[MODEL] = None
    runbook: str = DEFAULT_RUNBOOK
    interrupt_before_action: bool = False
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None

    def __init__(
        self,
        *,
        action_packages: Sequence[ActionPackage],
        use_retrieval: bool = False,
        model: Optional[MODEL] = None,
        runbook: str = DEFAULT_RUNBOOK,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        interrupt_before_action: bool = False,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        dynamic_headers = (
            {
                "x-invoked_by_assistant_id": agent_id,
                "x-invoked_on_behalf_of_user_id": user_id,
            }
            if agent_id and user_id
            else {}
        )
        tools = []
        for action_package in action_packages:
            action_package.additional_headers.update(dynamic_headers)
            tools.extend(get_action_server(action_package))
        if use_retrieval:
            if agent_id is None and thread_id is None:
                raise ValueError("agent_id or thread_id must be provided.")
            tools.append(get_retrieval_tool(agent_id, thread_id, model))

        if type(model) not in (OpenAIGPT, AzureGPT):
            raise ValueError(f"Model {model} is not supported for PlanExecute.")
        llm = get_chat_model(model)
        _agent = vitality_ai.get_tools_agent_executor(
            tools, llm, interrupt_before_action, CHECKPOINTER
        )
        agent_executor = _agent.with_config({"recursion_limit": 50})
        super().__init__(
            action_packages=action_packages,
            use_retrieval=use_retrieval,
            model=model,
            runbook=runbook,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


plan_execute = (
    ConfigurablePlanExecute(
        action_packages=[],
        use_retrieval=False,
        model=dummy_model,
        name=DEFAULT_NAME,
        runbook=DEFAULT_RUNBOOK,
        agent_id=None,
        thread_id=None,
        user_id=None,
        reasoning_level=AgentReasoning.DISABLED,
    )
    .configurable_fields(
        model=ConfigurableField(id="model", name="Model"),
        name=ConfigurableField(id="name", name="Agent Name"),
        runbook=ConfigurableField(id="runbook", name="Instructions"),
        interrupt_before_action=ConfigurableField(
            id="interrupt_before_action",
            name="Tool Confirmation",
            description="If Yes, you'll be prompted to continue before each tool is executed.\nIf No, tools will be executed automatically by the agent.",
        ),
        agent_id=ConfigurableField(id="agent_id", name="Agent ID", is_shared=True),
        thread_id=ConfigurableField(id="thread_id", name="Thread ID", is_shared=True),
        user_id=ConfigurableField(id="user_id", name="User ID", is_shared=True),
        action_packages=ConfigurableField(id="action_packages", name="Action Packages"),
        use_retrieval=ConfigurableField(id="use_retrieval", name="Use Retrieval"),
        reasoning_level=ConfigurableField(
            id="reasoning_level",
            name="Reasoning Level",
            description="The level of reasoning the agent should use.",
        ),
    )
    .with_types(input_type=Dict[str, str], output_type=Sequence[AnyMessage])
)

multi_agent_hierarchical_planning = (
    ConfigurableVitalityMultiAgentPlanningHierarchicalArchitecture(
        action_packages=[],
        use_retrieval=False,
        model=dummy_model,
        runbook=DEFAULT_RUNBOOK,
        agent_id=None,
        thread_id=None,
        user_id=None,
    )
    .configurable_fields(
        model=ConfigurableField(id="model", name="Model"),
        runbook=ConfigurableField(id="runbook", name="Instructions"),
        interrupt_before_action=ConfigurableField(
            id="interrupt_before_action",
            name="Tool Confirmation",
            description="If Yes, you'll be prompted to continue before each tool is executed.\nIf No, tools will be executed automatically by the agent.",
        ),
        agent_id=ConfigurableField(id="agent_id", name="Agent ID", is_shared=True),
        thread_id=ConfigurableField(id="thread_id", name="Thread ID", is_shared=True),
        user_id=ConfigurableField(id="user_id", name="User ID", is_shared=True),
        action_packages=ConfigurableField(id="action_packages", name="Action Packages"),
        use_retrieval=ConfigurableField(id="use_retrieval", name="Use Retrieval"),
    )
    .with_types(input_type=Dict[str, str], output_type=Sequence[AnyMessage])
)

runnable_agent: Pregel = (
    ConfigurableAgent(
        model=dummy_model,
        action_packages=[],
        use_retrieval=False,
        name=DEFAULT_NAME,
        runbook=DEFAULT_RUNBOOK,
        agent_id=None,
        thread_id=None,
        user_id=None,
        reasoning_level=AgentReasoning.DISABLED,
        knowledge_files=None,
    )
    .configurable_fields(
        model=ConfigurableField(id="model", name="Model"),
        name=ConfigurableField(id="name", name="Agent Name"),
        runbook=ConfigurableField(id="runbook", name="Instructions"),
        interrupt_before_action=ConfigurableField(
            id="interrupt_before_action",
            name="Tool Confirmation",
            description="If Yes, you'll be prompted to continue before each tool is executed.\nIf No, tools will be executed automatically by the agent.",
        ),
        agent_id=ConfigurableField(id="agent_id", name="Agent ID", is_shared=True),
        thread_id=ConfigurableField(id="thread_id", name="Thread ID", is_shared=True),
        user_id=ConfigurableField(id="user_id", name="User ID", is_shared=True),
        action_packages=ConfigurableField(id="action_packages", name="Action Packages"),
        use_retrieval=ConfigurableField(id="use_retrieval", name="Use Retrieval"),
        reasoning_level=ConfigurableField(
            id="reasoning_level",
            name="Reasoning Level",
            description="The level of reasoning the agent should use.",
        ),
        knowledge_files=ConfigurableField(
            id="knowledge_files",
            name="Knowledge Files",
            description="List of knowledge files available to the agent.",
        ),
    )
    .configurable_alternatives(
        ConfigurableField(id="type", name="Bot Type"),
        default_key="agent",
        prefix_keys=True,
        plan_execute=plan_execute,
        multi_agent_hierarchical_planning=multi_agent_hierarchical_planning,
    )
    .with_types(input_type=Messages, output_type=Sequence[AnyMessage])
)

if __name__ == "__main__":
    import asyncio

    from langchain.schema.messages import HumanMessage

    async def run():
        async for m in runnable_agent.astream_events(
            HumanMessage(content="whats your name"),
            config={"configurable": {"user_id": "2", "thread_id": "test1"}},
            version="v1",
        ):
            print(m)

    asyncio.run(run())
