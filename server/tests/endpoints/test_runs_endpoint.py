import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator, Mapping
from datetime import UTC, datetime
from typing import Any, NamedTuple

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.delta.base import GenericDelta
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.streaming.delta import (
    StreamingDelta,
    StreamingDeltaAgentFinished,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageContent,
    StreamingDeltaRequestToolExecution,
)
from agent_platform.core.thread.thread import Thread
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.user import User
from agent_platform.server.api.private_v2 import runs as runs_mod
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage import (
    AgentNotFoundError,
    RunNotFoundError,
    ThreadNotFoundError,
)

# -----------------------------------------------------------------------------
# Helper utilities -- these stay entirely local to the test module
# -----------------------------------------------------------------------------


class _CallCounter(dict[str, int]):
    """`dict` with a convenience `bump` method."""

    def bump(self, key: str) -> None:
        self[key] = self.get(key, 0) + 1


# -----------------------------------------------------------------------------
# Lightweight in-memory stubs
# -----------------------------------------------------------------------------


class StubStorage:
    def __init__(self) -> None:
        self.threads: dict[str, Thread] = {}
        self.runs: dict[str, Any] = {}
        self.agents: dict[str, Agent] = {}
        self.call_counts: _CallCounter = _CallCounter(
            get_agent=0,
            get_thread=0,
            upsert_thread=0,
            add_message_to_thread=0,
            create_run=0,
            upsert_run=0,
            get_run=0,
        )

    # ---------------- agent CRUD --------------------------------------------
    async def upsert_agent(self, user_id: str, agent: Agent) -> None:
        self.call_counts.bump("upsert_agent")
        self.agents[agent.agent_id] = agent

    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        self.call_counts.bump("delete_agent")
        del self.agents[agent_id]

    async def get_agent(self, user_id: str, agent_id: str) -> Agent:
        self.call_counts.bump("get_agent")
        return self.agents.setdefault(
            agent_id,
            Agent(
                agent_id=agent_id,
                name="StubAgent",
                description="A stub agent",
                version="0.0.1",
                runbook_structured=Runbook(raw_text="You are a helpful assistant.", content=[]),
                platform_configs=[],
                user_id=user_id,
                agent_architecture=AgentArchitecture(
                    name="agent_platform.architectures.default",
                    version="0.0.1",
                ),
                observability_configs=[],
            ),
        )

    # ---------------- thread CRUD -------------------------------------------
    async def get_thread(self, user_id: str, thread_id: str) -> Thread:
        self.call_counts.bump("get_thread")
        try:
            return self.threads[thread_id]
        except KeyError as exc:  # pragma: no cover
            raise ThreadNotFoundError from exc

    async def upsert_thread(self, user_id: str, thread: Thread) -> None:
        self.call_counts.bump("upsert_thread")
        self.threads[thread.thread_id] = thread

    async def add_message_to_thread(self, user_id: str, thread_id: str, message: Any) -> None:
        self.call_counts.bump("add_message_to_thread")

    # ---------------- run CRUD ----------------------------------------------
    async def create_run(self, run):
        self.call_counts.bump("create_run")
        self.runs[run.run_id] = run

    async def upsert_run(self, run):
        self.call_counts.bump("upsert_run")
        self.runs[run.run_id] = run

    async def get_run(self, run_id: str):
        self.call_counts.bump("get_run")
        if run_id not in self.runs:
            raise RunNotFoundError(run_id)
        return self.runs[run_id]

    # convenience for assertions
    def last_run(self):
        return next(reversed(self.runs.values())) if self.runs else None


class StubRunner:
    """Runner that immediately yields *AgentFinished* once invoked."""

    def __init__(self, *, run_id: str, thread_id: str, agent_id: str):
        self._thread_id = thread_id
        self._agent_id = agent_id
        self._run_id = run_id
        self._finished_delta = StreamingDeltaAgentFinished(
            run_id=run_id,
            thread_id=thread_id,
            agent_id=agent_id,
            timestamp=datetime.now(UTC),
        )
        self.kernel = None
        self.dispatched: list[Any] = []
        self._invoke_entered = asyncio.Event()

    # ---------------- runner lifecycle stubs --------------------------------
    async def start(self): ...

    async def stop(self): ...

    async def invoke(self, kernel):  # type: ignore[override]
        """Stores kernel, signals *get_event_stream* and returns immediately."""
        self.kernel = kernel
        self._invoke_entered.set()
        # Yield control so other tasks can proceed but finish fast.
        await asyncio.sleep(0)

    async def get_event_stream(self) -> AsyncGenerator[StreamingDelta, None]:
        await self._invoke_entered.wait()
        yield self._finished_delta

    async def dispatch_event(self, message):  # type: ignore[override]
        self.dispatched.append(message)


