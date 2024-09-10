from typing import Any, Dict, List, Mapping, Optional, Sequence

from langchain_core.messages import AnyMessage
from langchain_core.runnables import (
    ConfigurableField,
    Runnable,
    RunnableBinding,
)
from langgraph.graph.message import Messages
from langgraph.pregel import Pregel

from sema4ai_agent_server.agent_types.planner_agent import PlanExecuteAgentFactory
from sema4ai_agent_server.agent_types.tools_agent import ToolsAgentFactory
from sema4ai_agent_server.agent_types.vitality_ai_multi_agent import (
    vitality_ai_new as vitality_ai,
)
from sema4ai_agent_server.llms import get_chat_model
from sema4ai_agent_server.schema import (
    MODEL,
    ActionPackage,
    Agent,
    AgentArchitecture,
    AgentReasoning,
    AzureGPT,
    OpenAIGPT,
    Thread,
    User,
    dummy_agent,
    dummy_model,
)
from sema4ai_agent_server.storage.checkpoint import get_checkpointer
from sema4ai_agent_server.tools import (
    get_retrieval_tool,
    get_tools_from_action_packages,
)

DEFAULT_RUNBOOK = "You are a helpful agent."
DEFAULT_NAME = "Agent"


CHECKPOINTER = get_checkpointer()


# TODO: Each of these Configurables should be in their own file.
class ConfigurableAgent(RunnableBinding):
    agent: Optional[Agent] = None
    thread: Optional[Thread] = None
    use_retrieval: bool = False
    interrupt_before_action: bool = False
    knowledge_files: Optional[List[str]] = None

    def __init__(
        self,
        *,
        agent: Agent = None,
        thread: Optional[Thread] = None,
        use_retrieval: bool = False,
        interrupt_before_action: bool = False,
        knowledge_files: Optional[List[str]] = None,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        agent_factory = ToolsAgentFactory(
            agent=agent,
            thread=thread,  # TODO: thread may be None
            use_retrieval=use_retrieval,
            interrupt_before_action=interrupt_before_action,
            knowledge_files=knowledge_files,
        )
        agent_executor = agent_factory.compile_agent(**others)
        # TODO: I'm not sure these other params are actually needed on the Runnable
        super().__init__(
            # action_packages=action_packages,
            agent=agent,
            thread=thread,
            use_retrieval=use_retrieval,
            interrupt_before_action=interrupt_before_action,
            knowledge_files=knowledge_files,
            # model=model,
            # runbook=runbook,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


class ConfigurablePlanExecute(RunnableBinding):
    agent: Optional[Agent]
    thread: Optional[Thread] = None
    use_retrieval: bool = False
    interrupt_before_action: bool = False
    knowledge_files: Optional[List[str]] = None

    def __init__(
        self,
        *,
        agent: Optional[Agent] = None,
        thread: Optional[Thread] = None,
        use_retrieval: bool = False,
        interrupt_before_action: bool = False,
        knowledge_files: Optional[List[str]] = None,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        agent_factory = PlanExecuteAgentFactory(
            agent=agent,
            thread=thread,
            use_retrieval=use_retrieval,
            interrupt_before_action=interrupt_before_action,
            knowledge_files=knowledge_files,
        )
        agent_executor = agent_factory.compile_agent(**others)
        super().__init__(
            # action_packages=action_packages,
            agent=agent,
            thread=thread,
            use_retrieval=use_retrieval,
            interrupt_before_action=interrupt_before_action,
            knowledge_files=knowledge_files,
            # model=model,
            # runbook=runbook,
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
    user: Optional[User] = None

    def __init__(
        self,
        *,
        action_packages: Sequence[ActionPackage],
        use_retrieval: bool = False,
        model: Optional[MODEL] = None,
        runbook: str = DEFAULT_RUNBOOK,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        user: Optional[User] = None,
        interrupt_before_action: bool = False,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        dynamic_headers = (
            {
                "x-invoked_by_assistant_id": agent_id,
                "x-invoked_on_behalf_of_user_id": user.cr_user_id,
                "x-invoked_for_thread_id": thread_id,
            }
            if agent_id and user and thread_id
            else {}
        )
        tools = get_tools_from_action_packages(action_packages, dynamic_headers)
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
        agent_executor = _agent.with_config({"recursion_limit": 100})
        super().__init__(
            action_packages=action_packages,
            use_retrieval=use_retrieval,
            model=model,
            runbook=runbook,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


# TODO: This has not been updated to use factory
plan_execute = (
    ConfigurablePlanExecute(
        agent=dummy_plan_execute_agent,
        thread=None,
        use_retrieval=False,
        interrupt_before_action=False,
        knowledge_files=None,
    )
    .configurable_fields(
        agent=ConfigurableField(id="agent", name="Agent", is_shared=True),
        thread=ConfigurableField(id="thread", name="Thread", is_shared=True),
        use_retrieval=ConfigurableField(id="use_retrieval", name="Use Retrieval"),
        interrupt_before_action=ConfigurableField(
            id="interrupt_before_action",
            name="Tool Confirmation",
            description="If Yes, you'll be prompted to continue before each tool is executed.\nIf No, tools will be executed automatically by the agent.",
        ),
        knowledge_files=ConfigurableField(
            id="knowledge_files",
            name="Knowledge Files",
            description="List of knowledge files available to the agent.",
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
        user=None,
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
        user=ConfigurableField(id="user", name="User", is_shared=True),
        action_packages=ConfigurableField(id="action_packages", name="Action Packages"),
        use_retrieval=ConfigurableField(id="use_retrieval", name="Use Retrieval"),
    )
    .with_types(input_type=Dict[str, str], output_type=Sequence[AnyMessage])
)

# Add your architecture here.
ARCHITECTURE_CONFIGS: Dict[AgentArchitecture, Runnable] = {
    AgentArchitecture.PLAN_EXECUTE: plan_execute,
    AgentArchitecture.MULTI_AGENT_HIERARCHICAL_PLANNING: multi_agent_hierarchical_planning,
}

# Completeness check
missing_architectures = (
    set(AgentArchitecture)
    - set(ARCHITECTURE_CONFIGS.keys())
    - {AgentArchitecture.AGENT}
)
if missing_architectures:
    raise ValueError(
        f"Missing configurations for architectures: {missing_architectures}"
    )

alternatives = {
    arch.value: ARCHITECTURE_CONFIGS[arch]
    for arch in AgentArchitecture
    if arch != AgentArchitecture.AGENT
}

runnable_agent: Pregel = (
    ConfigurableAgent(
        agent=dummy_agent,
        thread=None,
        use_retrieval=False,
        interrupt_before_action=False,
        knowledge_files=None,
    )
    .configurable_fields(
        agent=ConfigurableField(id="agent", name="Agent", is_shared=True),
        thread=ConfigurableField(id="thread", name="Thread", is_shared=True),
        use_retrieval=ConfigurableField(id="use_retrieval", name="Use Retrieval"),
        interrupt_before_action=ConfigurableField(
            id="interrupt_before_action",
            name="Tool Confirmation",
            description="If Yes, you'll be prompted to continue before each tool is executed.\nIf No, tools will be executed automatically by the agent.",
        ),
        knowledge_files=ConfigurableField(
            id="knowledge_files",
            name="Knowledge Files",
            description="List of knowledge files available to the agent.",
        ),
    )
    .configurable_alternatives(
        ConfigurableField(id="type", name="Bot Type"),
        default_key=AgentArchitecture.AGENT.value,
        prefix_keys=True,
        **alternatives,
    )
    .with_types(input_type=Messages, output_type=Sequence[AnyMessage])
)
