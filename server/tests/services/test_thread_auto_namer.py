from collections.abc import AsyncIterator
from typing import Literal, cast
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.prompts import Prompt
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.runs import Run
from agent_platform.core.streaming.delta import StreamingDeltaThreadNameUpdated
from agent_platform.core.thread import Thread
from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.thread.messages import ThreadUserMessage
from agent_platform.core.user import User
from agent_platform.server.kernel import AgentServerKernel
from agent_platform.server.services.thread_auto_namer import (
    maybe_auto_name_thread,
)

pytest_plugins = [
    "server.tests.storage.conftest",
    "server.tests.storage.sqlite.conftest",
]


class FakePlatform:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text

    async def generate_response(self, prompt: Prompt, model: str) -> ResponseMessage:
        return ResponseMessage(
            content=[ResponseTextContent(text=self.response_text)],
            role="agent",
        )


class FakeKernel:
    def __init__(
        self,
        *,
        agent: Agent,
        thread: Thread,
        run: Run,
        user: User,
        platform: FakePlatform,
    ) -> None:
        self.agent = agent
        self.thread = thread
        self.run = run
        self.user = user
        self._platform = platform
        self._model = "test-model"
        self.outgoing_events = _CaptureEvents()

    async def get_platform_and_model(self, **_kwargs) -> tuple[FakePlatform, str]:
        return self._platform, self._model


class _CaptureEvents:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def dispatch(self, event: object) -> None:
        self.events.append(event)

    # Unused in these tests, but included for interface completeness
    async def stream(self) -> AsyncIterator[object]:
        for event in self.events:
            yield event

    async def wait_for_event(self, predicate):
        raise NotImplementedError


def _make_user(user_id: str) -> User:
    return User(user_id=user_id, sub=f"tenant:test:user:{user_id}")


def _make_run(
    agent_id: str,
    thread_id: str,
    status: Literal["created", "running", "completed", "failed", "cancelled"] = "running",
) -> Run:
    return Run(
        run_id=str(uuid4()),
        agent_id=agent_id,
        thread_id=thread_id,
        status=status,
        run_type="stream",
    )


@pytest.mark.asyncio
async def test_auto_names_thread_on_first_run(
    storage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    await storage.upsert_agent(sample_user_id, sample_agent)

    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Untitled Thread",
        messages=[ThreadUserMessage(content=[ThreadTextContent(text="Help me plan a weekend trip to Tokyo.")])],
    )
    await storage.upsert_thread(sample_user_id, thread)
    stored_thread = await storage.get_thread(sample_user_id, thread.thread_id)

    run = _make_run(sample_agent.agent_id, thread.thread_id)
    await storage.create_run(run)

    user = _make_user(sample_user_id)
    kernel = FakeKernel(
        agent=sample_agent,
        thread=stored_thread,
        run=run,
        user=user,
        platform=FakePlatform("Tokyo Weekend Outline!!! ✈️"),
    )

    await maybe_auto_name_thread(cast(AgentServerKernel, kernel), storage)

    updated_thread = await storage.get_thread(sample_user_id, thread.thread_id)
    assert updated_thread.name == "Tokyo Weekend Outline"
    thread_name_meta = updated_thread.metadata.get("thread_name", {})
    assert thread_name_meta.get("original_name") == "Untitled Thread"
    assert "auto_named_at" in thread_name_meta
    # Model identifier is optional in storage metadata; presence of auto_named_at is sufficient
    assert thread_name_meta.get("user_named") is not True

    # Verify an event was dispatched with the new name
    assert isinstance(kernel.outgoing_events.events[0], StreamingDeltaThreadNameUpdated)
    evt = kernel.outgoing_events.events[0]
    assert evt.event_type == "thread_name_updated"
    assert evt.thread_id == thread.thread_id
    assert evt.new_name == "Tokyo Weekend Outline"
    assert evt.old_name == "Untitled Thread"
    assert evt.reason == "auto"


