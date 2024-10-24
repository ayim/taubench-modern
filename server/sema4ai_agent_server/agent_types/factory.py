from abc import ABC, abstractmethod
from typing import Any, Dict, Self, Type

from langchain.tools import BaseTool, Tool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompt_values import PromptValue
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import merge_configs
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.graph import CompiledGraph
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from sema4ai_agent_server.llms import get_chat_model
from sema4ai_agent_server.schema import (
    Agent,
    AgentArchitecture,
    AmazonBedrock,
    AnthropicClaude,
    AzureGPT,
    GoogleGemini,
    Ollama,
    OpenAIGPT,
    Thread,
    dummy_agent,
)
from sema4ai_agent_server.tools import (
    get_retrieval_tool,
    get_tools_from_action_packages,
)

DEFAULT_SUPPORTED_MODELS: list[Type] = [
    OpenAIGPT,
    AzureGPT,
    AnthropicClaude,
    AmazonBedrock,
    GoogleGemini,
    Ollama,
]


class BaseInputSpec(BaseModel):
    """A base input spec for the chat prompt template.

    Define all fields to be used as the input to your PredefinedChatPromptTemplate
    in this class. Metadata will be merged with the runnable's config and will not
    be included in the input when the model is exported as a dictionary.
    """

    runnable_config: RunnableConfig | None = Field(
        None,
        description="An optional config that will be merged with the config of the "
        "chat prompt template when it is run.",
        exclude=True,
        repr=False,
    )


class PredefinedChatPromptTemplate(ChatPromptTemplate, ABC):
    """A predefined chat prompt template used within agent graphs to generate the base
    prompts used by each node in the graph.

    The init method will take an optional Agent object which can be used
    to set the prompts used for different configs such as LLMs used or
    `reasoning` levels set. It then calls the create_template_messages method
    to build the list of messages used in the chat template.
    """

    input_spec: type[BaseInputSpec] = Field(
        ...,
        description="The input spec used to define the input to the chat prompt template.",
    )

    def __init__(self, agent: Agent = None) -> None:
        super().__init__(self.create_template_messages(agent))

    @abstractmethod
    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        """Build the list of messages used in the chat template. This method is called
        as part of initialization and should be overridden by subclasses to set the
        messages used in the template.

        Example:

            ```python

            def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
                return [
                    ("system", "You are a helpful assistant."),
                    ("placeholder", "{messages}"),
                ]
            ```

        Args:
            agent (Agent, optional): The agent object used to set the prompts used for
                different configs such as LLMs used or `reasoning` set. Defaults to None.
        """
        pass

    def invoke(
        self, input: BaseInputSpec | Dict, config: RunnableConfig | None = None
    ) -> PromptValue:
        """Invoke the chat prompt template with the given input and config.

        Args:
            input (BaseInputSpec, Dict): The input to the chat prompt template. If a
                dictionary is passed, it will be converted to a BaseInputSpec object.
            config (RunnableConfig, optional): The config used to run the chat
                prompt template. Defaults to None. Will be merged with the input's
                runnable_config if it is not None.
        """
        if not isinstance(input, self.input_spec):
            input = self.input_spec(**input)
        return super().invoke(
            input.model_dump(), merge_configs(config, input.runnable_config)
        )

    async def ainvoke(
        self,
        input: BaseInputSpec | Dict,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> PromptValue:
        """Invoke the chat prompt template with the given input and config.

        Args:
            input (BaseInputSpec): The input to the chat prompt template.
            config (RunnableConfig, optional): The config used to run the chat
                prompt template. Defaults to None. Will be merged with the input's
                runnable_config if it is not None.
        """
        if not isinstance(input, self.input_spec):
            input = self.input_spec(**input)
        return await super().ainvoke(
            input.model_dump(), merge_configs(config, input.runnable_config), **kwargs
        )


class AgentFactory(BaseModel, ABC):
    """An abstract factory class used to create agents for different configurations.

    This class defines the interface between the server components and the agent
    graph components. The primary method of which is the create_agent method which
    must return a CompiledGraph object for the given configuration.

    This class additionally contains shared methods and properties used by all
    agent factories.

    As a shortcut, the class defines itself as callable so that you can directly
    call the factory to call the create_agent method.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

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

    checkpoint: BaseCheckpointSaver | None = Field(
        None,
        description="A checkpoint saver object used to save checkpoints for the agent.",
    )
    knowledge_files: list[str] | None = Field(
        None, description="A list of knowledge files used by the agent."
    )

    architecture: AgentArchitecture = Field(
        AgentArchitecture.AGENT,
        description="The architecture of the factory.",
        exclude=True,
        const=True,
    )
    supported_models: list[Type] = Field(
        DEFAULT_SUPPORTED_MODELS,
        description="The supported models for the agent.",
        exclude=True,
        const=True,
    )

    default_agent: Agent = Field(
        dummy_agent,
        description="A default agent used in place of an actual agent during app "
        "startup and similar calls.",
        exclude=True,
        const=True,
    )

    @abstractmethod
    def compile_agent(self, **kwargs) -> CompiledGraph:
        """Create an agent based on this factory's configuration.

        Args:
            **kwargs: Additional keyword arguments passed to the agent factory.

        Returns:
            CompiledGraph: A compiled graph from this factory's configuration.
        """
        pass

    def __call__(self, **kwargs):
        return self.compile_agent(**kwargs)

    def get_agent(self) -> Agent:
        """Get the agent object for the factory, if set to None, returns
        the default agent.
        """
        if self.agent is None:
            return self.default_agent
        return self.agent

    def create_dynamic_headers(self) -> dict:
        """Create dynamic headers for the agent.

        These are primarily used by the agent's action packages.
        """
        if self.agent is None or self.thread is None:
            return {}
        return {
            "x-invoked_by_assistant_id": self.agent.id,
            "x-invoked_on_behalf_of_user_id": self.agent.user_id,
            "x-invoked_for_thread_id": self.thread.thread_id,
        }

    def get_tools_from_action_packages(self) -> list[BaseTool]:
        """Converts the agent's action packages to tools for use in the agent graph.

        Returns:
            list[BaseTool]: A list of tools used by the agent graph.
        """
        if self.agent is None:
            return []
        return get_tools_from_action_packages(
            self.agent.action_packages, self.create_dynamic_headers()
        )

    def get_retrieval_tool(self) -> Tool:
        """Get the retrieval tool for the agent and thread."""
        if self.agent is None or self.thread is None:
            return None
        return get_retrieval_tool(
            self.agent.id, self.thread.thread_id, self.agent.model
        )

    def get_tools(self) -> list[BaseTool]:
        """Get all tools used by the agent graph including action
        packages and retrieval tools.
        """
        retrieval_tool = self.get_retrieval_tool()
        if retrieval_tool is None:
            return self.get_tools_from_action_packages()
        else:
            return self.get_tools_from_action_packages() + [self.get_retrieval_tool()]

    def get_chat_model(self) -> BaseChatModel | None:
        """Get the chat model for the agent."""
        if self.agent is None:
            return self.default_agent.model
        return get_chat_model(self.agent.model)

    @model_validator(mode="after")
    def validate_agent(self) -> Self:
        """Validate the agent's model is supported and the agent's architecture
        matches the factory's architecture.
        """
        if self.agent.model not in self.supported_models:
            raise ValueError(
                f"Model {self.agent.model} is not supported by this agent factory."
            )

        if self.agent.advanced_config.architecture != self.architecture:
            raise ValueError(
                f"Agent architecture {self.agent.advanced_config.architecture} does not match factory architecture {self.architecture}."
            )

        return self
