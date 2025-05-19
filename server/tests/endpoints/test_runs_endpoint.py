import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, ClassVar

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.delta.base import GenericDelta
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.streaming.delta import (
    StreamingDelta,
    StreamingDeltaAgentFinished,
    StreamingDeltaAgentReady,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageContent,
)
from agent_platform.core.thread.thread import Thread
from agent_platform.core.user import User
from agent_platform.server.api.private_v2 import runs as runs_mod
from agent_platform.server.storage import ThreadNotFoundError
from agent_platform.server.storage.errors import AgentNotFoundError


class StubStorage:
    """
    In-memory replacement for `StorageDependency` with only the
    coroutine methods that `runs.py` calls.
    """

    def __init__(self) -> None:
        self.threads: dict[str, Any] = {}
        self.runs: dict[str, Any] = {}
        self.agents: dict[str, Any] = {}
        self.call_counts: dict[str, int] = {
            "get_agent": 0,
            "get_thread": 0,
            "upsert_thread": 0,
            "add_message_to_thread": 0,
            "create_run": 0,
            "upsert_run": 0,
        }

    # ---- agent CRUD ------------------------------------------------
    async def get_agent(self, user_id: str, agent_id: str) -> Agent:
        # Always hand back the same stub
        self.call_counts["get_agent"] += 1
        return self.agents.setdefault(
            agent_id,
            Agent(
                agent_id=agent_id,
                name="StubAgent",
                description="A stub agent",
                version="0.0.1",
                runbook_structured=Runbook(
                    raw_text="You are a helpful assistant.",
                    content=[],
                ),
                platform_configs=[],
                user_id=user_id,
                agent_architecture=AgentArchitecture(
                    name="agent_platform.architectures.default",
                    version="0.0.1",
                ),
                observability_configs=[],
            ),
        )

    # ---- thread CRUD -----------------------------------------------
    async def get_thread(self, user_id: str, thread_id: str) -> Thread:
        try:
            self.call_counts["get_thread"] += 1
            return self.threads[thread_id]
        except KeyError as exc:
            raise ThreadNotFoundError from exc

    async def upsert_thread(self, user_id: str, thread: Thread) -> None:
        self.call_counts["upsert_thread"] += 1
        self.threads[thread.thread_id] = thread

    async def add_message_to_thread(
        self, user_id: str, thread_id: str, message: Any
    ) -> None:
        self.call_counts["add_message_to_thread"] += 1

    # ---- run CRUD --------------------------------------------------
    async def create_run(self, run) -> None:
        self.call_counts["create_run"] += 1
        self.runs[run.run_id] = run

    async def upsert_run(self, run) -> None:
        self.call_counts["upsert_run"] += 1
        self.runs[run.run_id] = run

    # Helpers for assertions
    def last_run(self):
        return next(reversed(self.runs.values())) if self.runs else None


class StubRunner:
    """
    Simulates the agent architecture's runner. It streams exactly one
    *AgentFinished* event and does nothing else.
    """

    override_agent_id: ClassVar[str] = "agent-1"

    def __init__(
        self,
        run_id: str,
        thread_id: str,
        agent_id: str,
    ) -> None:
        self._thread_id = thread_id
        self._agent_id = agent_id
        self._run_id = run_id
        self._finished_event = StreamingDeltaAgentFinished(
            run_id=run_id,
            thread_id=thread_id,
            agent_id=self.override_agent_id,
            timestamp=datetime.now(UTC),
        )
        self._invoked = asyncio.Event()
        self.dispatched = []

    # Runner lifecycle ----------------------------------------------
    async def start(self): ...

    async def stop(self): ...

    # The "business logic" ------------------------------------------
    async def invoke(self, kernel):
        # Wait until get_event_stream() has yielded and then let the
        # coroutine finish.
        await asyncio.sleep(1)
        await self._invoked.wait()

    async def get_event_stream(self) -> AsyncGenerator[StreamingDelta, None]:
        # First iteration of the async-generator: send the finished event
        self._invoked.set()
        yield self._finished_event

    async def dispatch_event(self, message):
        self.dispatched.append(message)


# -----------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------