@pytest.mark.asyncio
async def test_auto_name_skips_when_user_named(
    storage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    await storage.upsert_agent(sample_user_id, sample_agent)

    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Custom Name",
        metadata={"thread_name": {"user_named": True}},
        messages=[ThreadUserMessage(content=[ThreadTextContent(text="Summarize our team meeting notes.")])],
    )
    await storage.upsert_thread(sample_user_id, thread)
    stored_thread = await storage.get_thread(sample_user_id, thread.thread_id)

    run = _make_run(sample_agent.agent_id, thread.thread_id)
    await storage.create_run(run)

    user = _make_user(sample_user_id)
    kernel = FakeKernel(
        agent=sample_agent,
        thread=stored_thread,
        run=run,
        user=user,
        platform=FakePlatform("Meeting Summary"),
    )

    await maybe_auto_name_thread(cast(AgentServerKernel, kernel), storage)

    unchanged_thread = await storage.get_thread(sample_user_id, thread.thread_id)
    assert unchanged_thread.name == "Custom Name"
    thread_name_meta = unchanged_thread.metadata.get("thread_name", {})
    assert "auto_named_at" not in thread_name_meta
    assert thread_name_meta.get("user_named") is True


@pytest.mark.asyncio
async def test_auto_name_skips_when_prior_runs_exist(
    storage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    await storage.upsert_agent(sample_user_id, sample_agent)

    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Original Thread",
        messages=[ThreadUserMessage(content=[ThreadTextContent(text="Draft a quarterly budget overview.")])],
    )
    await storage.upsert_thread(sample_user_id, thread)
    stored_thread = await storage.get_thread(sample_user_id, thread.thread_id)

    previous_run = _make_run(sample_agent.agent_id, thread.thread_id, status="completed")
    await storage.create_run(previous_run)

    current_run = _make_run(sample_agent.agent_id, thread.thread_id)
    await storage.create_run(current_run)

    user = _make_user(sample_user_id)
    kernel = FakeKernel(
        agent=sample_agent,
        thread=stored_thread,
        run=current_run,
        user=user,
        platform=FakePlatform("Quarterly Budget Plan"),
    )

    await maybe_auto_name_thread(cast(AgentServerKernel, kernel), storage)

    persisted_thread = await storage.get_thread(sample_user_id, thread.thread_id)
    assert persisted_thread.name == "Original Thread"
    thread_name_meta = persisted_thread.metadata.get("thread_name", {})
    assert "auto_named_at" not in thread_name_meta


@pytest.mark.asyncio
async def test_auto_name_allows_duplicate_names(
    storage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    await storage.upsert_agent(sample_user_id, sample_agent)

    existing_thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Project Kickoff Summary",
        messages=[ThreadUserMessage(content=[ThreadTextContent(text="Capture kickoff details.")])],
    )
    await storage.upsert_thread(sample_user_id, existing_thread)

    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Another Thread",
        messages=[ThreadUserMessage(content=[ThreadTextContent(text="Outline the project kickoff steps.")])],
    )
    await storage.upsert_thread(sample_user_id, thread)
    stored_thread = await storage.get_thread(sample_user_id, thread.thread_id)

    run = _make_run(sample_agent.agent_id, thread.thread_id)
    await storage.create_run(run)

    user = _make_user(sample_user_id)
    kernel = FakeKernel(
        agent=sample_agent,
        thread=stored_thread,
        run=run,
        user=user,
        platform=FakePlatform("Project Kickoff Summary"),
    )

    await maybe_auto_name_thread(cast(AgentServerKernel, kernel), storage)

    renamed_thread = await storage.get_thread(sample_user_id, thread.thread_id)
    # Duplicates are allowed now; no suffixing
    assert renamed_thread.name == "Project Kickoff Summary"
    thread_name_meta = renamed_thread.metadata.get("thread_name", {})
    assert thread_name_meta.get("original_name") == "Another Thread"
    assert "auto_named_at" in thread_name_meta


# ---------------------- Sanitization unit tests ----------------------


def _call_private_sanitizer(name: str | None) -> str | None:
    # Local import to access private for testing
    from agent_platform.server.services import thread_auto_namer as mod

    return mod._sanitize_name(name)


def test_sanitize_strips_quotes_and_punct():
    # Comma is stripped by sanitizer now
    assert _call_private_sanitizer('  "Hello, World!!!"  ') == "Hello World"
    assert _call_private_sanitizer("`Project Plan:` ") == "Project Plan"


def test_sanitize_newlines_and_whitespace_collapse():
    s = "Line one\n\n  line\t two   three\r\n"
    assert _call_private_sanitizer(s) == "Line one line two three"


def test_sanitize_removes_emoji_preserves_unicode_letters():
    # Emoji removed, Japanese kept
    s = "旅行 計画 ✈️🧳"
    assert _call_private_sanitizer(s) == "旅行 計画"


def test_sanitize_truncates_to_max_length():
    long = "A " + ("very " * 50) + "long title indeed"
    sanitized = _call_private_sanitizer(long)
    assert sanitized is not None
    assert len(sanitized) <= 80
