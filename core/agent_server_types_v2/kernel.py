"""The Kernel module defines the core interfaces for agent-server interactions.

The Kernel is the primary SDK for Cognitive Architectures (CAs) to interact with the
agent-server system, providing a comprehensive set of APIs for agent operations,
memory management, tool execution, and UI interactions.

All interactions between a Cognitive Architecture and the agent-server must go through
this interface, ensuring a consistent and controlled interaction model.
"""

from abc import ABC, abstractmethod

from agent_server_types_v2.agent import Agent
from agent_server_types_v2.kernel_interfaces import (
    EventsInterface,
    FilesInterface,
    MemoryInterface,
    PlatformInterface,
    PromptsInterface,
    RunbookInterface,
    StorageInterface,
    ThreadStateInterface,
    ToolsInterface,
    UserInteractionsInterface,
)
from agent_server_types_v2.thread import Thread
from agent_server_types_v2.user import User


class Kernel(ABC):
    """The Kernel is the core interface for Cognitive Architectures
    (CAs) to interact with the agent-server.

    It provides a comprehensive set of APIs for agent operations, memory management,
    tool execution, and UI interactions.
    """

    @property
    @abstractmethod
    def agent(self) -> Agent:
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
    def platform(self) -> PlatformInterface:
        """Interface for interacting with the agent's model (LLM) platform.

        Every agent (and the kernel in general) has a model (LLM) platform
        configured so it can act intelligently. This API provides a way to
        interact with the model defined for the agent.

        Returns:
            PlatformInterface: Interface for model interactions.
        """
        # TODO: This implementation follows the idea that a user does not configure
        # the model in the agent but instead configures a default platform for the
        # kernel and then the agent architecture or the default model selector will
        # select the model from the platform.
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