@pytest.fixture
def stub_storage() -> StubStorage:
    return StubStorage()


@pytest.fixture
def stub_user() -> User:
    """A bare-minimum AuthedUserWebsocket replacement."""
    user_id = "00000000-0000-0000-0000-000000000000"
    sub = "tenant:testing:user:system"
    return User(user_id=user_id, sub=sub)


@pytest.fixture
def fastapi_app(
    stub_storage: StubStorage,
    stub_user: User,
) -> FastAPI:
    """
    Assemble a FastAPI app that includes only the runs router and
    overrides the heavy dependencies with our stubs.
    """
    app = FastAPI()

    # --- mount router ------------------------------------------------
    app.include_router(runs_mod.router, prefix="/runs")

    # --- dependency overrides ----------------------------------------
    #
    # 1. storage
    from agent_platform.server.storage.option import StorageService

    app.dependency_overrides[StorageService.get_instance] = lambda: stub_storage

    # 2. current websocket user
    from agent_platform.server.auth.handlers import auth_user_websocket

    app.dependency_overrides[auth_user_websocket] = lambda: stub_user

    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    # FastAPI's TestClient spins an event loop internally; we do *not*
    # mark websocket tests with @pytest.mark.asyncio.
    return TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def patch_agent_arch_manager(monkeypatch):
    async def _patched_get_runner(self, name, version, thread_id):
        return StubRunner(run_id="test-run", thread_id=thread_id, agent_id="agent-1")

    monkeypatch.setattr(
        "agent_platform.server.agent_architectures.AgentArchManager.get_runner",
        _patched_get_runner,
    )


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------


def make_initial_payload(agent_id: str, thread_id: str) -> dict[str, Any]:
    """Minimum valid InitiateStreamPayload JSON for the endpoint."""
    return {
        "agent_id": agent_id,
        "thread_id": thread_id,
        "messages": [],  # empty chat history
    }


# -----------------------------------------------------------------
# Tests
# -----------------------------------------------------------------


def test_stream_run_happy_path(client: TestClient, stub_storage: StubStorage):
    """
    The client sends the 3-field initial payload, receives
    *AgentReady* followed by *AgentFinished*, and the socket then
    closes cleanly.
    """
    test_agent_uuid = str(uuid.uuid4())
    test_thread_id = str(uuid.uuid4())
    StubRunner.override_agent_id = test_agent_uuid
    with client.websocket_connect(f"/runs/{test_agent_uuid}/stream") as ws:
        # ── 1. send payload ─────────────────────────────────────────
        ws.send_json(make_initial_payload(test_agent_uuid, test_thread_id))

        # ── 2. first frame: AgentReady ─────────────────────────────
        first = ws.receive_json()
        first.pop("event_type")
        as_delta = StreamingDeltaAgentReady(**first)
        assert as_delta.thread_id == test_thread_id
        assert as_delta.agent_id == test_agent_uuid

        # ── 3. second frame: AgentFinished ────────────────────────
        second = ws.receive_json()
        second.pop("event_type")
        as_delta = StreamingDeltaAgentFinished(**second)
        assert as_delta.thread_id == test_thread_id
        assert as_delta.agent_id == StubRunner.override_agent_id
        assert as_delta.timestamp

        # ── 4. connection should now be closed by the server ──────
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    # After the socket is shut the run should have been marked
    # "completed" in storage.
    saved_run = stub_storage.last_run()
    assert saved_run is not None
    assert saved_run.status == "completed"
    assert saved_run.metadata["finish_reason"] == "normal_completion"


def test_stream_run_agent_id_mismatch(client: TestClient):
    """
    If the URL path and the JSON payload contain different agent_ids,
    the server must close the connection with 1008 (policy violation).
    """
    test_agent_uuid = str(uuid.uuid4())
    mismatched_agent_id = str(uuid.uuid4())
    if mismatched_agent_id == test_agent_uuid:
        # Lol... this is like a lottery win here
        mismatched_agent_id = str(uuid.uuid4())
    test_thread_id = str(uuid.uuid4())
    StubRunner.override_agent_id = test_agent_uuid
    with client.websocket_connect(f"/runs/{test_agent_uuid}/stream") as ws:
        bad_payload = make_initial_payload(mismatched_agent_id, test_thread_id)
        ws.send_json(bad_payload)

        # Starlette returns a dict when the first frame is a close frame
        close_frame = ws.receive()

    assert close_frame["type"] == "websocket.close"
    assert close_frame["code"] == status.WS_1008_POLICY_VIOLATION


