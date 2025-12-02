"""Shared lightweight test stubs for Kernel-dependent tests.

These stubs implement just enough surface of Kernel and related
objects to exercise functionality that streams messages and persists
agent changes (e.g., special commands handlers).
"""

from dataclasses import dataclass
from typing import Any

from agent_platform.core.kernel import Kernel


class MsgStub:
    def __init__(self) -> None:
        self.agent_metadata: dict[str, Any] = {"models": []}
        self.contents: list[str] = []
        self._committed = False

    def append_content(self, s: str, complete: bool = False) -> None:
        self.contents.append(s)

    async def stream_delta(self) -> None:
        return None

    async def commit(self) -> None:
        self._committed = True


class ThreadStateStub:
    def __init__(self) -> None:
        self.thread_id = "t-1"
        self._last_msg: MsgStub | None = None

    async def new_agent_message(self, *_, **__) -> MsgStub:
        self._last_msg = MsgStub()
        return self._last_msg


@dataclass
class _AgentArch:
    name: str = "default"
    version: str = "1.0.0"


class AgentStub:
    def __init__(self) -> None:
        self.agent_id = "a-1"
        self.name = "Test Agent"
        self.version = "1.0.0"
        self.mode = "conversational"
        self.agent_architecture = _AgentArch()
        self.action_packages = []
        self.mcp_servers = []
        self.extra: dict[str, Any] = {"agent_settings": {}}

    def copy(self, **updates: Any) -> "AgentStub":
        new = AgentStub()
        new.__dict__.update(self.__dict__)
        for k, v in updates.items():
            setattr(new, k, v)
        return new


class UserStub:
    def __init__(self) -> None:
        self.user_id = "u-1"
        self.cr_user_id = "u-1"
        self.sub = "u-1"


class RunStub:
    def __init__(self) -> None:
        self.run_id = "r-1"


class ThreadStub:
    def __init__(self) -> None:
        self.thread_id = "t-1"
        self.messages: list[Any] = []
        self.latest_user_message_as_text = ""


class StorageStub:
    def __init__(self) -> None:
        self._last_upsert: tuple[str, Any] | None = None

    async def upsert_agent(self, user_id: str, agent: Any) -> None:
        self._last_upsert = (user_id, agent)


class MinimalKernelStub(Kernel):
    def __init__(self) -> None:
        self._agent = AgentStub()
        self._user = UserStub()
        self._run = RunStub()
        self._thread = ThreadStub()
        self._thread_state = ThreadStateStub()
        self._storage = StorageStub()

    # Properties used by handlers
    @property
    def agent(self) -> Any:
        return self._agent

    @property
    def user(self) -> Any:
        return self._user

    @property
    def thread(self) -> Any:
        return self._thread

    @property
    def run(self) -> Any:
        return self._run

    @property
    def thread_state(self) -> Any:
        return self._thread_state

    @property
    def storage(self) -> Any:
        return self._storage

    # Unused abstract properties for these tests
    @property
    def platforms(self):
        return []

    @property
    def converters(self):
        raise NotImplementedError

    @property
    def outgoing_events(self):
        raise NotImplementedError

    @property
    def incoming_events(self):
        raise NotImplementedError

    @property
    def files(self):
        raise NotImplementedError

    @property
    def memory(self):
        raise NotImplementedError

    @property
    def prompts(self):
        raise NotImplementedError

    @property
    def runbook(self):
        raise NotImplementedError

    @property
    def tools(self):
        raise NotImplementedError

    @property
    def client_tools(self):
        return []

    @property
    def user_interactions(self):
        raise NotImplementedError

    @property
    def otel(self):
        raise NotImplementedError

    @property
    def ctx(self) -> Any:
        class _Ctx:
            def add_span_attributes(self, *args: Any, **kwargs: Any) -> None:
                return None

            def increment_counter(self, *args: Any, **kwargs: Any) -> None:
                return None

        return _Ctx()

    @property
    def data_frames(self) -> Any:
        class _DF:
            def is_enabled(self) -> bool:
                return False

        return _DF()

    @property
    def work_item(self) -> Any:
        class _WI:
            def is_enabled(self) -> bool:
                return False

        return _WI()

    @property
    def documents(self) -> Any:
        class _Docs:
            async def is_enabled(self) -> bool:
                return False

            async def step_initialize(self, state: Any) -> None:
                pass

            def get_document_tools(self) -> tuple:
                return ()

        return _Docs()