# -----------------------------------------------------------------------------
# pytest fixtures & helpers
# -----------------------------------------------------------------------------


@pytest.fixture
def stub_storage() -> StubStorage:
    return StubStorage()


@pytest.fixture
def stub_user() -> User:
    return User(user_id="00000000-0000-0000-0000-000000000000", sub="tenant:testing:user:system")


@pytest.fixture
def fastapi_app(stub_storage: StubStorage, stub_user: User) -> FastAPI:
    """Spin up a minimal FastAPI app with dependency overrides."""

    app = FastAPI()
    app.include_router(runs_mod.router, prefix="/runs")

    # --- dependency overrides ------------------------------------------------
    from agent_platform.server.auth.handlers import auth_user, auth_user_websocket
    from agent_platform.server.storage.option import StorageService

    app.dependency_overrides[StorageService.get_instance] = lambda: stub_storage
    app.dependency_overrides[auth_user] = lambda: stub_user  # HTTP
    app.dependency_overrides[auth_user_websocket] = lambda: stub_user  # WS

    add_exception_handlers(app)

    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    """Sync TestClient -- fastapi's internal loop handles async parts."""

    return TestClient(fastapi_app)


# -----------------------------------------------------------------------------
# Runner injection fixture -- avoids copy-pasted monkey-patching blocks
# -----------------------------------------------------------------------------


class _Injected(NamedTuple):
    runner: StubRunner
    aid: str


@pytest.fixture
def inject_runner(monkeypatch):
    """Factory that patches AgentArchManager.get_runner on demand.

    Usage:
        ctx = inject_runner(TalkativeRunner, run_id="r", thread_id="t", agent_id="a")
        # ctx.runner is the instance passed to app
    """

    def _factory(cls=StubRunner, **kwargs) -> _Injected:  # type: ignore[var-annotated]
        runner = cls(**kwargs)

        async def _patched_get_runner(self, *_a, **_kw):
            return runner

        monkeypatch.setattr(
            "agent_platform.server.agent_architectures.AgentArchManager.get_runner",
            _patched_get_runner,
        )
        return _Injected(runner=runner, aid=kwargs.get("agent_id", ""))

    return _factory


# -----------------------------------------------------------------------------
# Common JSON helpers / assertion helpers
# -----------------------------------------------------------------------------


def make_initial_payload(
    agent_id: str,
    thread_id: str,
    client_tools: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"agent_id": agent_id, "thread_id": thread_id, "messages": []}
    if client_tools is not None:
        payload["client_tools"] = client_tools
    return payload


def make_sample_client_tool(**overrides) -> Mapping[str, Any]:
    base = {
        "name": "test_client_tool",
        "description": "A test tool provided by the client",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "msg"}},
            "required": ["message"],
        },
        "category": "client-exec-tool",
    }
    base.update(overrides)
    return base


def assert_ws_closed(frame: Mapping[str, Any], code: int, reason: str | None = None) -> None:
    assert frame["type"] == "websocket.close"
    assert frame["code"] == code
    if reason is not None:
        assert frame["reason"] == reason


# -----------------------------------------------------------------------------
#   1)  basic async / status endpoints
# -----------------------------------------------------------------------------


