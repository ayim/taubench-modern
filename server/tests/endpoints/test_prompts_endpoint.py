import json
import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.finalizers.truncation_finalizer import (
    TruncationFinalizer,
)
from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.thread import Thread
from agent_platform.core.user import User
from agent_platform.core.utils import SecretString
from agent_platform.server.api.private_v2.prompt import (
    _create_platform_interface_and_get_model,
    prompt_generate,
    prompt_stream,
)
from agent_platform.server.kernel.model_platform import AgentServerPlatformInterface


# ──────────────────────────────────────────────────────────────────────────────
# Lightweight doubles for the pieces we don't want to hit in unit tests
# ──────────────────────────────────────────────────────────────────────────────
class _DummyDelta:
    def __init__(self, path: str, op: str, value):
        self.path = path
        self._dict = {"op": op, "path": path, "value": value}

    def model_dump(self) -> dict:
        return self._dict


class _DummyConverters:
    async def convert_prompt(self, prompt, model_id=None):
        return prompt  # The caller never inspects the converted prompt in tests


class _DummyPlatformClient:
    """Enough surface area to satisfy the endpoint helpers."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.converters = _DummyConverters()

    def attach_kernel(self, kernel) -> None:
        self._kernel = kernel

    async def generate_response(self, *args, **kwargs):
        class _FakeResponse:
            def __init__(self, model: str):
                self.model = model

            def excluding_raw_response(self) -> dict:
                # Mirrors the example "generate" payload
                return {
                    "content": [{"kind": "text", "text": "Madison."}],
                    "role": "agent",
                    "stop_reason": None,
                    "model": self.model,
                    "usage": {},
                }

        return _FakeResponse(kwargs["model"] if "model" in kwargs else "")

    async def generate_stream_response(self, *args, **kwargs) -> AsyncGenerator[_DummyDelta, None]:
        yield _DummyDelta("/role", "add", "agent")
        yield _DummyDelta("/content", "add", [])
        yield _DummyDelta("/content/0/text", "add", "Mad")
        yield _DummyDelta("/content/0/text", "add", "is")
        yield _DummyDelta("/content/0/text", "add", "on.")

    async def stream_raw_response(self, *args, **kwargs) -> AsyncGenerator[_DummyDelta, None]:
        """Mock implementation of stream_raw_response for testing."""
        # Return the same deltas as generate_stream_response for testing
        yield _DummyDelta("/role", "add", "agent")
        yield _DummyDelta("/content", "add", [])
        yield _DummyDelta("/content/0/text", "add", "Mad")
        yield _DummyDelta("/content/0/text", "add", "is")
        yield _DummyDelta("/content/0/text", "add", "on.")


class _DummyStorage:
    def __init__(self, agent=None, thread=None):
        self._agent = agent
        self._thread = thread

    async def get_agent(self, user_id: str, agent_id: str):
        assert self._agent is not None
        assert agent_id == self._agent.agent_id
        return self._agent

    async def get_thread(self, user_id: str, thread_id: str):
        assert self._thread is not None
        assert thread_id == self._thread.thread_id
        return self._thread


_DUMMY_KERNEL = SimpleNamespace()

# Create a mock context with start_span method
_DUMMY_CTX = MagicMock()
_DUMMY_CTX.user_context = SimpleNamespace(
    user=User(user_id="testing", sub="testing"),
)
# Mock the start_span method to return a context manager that yields a mock span
mock_span = MagicMock()
_DUMMY_CTX.start_span.return_value.__enter__ = MagicMock(return_value=mock_span)
_DUMMY_CTX.start_span.return_value.__exit__ = MagicMock(return_value=None)


# ──────────────────────────────────────────────────────────────────────────────
# Re-usable monkey-patches
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _patch_dependencies(monkeypatch):
    """Redirect all heavyweight collaborators to our dummies."""
    # Make every platform config return the dummy client -------------------------------
    monkeypatch.setattr(
        "agent_platform.core.platforms.base.PlatformClient.from_platform_config",
        lambda kernel, config: _DummyPlatformClient(config.kind),
    )

    # Avoid needing a real model selector ----------------------------------------------
    monkeypatch.setattr(
        "agent_platform.core.model_selector.default.DefaultModelSelector.select_model",
        lambda *a, **k: (
            k["request"].direct_model_name or "dummy-model"  # Direct name might be None
            if "request" in k
            else "dummy-model"
        ),
    )

    # Short-circuit context & kernel construction --------------------------------------
    monkeypatch.setattr(
        "agent_platform.core.context.AgentServerContext.from_request",
        lambda *a, **k: _DUMMY_CTX,
    )
    monkeypatch.setattr(
        "agent_platform.server.api.private_v2.utils.create_minimal_kernel",
        lambda ctx: _DUMMY_KERNEL,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 1.  The helper that chooses / instantiates the platform client
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "raw_config",
    [
        {
            "kind": "openai",
            "openai_api_key": "testing",
        },
        {
            "kind": "azure",
            "azure_api_key": "testing",
            "azure_endpoint_url": "https://api.openai.com/v1",
            "azure_api_version": "2025-01-01",
            "azure_deployment_name": "gpt-4o",
        },
        {
            "kind": "bedrock",
            "aws_access_key_id": "testing",
            "aws_secret_access_key": "testing",
            "region_name": "us-east-1",
        },
        {
            "kind": "google",
            "google_api_key": "testing",
        },
        {
            "kind": "cortex",
            "snowflake_username": "testing",
            "snowflake_password": "testing",
            "snowflake_account": "testing",
        },
        {
            "kind": "groq",
            "groq_api_key": "testing",
        },
    ],
)
def test_create_platform_client_for_every_kind(raw_config):
    """Given different `platform_config.kind`, the correct client is returned."""
    config_copy = raw_config.copy()

    platform_interface, model = _create_platform_interface_and_get_model(
        platform_config_raw=raw_config,
        context=_DUMMY_CTX,
        model="dummy-model",
        model_type="llm",
    )

    assert isinstance(platform_interface, AgentServerPlatformInterface)
    assert isinstance(platform_interface.client, _DummyPlatformClient)
    assert platform_interface.client.kind == config_copy["kind"]
    assert model == "dummy-model"


# ──────────────────────────────────────────────────────────────────────────────
# 2a.  /generate:  make sure the JSON serialises cleanly
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_endpoint_serialises(monkeypatch):
    """The /generate route should emit exactly what the dummy client returns."""

    # Create a properly mocked finalize_messages method
    async def mock_finalize(*args, **kwargs):
        return None

    fake_prompt = SimpleNamespace(
        finalize_messages=AsyncMock(side_effect=mock_finalize),
        messages=[],  # Add messages attribute that the implementation expects
    )

    # Mock _create_platform_interface_and_get_model to help with the test
    monkeypatch.setattr(
        "agent_platform.server.api.private_v2.prompt._create_platform_interface_and_get_model",
        lambda **kwargs: (_DummyPlatformClient("openai"), "some-override-model"),
    )

    response = await prompt_generate(
        prompt=fake_prompt,  # type: ignore
        platform_config_raw={"kind": "openai", "openai_api_key": "testing"},
        user=User(user_id="testing", sub="testing"),
        model="some-override-model",
        request=Request(
            scope={
                "type": "http",
                "method": "POST",
                "path": "/api/v2/prompts/generate",
            }
        ),
        storage=_DummyStorage(),  # type: ignore
    )

    # Verify finalize_messages was called (with no arguments)
    fake_prompt.finalize_messages.assert_called_once_with()

    expected = {
        "content": [{"kind": "text", "text": "Madison."}],
        "role": "agent",
        "stop_reason": None,
        "usage": {},
        "model": "some-override-model",
    }
    assert response == expected


# ──────────────────────────────────────────────────────────────────────────────
# 2b.  /stream: verify the Server-Sent-Events payload
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_stream_endpoint_serialises(monkeypatch):
    """/stream should forward each delta as `data:` lines in SSE format."""
    sent_events: list[str] = []

    # Create a properly mocked finalize_messages method
    async def mock_finalize(*args, **kwargs):
        return None

    # Mock _create_platform_interface_and_get_model to help with the test
    monkeypatch.setattr(
        "agent_platform.server.api.private_v2.prompt._create_platform_interface_and_get_model",
        lambda **kwargs: (_DummyPlatformClient("openai"), "dummy-model"),
    )

    # Fire the endpoint ---------------------------------------------------------
    fake_prompt = SimpleNamespace(
        finalize_messages=AsyncMock(side_effect=mock_finalize),
        messages=[],  # Add messages attribute that the implementation expects
    )
    resp = await prompt_stream(
        prompt=fake_prompt,  # type: ignore
        platform_config_raw={"kind": "openai", "openai_api_key": "testing"},
        user=User(user_id="testing", sub="testing"),
        request=Request(
            scope={
                "type": "http",
                "method": "POST",
                "path": "/api/v2/prompts/stream",
            }
        ),
        storage=_DummyStorage(),  # type: ignore
    )

    # Verify finalize_messages was called (with no arguments)
    fake_prompt.finalize_messages.assert_called_once_with()

    # Consume the events the endpoint produced ----------------------------------
    async for event in resp.body_iterator:
        # We're giving this a stream of dicts, so this should be fine
        if isinstance(event, dict):
            sent_events.append(event["data"])

    # Two deltas were wired through by the dummy client (see _DummyPlatformClient)
    assert sent_events == [
        json.dumps({"op": "add", "path": "/role", "value": "agent"}),
        json.dumps({"op": "add", "path": "/content", "value": []}),
        json.dumps({"op": "add", "path": "/content/0/text", "value": "Mad"}),
        json.dumps({"op": "add", "path": "/content/0/text", "value": "is"}),
        json.dumps({"op": "add", "path": "/content/0/text", "value": "on."}),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Test for TruncationFinalizer actual functionality with model platform
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_truncation_finalizer_with_platform():
    """Test that the TruncationFinalizer actually truncates tool results
    when used with a platform."""
    # Create a large tool result
    large_result = "This is a very large tool result. " * 10000  # Lots of tokens

    # Create a prompt with a tool result
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the weather?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_123",
                        tool_name="get_weather",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Create objects to test with
    kernel = MagicMock()
    platform = MagicMock()
    platform.client.model_map.model_context_windows = {"gpt-3.5-turbo": 2000}

    # Create the finalizer
    finalizer = TruncationFinalizer()

    # Get a reference to the original text for comparison
    original_text = prompt.messages[1].content[0].content[0].text  # type: ignore

    # Call finalizer - this is how it's used in generate_response in model_platform.py
    await prompt.finalize_messages(
        kernel=kernel,
        prompt_finalizers=[finalizer],  # Changed from prompt_finalizer to prompt_finalizers
        platform=platform,
        model="gpt-3.5-turbo",
    )

    # Verify truncation occurred
    truncated_text = prompt.messages[1].content[0].content[0].text  # type: ignore
    assert len(truncated_text) < len(original_text)
    assert "[Truncated...]" in truncated_text


# ──────────────────────────────────────────────────────────────────────────────
# New tests: using agent_id and thread_id to fetch platform config
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_endpoint_uses_agent_id(monkeypatch):
    called: dict = {}

    def spy(**kwargs):
        called["cfg"] = kwargs["platform_config_raw"]
        return _DummyPlatformClient("openai"), "dummy-model"

    monkeypatch.setattr(
        "agent_platform.server.api.private_v2.prompt._create_platform_interface_and_get_model",
        spy,
    )

    fake_prompt = SimpleNamespace(
        finalize_messages=AsyncMock(return_value=None),
        messages=[],  # Add messages attribute that the implementation expects
    )

    agent = Agent(
        name="Agent",
        description="desc",
        user_id="testing",
        runbook_structured=Runbook(content=[], raw_text=""),
        version="1.0",
        platform_configs=[
            OpenAIPlatformParameters(
                openai_api_key=SecretString("k"), platform_id=str(uuid.uuid4())
            )
        ],  # type: ignore
        agent_architecture=AgentArchitecture(name="arch", version="1"),
    )

    storage = _DummyStorage(agent)

    await prompt_generate(
        prompt=fake_prompt,  # type: ignore
        user=User(user_id="testing", sub="testing"),
        request=Request(scope={"type": "http", "method": "POST", "path": "/"}),
        storage=storage,  # type: ignore
        agent_id=agent.agent_id,
    )

    assert called["cfg"] == agent.platform_configs[0].model_dump()


@pytest.mark.asyncio
async def test_generate_endpoint_uses_thread_id(monkeypatch):
    called: dict = {}

    def spy(**kwargs):
        called["cfg"] = kwargs["platform_config_raw"]
        return _DummyPlatformClient("openai"), "dummy-model"

    monkeypatch.setattr(
        "agent_platform.server.api.private_v2.prompt._create_platform_interface_and_get_model",
        spy,
    )

    fake_prompt = SimpleNamespace(
        finalize_messages=AsyncMock(return_value=None),
        messages=[],  # Add messages attribute that the implementation expects
    )

    agent = Agent(
        name="Agent",
        description="desc",
        user_id="testing",
        runbook_structured=Runbook(content=[], raw_text=""),
        version="1.0",
        platform_configs=[
            OpenAIPlatformParameters(
                openai_api_key=SecretString("k"), platform_id=str(uuid.uuid4())
            )
        ],  # type: ignore
        agent_architecture=AgentArchitecture(name="arch", version="1"),
    )

    thread = Thread(
        user_id="testing",
        agent_id=agent.agent_id,
        name="Thread",
    )

    storage = _DummyStorage(agent, thread)

    await prompt_generate(
        prompt=fake_prompt,  # type: ignore
        user=User(user_id="testing", sub="testing"),
        request=Request(scope={"type": "http", "method": "POST", "path": "/"}),
        storage=storage,  # type: ignore
        thread_id=thread.thread_id,
    )

    assert called["cfg"] == agent.platform_configs[0].model_dump()
