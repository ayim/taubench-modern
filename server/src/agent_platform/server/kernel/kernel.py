import json

from agent_platform.core.agent import Agent
from agent_platform.core.context import AgentServerContext
from agent_platform.core.kernel import Kernel
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
)
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.runs import Run
from agent_platform.core.streaming import IncomingDelta, StreamingDelta
from agent_platform.core.thread import Thread
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.user import User
from agent_platform.server.kernel.converters import AgentServerConvertersInterface
from agent_platform.server.kernel.data_frames import AgentServerDataFramesInterface
from agent_platform.server.kernel.events import AgentServerEventsInterface
from agent_platform.server.kernel.files import AgentServerFilesInterface
from agent_platform.server.kernel.memory import AgentServerMemoryInterface
from agent_platform.server.kernel.model_platform import AgentServerPlatformInterface
from agent_platform.server.kernel.otel import AgentServerOTelInterface
from agent_platform.server.kernel.prompts import AgentServerPromptsInterface
from agent_platform.server.kernel.runbook import AgentServerRunbookInterface
from agent_platform.server.kernel.storage import AgentServerStorageInterface
from agent_platform.server.kernel.thread_state import AgentServerThreadStateInterface
from agent_platform.server.kernel.tools import AgentServerToolsInterface
from agent_platform.server.kernel.user_interactions import (
    AgentServerUserInteractionsInterface,
)


class AgentServerKernel(Kernel):
    def __init__(  # noqa: PLR0915
        self,
        ctx: AgentServerContext,
        thread: Thread,
        agent: Agent,
        run: Run,
        client_tools: list[ToolDefinition] | None = None,
    ):
        # Store context
        self._ctx = ctx

        # Start by setting up OTel interface
        try:
            from opentelemetry import trace

            kernel_tracer = trace.get_tracer("agent-server.kernel")
            self._otel = AgentServerOTelInterface(kernel_tracer)
        except Exception:
            # TODO: where should we log this?
            self._otel = AgentServerOTelInterface()
        finally:
            self._otel.attach_kernel(self)

        with self._otel.span("initialize_kernel") as span:
            self._user = ctx.user_context.user
            span.add_event("attached user to kernel", {"user_id": self._user.user_id})
            self._agent = agent
            span.add_event(
                "attached agent to kernel", {"agent_id": agent.agent_id, "agent_name": agent.name}
            )
            self._thread = thread
            span.add_event("attached thread to kernel", {"thread_id": thread.thread_id})
            self._run = run
            span.add_event("attached run to kernel", {"run_id": run.run_id})
            self._client_tools = client_tools or []
            if self._client_tools:
                span.add_event(
                    "attached client tools",
                    {
                        "count": len(self._client_tools),
                        # Let's log the full client tool defs for future debugging
                        "tools": [json.dumps(t.model_dump()) for t in self._client_tools],
                    },
                )

        with self._otel.span("initialize_interfaces") as span:
            self._outgoing_events = AgentServerEventsInterface()
            span.add_event("initialized outgoing events")
            self._incoming_events = AgentServerEventsInterface()
            span.add_event("initialized incoming events")
            self._files = AgentServerFilesInterface()
            span.add_event("initialized files")
            self._memory = AgentServerMemoryInterface()
            span.add_event("initialized memory")
            self._prompts = AgentServerPromptsInterface()
            span.add_event("initialized prompts")
            self._runbook = AgentServerRunbookInterface()
            span.add_event("initialized runbook")
            self._storage = AgentServerStorageInterface()
            span.add_event("initialized storage")
            self._tools = AgentServerToolsInterface()
            span.add_event("initialized tools")
            self._thread_state = AgentServerThreadStateInterface(thread, agent)
            span.add_event("initialized thread state")
            self._user_interactions = AgentServerUserInteractionsInterface()
            span.add_event("initialized user interactions")
            self._converters = AgentServerConvertersInterface()
            span.add_event("initialized converters")
            self._data_frames = AgentServerDataFramesInterface()
            span.add_event("initialized data frames")
            self._model_platforms = []

            # TODO: if kernel is used in init for some interfaces,
            # the order of initialization is important.
            self._outgoing_events.attach_kernel(self)
            span.add_event("attached outgoing events")
            self._incoming_events.attach_kernel(self)
            span.add_event("attached incoming events")
            self._converters.attach_kernel(self)
            span.add_event("attached converters")
            self._files.attach_kernel(self)
            span.add_event("attached files")
            self._memory.attach_kernel(self)
            span.add_event("attached memory")
            self._prompts.attach_kernel(self)
            span.add_event("attached prompts")
            self._runbook.attach_kernel(self)
            span.add_event("attached runbook")
            self._storage.attach_kernel(self)
            span.add_event("attached storage")
            self._tools.attach_kernel(self)
            span.add_event("attached tools")
            self._thread_state.attach_kernel(self)
            span.add_event("attached thread state")
            self._user_interactions.attach_kernel(self)
            span.add_event("attached user interactions")
            self._data_frames.attach_kernel(self)
            span.add_event("attached data frames")

            # Go through agent.platform_configs and create a platform interface for each
            span.add_event("initializing model platforms")
            for i, platform_config in enumerate(agent.platform_configs):
                span.add_event(
                    f"initializing model platform #{i + 1}",
                    {"platform_class": platform_config.__class__.__name__},
                )
                self._model_platforms.append(
                    AgentServerPlatformInterface(
                        PlatformClient.from_platform_config(
                            kernel=self,
                            config=platform_config,
                        ),
                    ),
                )
                span.add_event(f"initialized model platform #{i + 1}")
                self._model_platforms[-1].attach_kernel(self)
                span.add_event(f"attached model platform #{i + 1}")

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
    def run(self) -> Run:
        return self._run

    @property
    def client_tools(self) -> list[ToolDefinition]:
        return self._client_tools

    @property
    def converters(self) -> ConvertersInterface:
        return self._converters

    @property
    def data_frames(self) -> DataFramesInterface:
        return self._data_frames

    @property
    def outgoing_events(self) -> EventsInterface[StreamingDelta]:
        return self._outgoing_events

    @property
    def incoming_events(self) -> EventsInterface[IncomingDelta]:
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
    def platforms(self) -> list[PlatformInterface]:
        return self._model_platforms

    @property
    def otel(self) -> OTelInterface:
        return self._otel

    @property
    def ctx(self) -> AgentServerContext:
        return self._ctx