def test_async_run_happy_path(client: TestClient, stub_storage: StubStorage, inject_runner):
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(StubRunner, run_id="r", thread_id=tid, agent_id=aid)

    resp = client.post(f"/runs/{aid}/async", json=make_initial_payload(aid, tid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"running", "completed"}
    assert uuid.UUID(body["run_id"])  # valid UUID

    run = stub_storage.last_run()
    assert run is not None
    assert run.run_type == "async"
    assert run.run_id == body["run_id"]


# status -- covers both running & completed after background task
@pytest.mark.parametrize("final_state", ["running", "completed"])
def test_get_run_status_happy_path(
    client: TestClient,
    stub_storage: StubStorage,
    inject_runner,
    final_state,
):
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    # tweak runner so that invoke never returns to simulate long-running if desired

    class SlowRunner(StubRunner):
        async def invoke(self, kernel):
            if final_state == "running":
                # never finishes --> server will mark running
                await asyncio.sleep(0.05)
            else:
                await super().invoke(kernel)

    inject_runner(SlowRunner, run_id="r", thread_id=tid, agent_id=aid)

    run_resp = client.post(f"/runs/{aid}/async", json=make_initial_payload(aid, tid))
    run_id = run_resp.json()["run_id"]

    status_resp = client.get(f"/runs/{run_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == final_state


def test_get_run_status_not_found(client: TestClient):
    missing = str(uuid.uuid4())

    resp = client.get(f"/runs/{missing}/status")
    assert resp.status_code == 404


# -----------------------------------------------------------------------------
#   2)  Agent-ID mismatch -- parameterised for HTTP & WS endpoints
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("endpoint", "is_ws", "close_code", "msg"),
    [
        ("/sync", False, status.HTTP_400_BAD_REQUEST, "Agent ID mismatch in URL and payload."),
        ("/async", False, status.HTTP_400_BAD_REQUEST, "Agent ID mismatch in URL and payload."),
        ("/stream", True, status.WS_1008_POLICY_VIOLATION, "Agent ID mismatch in URL and payload."),
    ],
)
def test_agent_id_mismatch(
    client: TestClient,
    endpoint: str,
    is_ws: bool,
    close_code: int,
    msg: str,
):
    aid, other, tid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    assert aid != other  # sanity

    if is_ws:
        with client.websocket_connect(f"/runs/{aid}{endpoint}") as ws:
            ws.send_json(make_initial_payload(other, tid))
            frame = ws.receive()
        assert_ws_closed(frame, close_code, msg)
    else:
        resp = client.post(f"/runs/{aid}{endpoint}", json=make_initial_payload(other, tid))
        assert resp.status_code == close_code
        assert resp.json()["error"]["message"] == msg


# -----------------------------------------------------------------------------
#   3)  stream happy-path & error branches
# -----------------------------------------------------------------------------


def _stream_open(client: TestClient, aid: str):  # helper so type checker knows return
    return client.websocket_connect(f"/runs/{aid}/stream")


def _ephemeral_stream_open(client: TestClient):
    return client.websocket_connect("/runs/ephemeral/stream")


def test_stream_happy_flow(client: TestClient, inject_runner, stub_storage: StubStorage):
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(StubRunner, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid))
        ready = ws.receive_json()
        finished = ws.receive_json()
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    assert ready["event_type"] == "agent_ready"
    assert finished["event_type"] == "agent_finished"

    saved = stub_storage.last_run()
    assert saved is not None
    assert saved.status == "completed"
    assert saved.metadata["finish_reason"] == "normal_completion"


def test_ephemeral_stream_happy_flow(client: TestClient, inject_runner):
    inject_runner(StubRunner, run_id="r", thread_id="ephemeral", agent_id="ephemeral")

    # Create a properly structured agent payload that matches UpsertAgentPayload
    agent_payload = {
        "name": "Tmp",
        "description": "tmp",
        "version": "1.0",
        "runbook": "You are a helpful assistant.",
        "agent_architecture": {
            "name": "agent_platform.architectures.default",
            "version": "1.0.0",
        },
        "platform_configs": [],
        "action_packages": [],
        "mcp_servers": [],
        "question_groups": [],
        "observability_configs": [],
        "mode": "conversational",
        "extra": {},
        "advanced_config": {},
        "metadata": {},
        "public": True,
        "id": None,
        "agent_id": None,
        "user_id": None,
        "created_at": None,
        "structured_runbook": None,
        "model": None,
    }

    with _ephemeral_stream_open(client) as ws:
        ws.send_json({"agent": agent_payload, "messages": []})
        ready = ws.receive_json()
        finished = ws.receive_json()
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    assert ready["event_type"] == "agent_ready"
    assert finished["event_type"] == "agent_finished"


