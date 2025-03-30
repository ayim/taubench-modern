"""The Kernel module defines the core interfaces for agent-server interactions.

The Kernel is the primary SDK for Cognitive Architectures (CAs) to interact with the
agent-server system, providing a comprehensive set of APIs for agent operations,
memory management, tool execution, and UI interactions.

All interactions between a Cognitive Architecture and the agent-server must go through
this interface, ensuring a consistent and controlled interaction model.
"""

from abc import ABC, abstractmethod
from typing import Literal

from agent_platform.core.agent import Agent
from agent_platform.core.kernel_interfaces import (
    ConvertersInterface,
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
)
from agent_platform.core.model_selector import (
    DefaultModelSelector,
    ModelSelectionRequest,
    ModelSelector,
)
from agent_platform.core.runs import Run
from agent_platform.core.thread import Thread
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
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        """Interface for converting between thread, prompt, and response objects.
        """
        pass

    @property
    @abstractmethod
    def outgoing_events(self) -> EventsInterface:
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
    def incoming_events(self) -> EventsInterface:
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

    async def get_platform_and_model(
        self,
        direct_model_name: str | None = None,
        provider: str | None = None,
        model_type: Literal[
            "llm",
            "embedding",
            "text-to-image",
            "text-to-audio",
            "audio-to-text",
        ] | None = None,
        quality_tier: Literal["best", "balanced", "fastest"] | None = None,
    ) -> tuple[PlatformInterface, str]:
        """Get a platform and a selected model.

        Arguments:
            direct_model_name: The name of the model to select. (Optional)
            provider: The provider of the model to select. (Optional)
            model_type: The type of model to select. (Optional)
            quality_tier: The quality tier of the model to select. (Optional)

        Returns:
            tuple[PlatformInterface, str]: A tuple of the first platform
                that supports the requested model and the model id.
        """
        for platform in self.platforms:
            model = self.model_selector.select_model(
                platform.client,
                ModelSelectionRequest(
                    direct_model_name=direct_model_name,
                    provider=provider,
                    model_type=model_type,
                    quality_tier=quality_tier,
                ),
            )
            if model:
                return platform, model

        raise ValueError(
            f"No platform found for model type: {model_type}, "
            f"quality tier: {quality_tier}, "
            f"provider: {provider}, "
            f"direct model name: {direct_model_name}",
        )
