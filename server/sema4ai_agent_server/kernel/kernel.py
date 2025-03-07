from agent_server_types_v2.agent import Agent
from agent_server_types_v2.kernel import Kernel
from agent_server_types_v2.kernel_interfaces import (
    ConvertersInterface,
    EventsInterface,
    FilesInterface,
    MemoryInterface,
    PromptsInterface,
    RunbookInterface,
    StorageInterface,
    ThreadStateInterface,
    ToolsInterface,
    UserInteractionsInterface,
)
from agent_server_types_v2.platforms.base import PlatformClient
from agent_server_types_v2.thread import Thread
from agent_server_types_v2.user import User
from sema4ai_agent_server.kernel.converters import AgentServerConvertersInterface
from sema4ai_agent_server.kernel.events import AgentServerEventsInterface
from sema4ai_agent_server.kernel.files import AgentServerFilesInterface
from sema4ai_agent_server.kernel.memory import AgentServerMemoryInterface
from sema4ai_agent_server.kernel.model_platform import AgentServerPlatformInterface
from sema4ai_agent_server.kernel.prompts import AgentServerPromptsInterface
from sema4ai_agent_server.kernel.runbook import AgentServerRunbookInterface
from sema4ai_agent_server.kernel.storage import AgentServerStorageInterface
from sema4ai_agent_server.kernel.thread_state import AgentServerThreadStateInterface
from sema4ai_agent_server.kernel.tools import AgentServerToolsInterface
from sema4ai_agent_server.kernel.user_interactions import (
    AgentServerUserInteractionsInterface,
)


class AgentServerKernel(Kernel):
    def __init__(self, user: User, thread: Thread, agent: Agent):
        self._user = user
        self._thread = thread
        self._agent = agent

        self._outgoing_events = AgentServerEventsInterface()
        self._incoming_events = AgentServerEventsInterface()
        self._files = AgentServerFilesInterface()
        self._memory = AgentServerMemoryInterface()
        self._prompts = AgentServerPromptsInterface()
        self._runbook = AgentServerRunbookInterface()
        self._storage = AgentServerStorageInterface()
        self._tools = AgentServerToolsInterface()
        self._thread_state = AgentServerThreadStateInterface(thread, agent)
        self._user_interactions = AgentServerUserInteractionsInterface()
        self._converters = AgentServerConvertersInterface()
        self._model_platforms = []

        # TODO: if kernel is used in init for some interfaces,
        # the order of initialization is important.
        self._outgoing_events.attach_kernel(self)
        self._incoming_events.attach_kernel(self)
        self._converters.attach_kernel(self)
        self._files.attach_kernel(self)
        self._memory.attach_kernel(self)
        self._prompts.attach_kernel(self)
        self._runbook.attach_kernel(self)
        self._storage.attach_kernel(self)
        self._tools.attach_kernel(self)
        self._thread_state.attach_kernel(self)
        self._user_interactions.attach_kernel(self)

        # Go through agent.platform_configs and create a platform interface for each
        for platform_config in agent.platform_configs:
            self._model_platforms.append(
                AgentServerPlatformInterface(
                    PlatformClient.from_platform_config(
                        kernel=self,
                        config=platform_config,
                    ),
                ),
            )
            self._model_platforms[-1].attach_kernel(self)

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def user(self) -> User:
        return self._user

    @property
    def thread(self) -> Thread:
        return self._thread

    @property
    def converters(self) -> ConvertersInterface:
        return self._converters

    @property
    def outgoing_events(self) -> EventsInterface:
        return self._outgoing_events

    @property
    def incoming_events(self) -> EventsInterface:
        return self._incoming_events

    @property
    def files(self) -> FilesInterface:
        return self._files

    @property
    def memory(self) -> MemoryInterface:
        return self._memory

    @property
    def prompts(self) -> PromptsInterface:
        return self._prompts

    @property
    def runbook(self) -> RunbookInterface:
        return self._runbook

    @property
    def storage(self) -> StorageInterface:
        return self._storage

    @property
    def tools(self) -> ToolsInterface:
        return self._tools

    @property
    def thread_state(self) -> ThreadStateInterface:
        return self._thread_state

    @property
    def user_interactions(self) -> UserInteractionsInterface:
        return self._user_interactions

    @property
    def platforms(self) -> list[AgentServerPlatformInterface]:
        return self._model_platforms
