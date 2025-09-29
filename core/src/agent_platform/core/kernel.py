"""The Kernel module defines the core interfaces for agent-server interactions.

The Kernel is the primary SDK for Cognitive Architectures (CAs) to interact with the
agent-server system, providing a comprehensive set of APIs for agent operations,
memory management, tool execution, and UI interactions.

All interactions between a Cognitive Architecture and the agent-server must go through
this interface, ensuring a consistent and controlled interaction model.
"""

from abc import ABC, abstractmethod
from typing import Any

from agent_platform.core.agent import Agent
from agent_platform.core.context import AgentServerContext
from agent_platform.core.errors.streaming import NoPlatformOrModelFoundError
from agent_platform.core.kernel_interfaces import (
    ConvertersInterface,
    DataFramesInterface,
    EventsInterface,
    FilesInterface,
    MemoryInterface,
    OTelInterface,
    PlatformInterface,
    PromptsInterface,
    RunbookInterface,
    StorageInterface,
    ThreadStateInterface,
    ToolsInterface,
    UserInteractionsInterface,
    WorkItemInterface,
)
from agent_platform.core.model_selector import (
    DefaultModelSelector,
    ModelSelectionRequest,
    ModelSelector,
)
from agent_platform.core.platforms.configs import ModelPrioritization, ModelType
from agent_platform.core.runs import Run
from agent_platform.core.streaming import IncomingDelta, StreamingDelta
from agent_platform.core.thread import Thread
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.user import User


