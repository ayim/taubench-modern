from typing import Any, Mapping, Sequence

from agent_server_types import (
    Agent,
    Thread,
    dummy_agent,
)
from langchain_core.messages import AnyMessage
from langchain_core.runnables import (
    ConfigurableField,
    RunnableBinding,
)
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.message import Messages
from langgraph.pregel import Pregel
from pydantic import Field

from sema4ai_agent_server.agent_architecture_manager import agent_architectures
from sema4ai_agent_server.storage.checkpoint import get_checkpointer

DEFAULT_RUNBOOK = "You are a helpful agent."
DEFAULT_NAME = "Agent"


CHECKPOINTER = get_checkpointer()


class ConfigurableAgent(RunnableBinding):
    # Primary configurable fields
    agent: Agent | None = Field(
        None,
        description="The agent object used to set the prompts used for different configs.",
    )
    thread: Thread | None = Field(
        None, description="The thread the agent will be called on."
    )
    use_retrieval: bool = Field(
        False,
        description="A boolean flag indicating whether retrieval is enabled for the agent.",
    )
    interrupt_before_action: bool = Field(
        False,
        description="A boolean flag indicating whether the agent should interrupt "
        "before performing an action.",
    )
    knowledge_files: list[str] | None = Field(
        None, description="A list of knowledge files used by the agent."
    )
    checkpointer: BaseCheckpointSaver | None = Field(
        None,
        description="A checkpoint saver object used to save checkpoints for the agent.",
    )

    def __init__(
        self,
        *,
        agent: Agent | None = None,
        thread: Thread | None = None,
        use_retrieval: bool = False,
        interrupt_before_action: bool = False,
        knowledge_files: list[str] | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        kwargs: Mapping[str, Any] | None = None,
        config: Mapping[str, Any] | None = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        if agent is None:
            agent = dummy_agent
        agent_factory_class = agent_architectures[agent.advanced_config.architecture]
        agent_factory = agent_factory_class(
            agent=agent,
            thread=thread,
            use_retrieval=use_retrieval,
            interrupt_before_action=interrupt_before_action,
            checkpointer=checkpointer,
            knowledge_files=knowledge_files,
        )
        agent_executor = agent_factory.compile_agent(**others)
        super().__init__(
            agent_factory_class=agent_factory_class,
            agent=agent,
            thread=thread,
            use_retrieval=use_retrieval,
            interrupt_before_action=interrupt_before_action,
            knowledge_files=knowledge_files,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )


runnable_agent: Pregel = (
    ConfigurableAgent(
        agent=dummy_agent,
        thread=None,
        use_retrieval=False,
        interrupt_before_action=False,
        knowledge_files=None,
    )
    .configurable_fields(
        agent_factory_class=ConfigurableField(
            id="agent_factory_class",
            name="Agent Factory Class",
            description="The agent factory class to use. If provided as a string, it "
            "must be the fully qualified class name.",
        ),
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
    .with_types(input_type=Messages, output_type=Sequence[AnyMessage])
)