def test_ephemeral_stream_with_metadata_and_name(client: TestClient, inject_runner):
    """Test ephemeral stream with additional metadata and custom name."""
    inject_runner(StubRunner, run_id="r", thread_id="ephemeral", agent_id="ephemeral")

    agent_payload = {
        "name": "TestAgent",
        "description": "A test agent for ephemeral runs",
        "version": "2.0",
        "runbook": "You are a test assistant.",
        "agent_architecture": {
            "name": "agent_platform.architectures.default",
            "version": "1.0.0",
        },
        "platform_configs": [],
        "action_packages": [],
        "mcp_servers": [],
        "question_groups": [],
        "observability_configs": [],
        "mode": "conversational",
        "extra": {},
        "advanced_config": {},
        "metadata": {},
        "public": True,
    }

    payload = {
        "agent": agent_payload,
        "name": "Test Thread",
        "messages": [],
        "metadata": {"test": "value"},
        "client_tools": [],
    }

    with _ephemeral_stream_open(client) as ws:
        ws.send_json(payload)
        ready = ws.receive_json()
        finished = ws.receive_json()
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    assert ready["event_type"] == "agent_ready"
    assert finished["event_type"] == "agent_finished"


def test_ephemeral_stream_invalid_agent_payload(client: TestClient):
    """Test that ephemeral stream rejects invalid agent payloads."""
    # Missing required fields
    bad_agent_payload = {
        "name": "Tmp",
        # Missing description, version, etc.
    }

    with _ephemeral_stream_open(client) as ws:
        ws.send_json({"agent": bad_agent_payload, "messages": []})
        frame = ws.receive()

    # Should close with error due to invalid payload
    assert frame["type"] == "websocket.close"
    assert frame["code"] in {status.WS_1003_UNSUPPORTED_DATA, status.WS_1008_POLICY_VIOLATION}


def test_ephemeral_stream_with_client_tools(client: TestClient, inject_runner):
    """Test ephemeral stream with client tools."""
    inject_runner(StubRunner, run_id="r", thread_id="ephemeral", agent_id="ephemeral")

    agent_payload = {
        "name": "TestAgent",
        "description": "A test agent with client tools",
        "version": "1.0",
        "runbook": "You are a helpful assistant.",
        "agent_architecture": {
            "name": "agent_platform.architectures.default",
            "version": "1.0.0",
        },
        "platform_configs": [],
        "action_packages": [],
        "mcp_servers": [],
        "question_groups": [],
        "observability_configs": [],
        "mode": "conversational",
        "extra": {},
        "advanced_config": {},
        "metadata": {},
        "public": True,
    }

    client_tools = [make_sample_client_tool(name="ephemeral_tool")]

    payload = {
        "agent": agent_payload,
        "messages": [],
        "client_tools": client_tools,
    }

    with _ephemeral_stream_open(client) as ws:
        ws.send_json(payload)
        ready = ws.receive_json()
        finished = ws.receive_json()
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    assert ready["event_type"] == "agent_ready"
    assert finished["event_type"] == "agent_finished"


def test_ephemeral_stream_does_not_auto_name(
    client: TestClient, inject_runner, stub_storage: StubStorage
):
    """Ephemeral threads should never be auto-named regardless of model output."""
    inject_runner(StubRunner, run_id="r", thread_id="ephemeral", agent_id="ephemeral")

    agent_payload = {
        "name": "TestAgent",
        "description": "A test agent",
        "version": "1.0",
        "runbook": "You are a helpful assistant.",
        "agent_architecture": {
            "name": "agent_platform.architectures.default",
            "version": "1.0.0",
        },
        "platform_configs": [],
        "action_packages": [],
        "mcp_servers": [],
        "question_groups": [],
        "observability_configs": [],
        "mode": "conversational",
        "extra": {},
        "advanced_config": {},
        "metadata": {},
        "public": True,
    }

    payload = {
        "agent": agent_payload,
        "name": "Custom Ephemeral",
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Hello"}]}],
        "metadata": {},
        "client_tools": [],
    }

    with _ephemeral_stream_open(client) as ws:
        ws.send_json(payload)
        ws.receive_json()  # ready
        ws.receive_json()  # finished
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    # One thread should exist with the provided name and without auto-namer metadata
    assert len(stub_storage.threads) == 1
    thread = next(iter(stub_storage.threads.values()))
    assert thread.name == "Custom Ephemeral"
    assert "thread_name" not in (thread.metadata or {})