class Kernel(ABC):
    """The Kernel is the core interface for Cognitive Architectures
    (CAs) to interact with the agent-server.

    It provides a comprehensive set of APIs for agent operations, memory management,
    tool execution, and UI interactions.
    """

    @property
    def model_selector(self) -> ModelSelector:
        """The model selector bound to this kernel instance."""
        return DefaultModelSelector()

    @property
    def current_datetime_str(self) -> str:
        """The current date and time as a string."""
        from datetime import UTC, datetime

        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    @property
    @abstractmethod
    def agent(self) -> "Agent":
        """The agent bound to this kernel instance.

        Returns:
            Agent: The agent bound to this kernel instance.
        """
        pass

    @property
    @abstractmethod
    def user(self) -> User:
        """The user bound to this kernel instance.

        Returns:
            User: The user bound to this kernel instance.
        """
        pass

    @property
    @abstractmethod
    def thread(self) -> Thread:
        """The thread bound to this kernel instance.

        Returns:
            Thread: The thread bound to this kernel instance.
        """
        pass

    @property
    @abstractmethod
    def run(self) -> Run:
        """The run bound to this kernel instance.

        Returns:
            Run: The run bound to this kernel instance.
        """
        pass

    @property
    @abstractmethod
    def converters(self) -> ConvertersInterface:
        """Interface for converting between thread, prompt, and response objects."""
        pass

    @property
    @abstractmethod
    def outgoing_events(self) -> EventsInterface[StreamingDelta]:
        """Generic event bus for CA to emit events to the agent-server.

        When invoking a Cognitive Architecture (CA) asynchronously, the CA will
        emit events to this (outgoing) bus. The agent-server will listen to these
        events and pass along appropriate updates to downstream listeners. For the
        most part, other APIs within the Kernel will send appropriate events to
        this bus. But, if you need to manually emit an event, you can do so here.

        Returns:
            EventsInterface: Interface for emitting events to the agent-server.
        """
        pass

    @property
    @abstractmethod
    def incoming_events(self) -> EventsInterface[IncomingDelta]:
        """Generic event bus for receiving events from the agent-server.

        The agent-server will emit events to this (incoming) bus. The CA may choose to
        listen to these events, or ignore them. (Think of cases like blocking until a
        user responds, or waiting for a user to respond, etc.)

        Returns:
            EventsInterface: Interface for receiving events from the agent-server.
        """
        pass

    @property
    @abstractmethod
    def files(self) -> FilesInterface:
        """Interface for interacting with files uploaded in agent chat.

        It is possible to upload files in a chat with an agent. This API allows
        for interacting with these files. Any CA that wants to support uploaded
        files will need to work with this API.

        Returns:
            FilesInterface: Interface for managing uploaded files.
        """
        pass

    @property
    @abstractmethod
    def memory(self) -> MemoryInterface:
        """Interface for interacting with the agent's memory.

        The memory API is used to interact with the agent's memory. This includes
        things like reading from memory, writing to memory, and other memory-related
        operations.

        Returns:
            MemoryInterface: Interface for memory operations.
        """
        pass

    @property
    @abstractmethod
    def platforms(self) -> list[PlatformInterface]:
        """Interface for interacting with the agent's model (LLM) platform.

        Every agent (and the kernel in general) has a model (LLM) platform
        configured so it can act intelligently. This API provides a way to
        interact with the model defined for the agent.

        Returns:
            list[PlatformInterface]: List of platform interfaces.
        """
        pass

    @property
    @abstractmethod
    def prompts(self) -> PromptsInterface:
        """Interface for building and managing prompts within a CA.

        The prompts API is used to build and manage prompts
        within a Cognitive Architecture (CA). The key features
        of this API are to support easy and opinionated prompt
        formatting.

        Returns:
            PromptsInterface: Interface for prompt management.
        """
        pass

    @property
    @abstractmethod
    def runbook(self) -> RunbookInterface:
        """Interface for interacting with the agent's natural language runbook.

        Every agent has a natural language runbook. The runbook is the key
        source of truth for the agents behavior. It is up to a Cognitive
        Architecture (CA) to interpret the runbook and use it to do useful
        work. This API provides a way for CAs to interact with the runbook
        (both as prose and as structured data, if runbook annotations are
        present).

        Returns:
            RunbookInterface: Interface for runbook interactions.
        """
        pass

    @property
    @abstractmethod
    def storage(self) -> StorageInterface:
        """Interface for interacting with the agent-server's storage.

        The storage API is used to interact with the agent-server's storage. This is
        useful for storing and retrieving data that is not specific to the agent, but
        may be useful for the Cognitive Architecture (CA) across multiple agents or
        across multiple runs.

        Returns:
            StorageInterface: Interface for storage operations.
        """
        pass

    @property
    @abstractmethod
    def tools(self) -> ToolsInterface:
        """Interface for building and executing tools.

        The tools API is used to build and execute tools. There are three primary
        types of tools: (1) actions attached to the agent, (2) internal tools provided
        by various Kernel interfaces, and (3) tools defined internally to a Cognitive
        Architecture (CA). The tools API provides a way to build and execute all
        three types of tools.

        Returns:
            ToolsInterface: Interface for tool operations.
        """
        pass

    @property
    @abstractmethod
    def client_tools(self) -> list[ToolDefinition]:
        """Tools attached to the kernel from an external client.

        Returns:
            list[ToolDefinition]: List of tool definitions.
        """
        pass

    @property
    @abstractmethod
    def thread_state(self) -> ThreadStateInterface:
        """Interface for accessing the in-memory representation of the current thread.

        The thread state is persisted to storage by the agent-server and, through the
        agent-server, thread state is used to update the UI.

        Returns:
            ThreadStateInterface: Interface for thread state operations.
        """
        pass

    @property
    @abstractmethod
    def user_interactions(self) -> UserInteractionsInterface:
        """Interface for interacting with the user.

        The user API is used to interact with the user. This includes things like
        prompting the user for input, blocking until the user responds, etc.

        Returns:
            UserInterface: Interface for user interactions.
        """
        pass

    @property
    @abstractmethod
    def otel(self) -> OTelInterface:
        """Interface for interacting with the OpenTelemetry (OTel) API.

        The OTel API is used to interact with the OpenTelemetry (OTel) API.
        """
        pass

    @property
    @abstractmethod
    def ctx(self) -> AgentServerContext:
        """Interface for interacting with the agent-server context.

        The agent-server context is used to interact with the agent-server.
        """

    @property
    @abstractmethod
    def data_frames(self) -> DataFramesInterface:
        """Interface for interacting with the agent-server's data frames.

        The data frames API is used to interact with the agent-server's data frames.
        """

    @property
    @abstractmethod
    def work_item(self) -> WorkItemInterface:
        """Interface for interacting with the thread's work item."""
        pass

    async def get_platform_and_model(
        self,
        direct_model_name: str | None = None,
        model_type: ModelType | None = None,
        prioritize: ModelPrioritization | None = None,
    ) -> tuple[PlatformInterface, str]:
        """Get a platform and a selected model.

        Arguments:
            direct_model_name: The name of the model to select. (Optional)
            model_type: The type of model to select. (Optional)
            prioritize: The prioritization of the model to select. (Optional)

        Returns:
            tuple[PlatformInterface, str]: A tuple of the first platform
                that supports the requested model and the model id.
        """
        for platform in self.platforms:
            model = self.model_selector.select_model(
                platform.client,
                ModelSelectionRequest(
                    direct_model_name=direct_model_name,
                    model_type=model_type,
                    prioritize=prioritize,
                ),
            )
            if model:
                return platform, model

        raise NoPlatformOrModelFoundError(
            message=f"No platform found for model type: {model_type}, "
            f"prioritizing: {prioritize}, "
            f"direct model name: {direct_model_name}",
            data={
                "model_type": model_type,
                "prioritize": prioritize,
                "direct_model_name": direct_model_name,
            },
        )

    def get_standard_span_attributes(
        self,
        extra_attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get standard span attributes that should be added to every span.

        This includes agent, thread, and run information.
        Additional attributes can be passed via kwargs.

        Args:
            **kwargs: Additional attributes to include

        Returns:
            dict[str, str]: Dictionary of attributes ready for ctx.add_span_attributes
        """
        attributes = {}

        # User information
        if self.user.cr_user_id:
            attributes["user_id"] = self.user.cr_user_id
        else:
            attributes["user_id"] = self.user.sub

        # Agent information
        if self.agent.agent_id:
            attributes["agent_id"] = self.agent.agent_id
        if self.agent.name:
            attributes["agent_name"] = self.agent.name

        # Thread information
        if self.thread.thread_id:
            attributes["thread_id"] = self.thread.thread_id
        if self.thread.name:
            attributes["thread_name"] = self.thread.name

        # Run information
        if self.run.run_id:
            attributes["run_id"] = self.run.run_id

        # Agent architecture information
        if self.agent.agent_architecture.name:
            attributes["agent_architecture_name"] = self.agent.agent_architecture.name
        if self.agent.agent_architecture.version:
            attributes["agent_architecture_version"] = self.agent.agent_architecture.version

        if extra_attributes:
            attributes.update(extra_attributes)

        return attributes
