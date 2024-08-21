from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

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
    AzureGPT,
    OpenAIGPT4o,
    OpenAIGPT4Turbo,
    OpenAIGPT35Turbo,
    dummy_model,
)
from sema4ai_agent_server.storage.checkpoint import get_checkpointer
from sema4ai_agent_server.tools import (
    TOOLS,
    ActionServer,
    Arxiv,
    AvailableTools,
    Connery,
    DallE,
    DDGSearch,
    PressReleases,
    PubMed,
    Retrieval,
    SecFilings,
    Tavily,
    TavilyAnswer,
    Wikipedia,
    YouSearch,
    get_retrieval_tool,
)

Tool = Union[
    ActionServer,
    Connery,
    DDGSearch,
    Arxiv,
    YouSearch,
    SecFilings,
    PressReleases,
    PubMed,
    Wikipedia,
    Tavily,
    TavilyAnswer,
    Retrieval,
    DallE,
]


DEFAULT_RUNBOOK = "You are a helpful agent."
DEFAULT_NAME = "Agent"


CHECKPOINTER = get_checkpointer()


def get_agent_executor(
    tools: list,
    model: MODEL,
    name: str,
    runbook: str,
    interrupt_before_action: bool,
    reasoning_level: int,
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
    tools: Sequence[Tool]
    model: Optional[MODEL] = None
    name: str = DEFAULT_NAME
    runbook: str = DEFAULT_RUNBOOK
    interrupt_before_action: bool = False
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    reasoning_level: int = 0
    knowledge_files: Optional[List[str]] = None

    def __init__(
        self,
        *,
        tools: Sequence[Tool],
        model: Optional[MODEL] = None,
        name: str = DEFAULT_NAME,
        runbook: str = DEFAULT_RUNBOOK,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        interrupt_before_action: bool = False,
        reasoning_level: int = 0,
        knowledge_files: Optional[List[str]] = None,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        _tools = []
        for _tool in tools:
            if _tool["type"] == AvailableTools.RETRIEVAL:
                if agent_id is None and thread_id is None:
                    raise ValueError(
                        "Either agent_id or thread_id must be provided if Retrieval tool is used"
                    )
                _tools.append(get_retrieval_tool(agent_id, thread_id, model))
            else:
                tool_config = _tool.get("config", {})
                _returned_tools = TOOLS[_tool["type"]](**tool_config)
                if isinstance(_returned_tools, list):
                    _tools.extend(_returned_tools)
                else:
                    _tools.append(_returned_tools)

        _agent = get_agent_executor(
            _tools,
            model,
            name,
            runbook,
            interrupt_before_action,
            reasoning_level,
            knowledge_files,
        )
        agent_executor = _agent.with_config({"recursion_limit": 50})
        super().__init__(
            tools=tools,
            model=model,
            runbook=runbook,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


class ConfigurablePlanExecute(RunnableBinding):
    tools: Sequence[Tool]
    model: Optional[MODEL] = None
    name: str = DEFAULT_NAME
    runbook: str = DEFAULT_RUNBOOK
    interrupt_before_action: bool = False
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    reasoning_level: Optional[int] = None

    def __init__(
        self,
        *,
        tools: Sequence[Tool],
        model: Optional[MODEL] = None,
        name: str = DEFAULT_NAME,
        runbook: str = DEFAULT_RUNBOOK,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        interrupt_before_action: bool = False,
        reasoning_level: Optional[int] = None,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        _tools = []
        for _tool in tools:
            if _tool["type"] == AvailableTools.RETRIEVAL:
                if agent_id is None or thread_id is None:
                    raise ValueError(
                        "Both agent_id and thread_id must be provided if Retrieval tool is used"
                    )
                _tools.append(get_retrieval_tool(agent_id, thread_id, model))
            else:
                tool_config = _tool.get("config", {})
                _returned_tools = TOOLS[_tool["type"]](**tool_config)
                if isinstance(_returned_tools, list):
                    _tools.extend(_returned_tools)
                else:
                    _tools.append(_returned_tools)

        if type(model) not in (
            OpenAIGPT35Turbo,
            OpenAIGPT4Turbo,
            OpenAIGPT4o,
            AzureGPT,
        ):
            raise ValueError(f"Model {model} is not supported for PlanExecute.")
        llm = get_chat_model(model)
        _agent = get_plan_execute_agent(
            _tools,
            llm,
            name,
            runbook,
            interrupt_before_action,
            reasoning_level,
            CHECKPOINTER,
        )
        agent_executor = _agent.with_config({"recursion_limit": 50})
        super().__init__(
            tools=tools,
            model=model,
            runbook=runbook,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


class ConfigurableVitalityMultiAgentPlanningHierarchicalArchitecture(RunnableBinding):
    tools: Sequence[Tool]
    model: Optional[MODEL] = None
    runbook: str = DEFAULT_RUNBOOK
    interrupt_before_action: bool = False
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None

    def __init__(
        self,
        *,
        tools: Sequence[Tool],
        model: Optional[MODEL] = None,
        runbook: str = DEFAULT_RUNBOOK,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        interrupt_before_action: bool = False,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        _tools = []
        for _tool in tools:
            if _tool["type"] == AvailableTools.RETRIEVAL:
                if agent_id is None or thread_id is None:
                    raise ValueError(
                        "Both agent_id and thread_id must be provided if Retrieval tool is used"
                    )
                _tools.append(get_retrieval_tool(agent_id, thread_id, model))
            else:
                tool_config = _tool.get("config", {})
                _returned_tools = TOOLS[_tool["type"]](**tool_config)
                if isinstance(_returned_tools, list):
                    _tools.extend(_returned_tools)
                else:
                    _tools.append(_returned_tools)
        if type(model) not in (
            OpenAIGPT35Turbo,
            OpenAIGPT4Turbo,
            OpenAIGPT4o,
            AzureGPT,
        ):
            raise ValueError(f"Model {model} is not supported for PlanExecute.")
        llm = get_chat_model(model)
        _agent = vitality_ai.get_tools_agent_executor(
            _tools, llm, interrupt_before_action, CHECKPOINTER
        )
        agent_executor = _agent.with_config({"recursion_limit": 50})
        super().__init__(
            tools=tools,
            model=model,
            runbook=runbook,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


chat_plan_execute = (
    ConfigurablePlanExecute(
        tools=[],
        model=dummy_model,
        name=DEFAULT_NAME,
        runbook=DEFAULT_RUNBOOK,
        agent_id=None,
        thread_id=None,
        reasoning_level=0,
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
        tools=ConfigurableField(id="tools", name="Tools"),
        reasoning_level=ConfigurableField(
            id="reasoning_level",
            name="Reasoning Level",
            description="The level of reasoning the agent should use, 0 for no reasoning, 1 for succinct reasoning, 2 for verbose reasoning.",
        ),
    )
    .with_types(input_type=Dict[str, str], output_type=Sequence[AnyMessage])
)

multi_agent_hierarchical_planning = (
    ConfigurableVitalityMultiAgentPlanningHierarchicalArchitecture(
        tools=[],
        model=dummy_model,
        runbook=DEFAULT_RUNBOOK,
        agent_id=None,
        thread_id=None,
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
        tools=ConfigurableField(id="tools", name="Tools"),
    )
    .with_types(input_type=Dict[str, str], output_type=Sequence[AnyMessage])
)

runnable_agent: Pregel = (
    ConfigurableAgent(
        model=dummy_model,
        tools=[],
        name=DEFAULT_NAME,
        runbook=DEFAULT_RUNBOOK,
        agent_id=None,
        thread_id=None,
        reasoning_level=0,
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
        tools=ConfigurableField(id="tools", name="Tools"),
        reasoning_level=ConfigurableField(
            id="reasoning_level",
            name="Reasoning Level",
            description="The level of reasoning the agent should use, 0 for no reasoning, 1 for succinct reasoning, 2 for verbose reasoning.",
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
        chat_plan_execute=chat_plan_execute,
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