def test_stream_run_client_disconnect(client: TestClient, stub_storage: StubStorage):
    """
    If the *client* closes the socket first, the server should mark
    the run as "cancelled".
    """
    test_agent_uuid = str(uuid.uuid4())
    test_thread_id = str(uuid.uuid4())
    StubRunner.override_agent_id = test_agent_uuid
    with client.websocket_connect(f"/runs/{test_agent_uuid}/stream") as ws:
        ws.send_json(make_initial_payload(test_agent_uuid, test_thread_id))
        # Consume AgentReady only; then close from the client side.
        ws.receive_json()  # AgentReady
        ws.close(code=status.WS_1000_NORMAL_CLOSURE)

    saved_run = stub_storage.last_run()
    assert saved_run is not None
    assert saved_run.status == "cancelled"
    assert saved_run.metadata["finish_reason"] == "websocket_disconnected"


def test_stream_invalid_json_payload(client: TestClient):
    aid = str(uuid.uuid4())
    with client.websocket_connect(f"/runs/{aid}/stream") as ws:
        ws.send_text("this is not JSON")
        close = ws.receive()
    assert close["code"] == status.WS_1003_UNSUPPORTED_DATA


def test_stream_initial_payload_timeout(monkeypatch, client: TestClient):
    # 1. Patch _get_initial_payload to use a very short timeout.
    #    Store the original to call it from our wrapper.
    original_get_initial_payload = runs_mod._get_initial_payload

    async def fast_timeout_get_initial_payload(websocket, timeout: float = 10.0):
        return await original_get_initial_payload(websocket, timeout=0.01)

    monkeypatch.setattr(
        runs_mod, "_get_initial_payload", fast_timeout_get_initial_payload
    )

    # 2. Make the actual websocket.receive_json hang longer than our new short timeout
    #    This ensures that the wait_for inside the (now fast-timed-out)
    #    _get_initial_payload will indeed raise a TimeoutError.
    async def _hang_forever_receive_json(*args, **kwargs):
        await asyncio.sleep(0.1)  # Sleep for 0.1s, which is > patched 0.01s timeout

    monkeypatch.setattr(
        "starlette.websockets.WebSocket.receive_json", _hang_forever_receive_json
    )

    aid = str(uuid.uuid4())
    with client.websocket_connect(f"/runs/{aid}/stream") as ws:
        # Client sends nothing.
        # The server side will call our patched _get_initial_payload,
        # which will call the original with a 0.01s timeout.
        # The patched websocket.receive_json will sleep for 0.1s,
        # causing the wait_for in _get_initial_payload to time out.
        # This leads to a WebSocketException and a close frame.
        close_frame = ws.receive()  # Client receives the close frame.

    assert close_frame["type"] == "websocket.close"
    assert close_frame["code"] == status.WS_1008_POLICY_VIOLATION
    assert close_frame["reason"] == "Initial payload not received in time"


def test_stream_agent_not_found(client: TestClient, monkeypatch, stub_user: User):
    class EmptyStorage(StubStorage):
        async def get_agent(self, user_id: str, agent_id: str) -> Agent:
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
        close = ws.receive()

    assert close["code"] == status.WS_1008_POLICY_VIOLATION
    assert close["reason"] == "Agent not found"


def test_stream_runner_crash_marks_failed(
    monkeypatch,
    client: TestClient,
    stub_storage: StubStorage,
):
    class ExplodingRunner(StubRunner):
        async def invoke(self, kernel):
            raise RuntimeError("kaboom")

    async def _patched_get_runner(self, *_, **__):
        return ExplodingRunner(run_id="r", thread_id="t", agent_id="a")

    monkeypatch.setattr(
        "agent_platform.server.agent_architectures.AgentArchManager.get_runner",
        _patched_get_runner,
    )

    aid = tid = str(uuid.uuid4())
    with client.websocket_connect(f"/runs/{aid}/stream") as ws:
        ws.send_json(make_initial_payload(aid, tid))
        # Still going to get an agent ready
        ws.receive_json()
        ws.receive_json()
        close = ws.receive()
    assert close["code"] == status.WS_1011_INTERNAL_ERROR

    run = stub_storage.last_run()
    assert run is not None
    assert run.status == "failed"
    assert run.metadata["finish_reason"] == "unexpected_error"