def test_stream_client_disconnect_marks_cancelled(
    client: TestClient,
    inject_runner,
    stub_storage: StubStorage,
):
    """Client closes before runner finishes --> run becomes *cancelled*."""

    class HangingRunner(StubRunner):
        async def get_event_stream(self):
            # Hold the generator open forever without yielding a finished event
            await asyncio.Event().wait()
            if False:  # pragma: no cover
                yield self._finished  # ensures this is an *async-generator*

    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(HangingRunner, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid))
        ws.receive_json()  # agent_ready
        ws.close(code=status.WS_1000_NORMAL_CLOSURE)

    last_run = stub_storage.last_run()
    assert last_run is not None
    assert last_run.status == "cancelled"


def test_stream_invalid_json_payload(client: TestClient):
    aid = str(uuid.uuid4())
    with _stream_open(client, aid) as ws:
        ws.send_text("not-json")
        frame = ws.receive()
    assert_ws_closed(frame, status.WS_1003_UNSUPPORTED_DATA)


def test_stream_initial_payload_timeout(client: TestClient, monkeypatch):
    """Close with 1008 if initial payload never arrives."""
    orig = runs_mod._get_initial_payload

    async def tiny_timeout(ws, *, timeout: float = 10.0):
        return await orig(ws, timeout=0.001)

    monkeypatch.setattr(runs_mod, "_get_initial_payload", tiny_timeout)

    aid = str(uuid.uuid4())
    with _stream_open(client, aid) as ws:
        frame = ws.receive()
    assert_ws_closed(frame, status.WS_1008_POLICY_VIOLATION, "Initial payload not received in time")


# -----------------------------------------------------------------------------
#   4)  storage / runner error branches
# -----------------------------------------------------------------------------


def test_stream_agent_not_found(client: TestClient, stub_user: User):
    class EmptyStorage(StubStorage):
        async def get_agent(self, *_a, **_kw):
            raise AgentNotFoundError

    app = FastAPI()
    app.include_router(runs_mod.router, prefix="/runs")

    from agent_platform.server.auth.handlers import auth_user_websocket
    from agent_platform.server.storage.option import StorageService

    app.dependency_overrides[StorageService.get_instance] = lambda: EmptyStorage()
    app.dependency_overrides[auth_user_websocket] = lambda: stub_user

    tc = TestClient(app)
    aid = tid = str(uuid.uuid4())
    with tc.websocket_connect(f"/runs/{aid}/stream") as ws:
        ws.send_json(make_initial_payload(aid, tid))
        frame = ws.receive()
    assert_ws_closed(frame, status.WS_1008_POLICY_VIOLATION, "Agent not found")


def test_stream_runner_crash_marks_failed(
    client: TestClient,
    inject_runner,
    stub_storage: StubStorage,
):
    class KaboomRunner(StubRunner):
        async def invoke(self, kernel):
            raise RuntimeError("boom")

    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(KaboomRunner, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid))
        ws.receive_json()  # ready
        frame = ws.receive()
    assert_ws_closed(frame, status.WS_1011_INTERNAL_ERROR)
    last_run = stub_storage.last_run()
    assert last_run is not None
    assert last_run.status == "failed"


# -----------------------------------------------------------------------------
#   5)  delta ordering & client-to-runner dispatch
# -----------------------------------------------------------------------------


def test_stream_server_delta_order(client: TestClient, inject_runner):
    class Talkative(StubRunner):
        async def get_event_stream(self):
            yield StreamingDeltaMessageBegin(
                thread_id=self._thread_id,
                agent_id=self._agent_id,
                timestamp=datetime.now(UTC),
                sequence_number=0,
                message_id="m0",
            )
            yield StreamingDeltaMessageContent(
                timestamp=datetime.now(UTC),
                sequence_number=1,
                message_id="m0",
                delta=GenericDelta(path="/kind", op="replace", value="text"),
            )
            yield self._finished_delta

    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(Talkative, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid))
        kinds = [ws.receive_json()["event_type"] for _ in range(3)]
        assert kinds == ["agent_ready", "message_begin", "message_content"]


def test_stream_client_messages_reach_runner(client: TestClient, inject_runner):
    echo_messages: list[dict[str, Any]] = []

    class Echo(StubRunner):
        async def invoke(self, kernel):
            self.kernel = kernel
            self._invoke_entered.set()
            await asyncio.sleep(0.05)

        async def dispatch_event(self, message):
            echo_messages.append(message)

    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(Echo, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid))
        ws.receive_json()  # agent_ready
        msgs = [{"kind": "user", "seq": i} for i in range(3)]
        for m in msgs:
            ws.send_json(m)
        ws.receive_json()  # agent_finished
        # wait for the server-initiated close frame so TestClient exit is clean
        frame = ws.receive()
        assert_ws_closed(frame, status.WS_1000_NORMAL_CLOSURE)

    assert echo_messages == msgs


def test_stream_run_applies_auto_thread_naming(
    client: TestClient,
    inject_runner,
    stub_storage: StubStorage,
    monkeypatch,
):
    """Verify the auto-namer completes before stream completion and persists name."""

    class FakePlatform:
        def __init__(self, text: str) -> None:
            self._text = text

        async def generate_response(self, prompt, model):
            from agent_platform.core.responses.content import ResponseTextContent
            from agent_platform.core.responses.response import ResponseMessage

            return ResponseMessage(content=[ResponseTextContent(text=self._text)], role="agent")

    async def fake_selector(self, **_kwargs):
        return FakePlatform("Tokyo Weekend Outline!!! ✈️"), "test-model"

    # Patch kernel platform/model selection and storage helpers used by auto-namer
    from agent_platform.server.kernel import AgentServerKernel

    monkeypatch.setattr(AgentServerKernel, "get_platform_and_model", fake_selector, raising=True)

    async def list_runs_for_thread(thread_id: str):
        # Return only runs for the thread; will include the active run
        return [r for r in stub_storage.runs.values() if r.thread_id == thread_id]

    async def list_threads_for_agent(user_id: str, agent_id: str):
        return [t for t in stub_storage.threads.values() if t.agent_id == agent_id]

    # Attach the missing methods to the stub storage
    monkeypatch.setattr(stub_storage, "list_runs_for_thread", list_runs_for_thread, raising=False)
    monkeypatch.setattr(
        stub_storage, "list_threads_for_agent", list_threads_for_agent, raising=False
    )

    # Inject a runner that finishes immediately
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(StubRunner, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        payload = make_initial_payload(aid, tid)
        payload["messages"] = [
            {
                "role": "user",
                "content": [{"kind": "text", "text": "Help me plan a weekend trip to Tokyo."}],
            }
        ]
        ws.send_json(payload)
        ws.receive_json()  # agent_ready
        ws.receive_json()  # agent_finished
        frame = ws.receive()
        assert_ws_closed(frame, status.WS_1000_NORMAL_CLOSURE)

    # Ensure thread was auto-named (sanitized and persisted)
    thread = stub_storage.threads[tid]
    assert thread.name == "Tokyo Weekend Outline"
    meta = thread.metadata.get("thread_name", {})
    assert "auto_named_at" in meta


# -----------------------------------------------------------------------------
#   6)  thread upsert vs add-message paths
# -----------------------------------------------------------------------------


def test_upsert_thread_called_on_new_thread(
    client: TestClient,
    stub_storage: StubStorage,
    inject_runner,
):
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(StubRunner, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid))
        ws.receive_json()
        ws.receive_json()

    assert stub_storage.call_counts["upsert_thread"] == 1
    assert stub_storage.call_counts["add_message_to_thread"] == 0


def test_add_message_called_on_existing_thread(
    client: TestClient,
    stub_storage: StubStorage,
    inject_runner,
):
    tid, aid = str(uuid.uuid4()), str(uuid.uuid4())
    stub_storage.threads[tid] = Thread(
        thread_id=tid,
        user_id="u",
        messages=[],
        agent_id=aid,
        name="existing",
    )
    inject_runner(StubRunner, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        payload = make_initial_payload(aid, tid)
        payload["messages"] = [{"role": "user", "content": []}]
        ws.send_json(payload)
        ws.receive_json()
        ws.receive_json()

    assert stub_storage.call_counts["upsert_thread"] == 0
    assert stub_storage.call_counts["add_message_to_thread"] == 1


# -----------------------------------------------------------------------------
#   7)  client-tool plumbing -- happy paths + schema error
# -----------------------------------------------------------------------------


def _register_kernel_capture(inject_runner):  # helper used by multiple tests
    captured = {}

    class Inspect(StubRunner):
        async def invoke(self, kernel):
            captured["kernel"] = kernel
            await super().invoke(kernel)

    return captured, Inspect


def test_stream_with_client_tools(client: TestClient, inject_runner):
    cap, runner = _register_kernel_capture(inject_runner)
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(runner, run_id="r", thread_id=tid, agent_id=aid)

    tools = [make_sample_client_tool()]
    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid, tools))
        ws.receive_json()
        ws.receive_json()
    kernel = cap["kernel"]
    assert kernel is not None
    assert [t.name for t in kernel.client_tools] == ["test_client_tool"]