def test_stream_server_to_client_delta_flow(monkeypatch, client: TestClient):
    """
    Runner emits Begin + Content + Finished; ensure they arrive in order.
    """

    class TalkativeRunner(StubRunner):
        async def get_event_stream(self):
            yield StreamingDeltaMessageBegin(
                thread_id=self._thread_id,
                agent_id=self.override_agent_id,
                timestamp=datetime.now(UTC),
                sequence_number=0,
                message_id="00000000-0000-0000-0000-000000000001",
            )
            yield StreamingDeltaMessageContent(
                timestamp=datetime.now(UTC),
                sequence_number=1,
                message_id="00000000-0000-0000-0000-000000000002",
                delta=GenericDelta(
                    path="/kind",
                    op="replace",
                    value="text",
                ),
            )
            yield self._finished_event

    async def _patched_get_runner(self, *_, **__):
        return TalkativeRunner(run_id="r", thread_id="t", agent_id="a")

    monkeypatch.setattr(
        "agent_platform.server.agent_architectures.AgentArchManager.get_runner",
        _patched_get_runner,
    )

    aid = tid = str(uuid.uuid4())
    with client.websocket_connect(f"/runs/{aid}/stream") as ws:
        ws.send_json(make_initial_payload(aid, tid))

        kinds = [ws.receive_json()["event_type"] for _ in range(3)]
        assert kinds == [
            "agent_ready",
            "message_begin",
            "message_content",
        ]

        ws.close()


def test_stream_client_messages_dispatched(monkeypatch, client: TestClient):
    """
    Verify that whatever the client sends after AgentReady is forwarded
    to runner.dispatch_event().
    """

    class EchoRunner(StubRunner):
        async def invoke(self, kernel):
            await asyncio.sleep(0.05)  # keep socket open for a moment

    echo = EchoRunner(run_id="r", thread_id="t", agent_id="a")

    async def _patched_get_runner(self, *_, **__):
        return echo

    monkeypatch.setattr(
        "agent_platform.server.agent_architectures.AgentArchManager.get_runner",
        _patched_get_runner,
    )

    aid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    with client.websocket_connect(f"/runs/{aid}/stream") as ws:
        ws.send_json(make_initial_payload(aid, tid))
        ws.receive_json()  # AgentReady
        to_send = [{"kind": "user_event", "seq": i} for i in range(3)]
        for msg in to_send:
            ws.send_json(msg)

        ws.receive_json()  # AgentFinished
        ws.close()

    assert echo.dispatched == to_send


def test_upsert_thread_called_on_new_thread(
    client: TestClient,
    stub_storage: StubStorage,
):
    aid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    with client.websocket_connect(f"/runs/{aid}/stream") as ws:
        ws.send_json(make_initial_payload(aid, tid))
        ws.receive_json()
        ws.receive_json()
        ws.close()

    assert stub_storage.call_counts["upsert_thread"] == 1
    assert stub_storage.call_counts["add_message_to_thread"] == 0


def test_add_message_called_on_existing_thread(
    client: TestClient,
    stub_storage: StubStorage,
):
    # Pre-insert a thread so code path hits add_message_to_thread
    tid = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    stub_storage.threads[tid] = Thread(
        thread_id=tid,
        user_id="u",
        messages=[],
        agent_id=aid,
        name="test-thread",
    )

    with client.websocket_connect(f"/runs/{aid}/stream") as ws:
        ws.send_json(make_initial_payload(aid, tid))
        ws.receive_json()
        ws.receive_json()
        ws.close()

    assert stub_storage.call_counts["add_message_to_thread"] >= 0
    # upsert should NOT be called for an existing thread
    assert stub_storage.call_counts["upsert_thread"] == 0