@pytest.mark.parametrize("tool_count", [0, 2])
def test_multiple_or_empty_client_tools(client: TestClient, inject_runner, tool_count: int):
    cap, runner = _register_kernel_capture(inject_runner)
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    inject_runner(runner, run_id="r", thread_id=tid, agent_id=aid)

    tools = [make_sample_client_tool(name=f"tool{i}") for i in range(tool_count)]
    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid, tools))
        ws.receive_json()
        ws.receive_json()
    kernel = cap["kernel"]
    assert kernel is not None
    assert len(kernel.client_tools) == tool_count


def test_invalid_client_tool_schema_rejected(client: TestClient):
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    bad_tools = [{"name": "bad"}]  # missing required fields
    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid, bad_tools))  # type: ignore[arg-type] (for testing)
        frame = ws.receive()
    # spec says either unsupported-data or policy-violation
    assert frame["code"] in {status.WS_1003_UNSUPPORTED_DATA, status.WS_1008_POLICY_VIOLATION}


# -----------------------------------------------------------------------------
#   8)  full execution flow -- info vs exec tools
# -----------------------------------------------------------------------------


def test_client_info_and_exec_tools_flow(client: TestClient, inject_runner, monkeypatch):
    aid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    outgoing: list[Any] = []

    async def capture(self, event):
        outgoing.append(event)

    from agent_platform.server.kernel.events import AgentServerEventsInterface

    monkeypatch.setattr(AgentServerEventsInterface, "dispatch", capture)

    class Tooly(StubRunner):
        async def invoke(self, kernel):
            # info tool completes immediately
            info_tool = ToolDefinition(
                name="info",
                description="info",
                input_schema={"type": "object"},
                category="client-info-tool",
            )
            info_call = ResponseToolUseContent(
                tool_call_id="info1", tool_name="info", tool_input_raw="{}"
            )
            async for _ in kernel.tools.execute_pending_tool_calls([(info_tool, info_call)]):
                pass

            # exec tool triggers request & waits --> we'll cancel quickly
            exec_tool = ToolDefinition(
                name="exec",
                description="exec",
                input_schema={"type": "object"},
                category="client-exec-tool",
            )
            exec_call = ResponseToolUseContent(
                tool_call_id="exec1", tool_name="exec", tool_input_raw="{}"
            )
            task = asyncio.create_task(kernel.tools._safe_execute_client_tool(exec_tool, exec_call))
            await asyncio.sleep(0.005)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await super().invoke(kernel)

    inject_runner(Tooly, run_id="r", thread_id=tid, agent_id=aid)

    with _stream_open(client, aid) as ws:
        ws.send_json(make_initial_payload(aid, tid, []))
        # Consume until server closes or disconnect happens
        try:
            while True:
                msg = ws.receive()
                if msg["type"] == "websocket.close":
                    break
        except WebSocketDisconnect:
            pass

    tool_names = {
        e.tool_name for e in outgoing if isinstance(e, StreamingDeltaRequestToolExecution)
    }
    assert "exec" in tool_names
    assert "info" in tool_names

    # Make sure the info tool's event was _not_ set to requires_execution=True
    info_events = [
        e
        for e in outgoing
        if isinstance(e, StreamingDeltaRequestToolExecution) and e.tool_name == "info"
    ]
    assert len(info_events) == 1
    assert info_events[0].requires_execution is False

    # Make sure the exec tool's event was set to requires_execution=True
    exec_events = [
        e
        for e in outgoing
        if isinstance(e, StreamingDeltaRequestToolExecution) and e.tool_name == "exec"
    ]
    assert len(exec_events) == 1
    assert exec_events[0].requires_execution is True
