import json
import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.platforms.configs import PlatformModelConfigs
from agent_platform.core.platforms.openai.converters import OpenAIConverters
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.prompts.content.document import PromptDocumentContent
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

    def __init__(self, kind: str, parameters=None) -> None:
        self.kind = kind
        self.name = kind
        self.parameters = parameters
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
def _patch_dependencies(monkeypatch, request):
    """Redirect all heavyweight collaborators to our dummies."""
    # Make every platform config return the dummy client -------------------------------
    monkeypatch.setattr(
        "agent_platform.core.platforms.base.PlatformClient.from_platform_config",
        lambda kernel, config: _DummyPlatformClient(config.kind, config),
    )

    # Avoid needing a real model selector ----------------------------------------------
    if request.node.get_closest_marker("real_selector") is None:
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


@pytest.mark.asyncio
async def test_generate_endpoint_with_document_content(monkeypatch):
    """Test /generate endpoint with PromptDocumentContent."""
    import base64

    # Create a simple test document (mimicking a PDF)
    test_document_content = b"This is a test PDF document content"
    base64_content = base64.b64encode(test_document_content).decode("utf-8")

    # Mock _create_platform_interface_and_get_model to help with the test
    monkeypatch.setattr(
        "agent_platform.server.api.private_v2.prompt._create_platform_interface_and_get_model",
        lambda **kwargs: (_DummyPlatformClient("openai"), "some-override-model"),
    )

    # Create a prompt with document content following the spar-prompt-generate.py pattern
    prompt_with_document = Prompt(
        messages=[
            PromptUserMessage(
                [
                    PromptTextContent(text="Please summarize this document."),
                    PromptDocumentContent(
                        name="test_document.pdf",
                        mime_type="application/pdf",
                        value=base64_content,
                        sub_type="base64",
                    ),
                ]
            )
        ]
    )

    response = await prompt_generate(
        prompt=prompt_with_document,
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

    # Verify the response structure matches expected format
    expected = {
        "content": [{"kind": "text", "text": "Madison."}],
        "role": "agent",
        "stop_reason": None,
        "usage": {},
        "model": "some-override-model",
    }
    assert response == expected

    # Verify the document content was properly included in the prompt
    assert len(prompt_with_document.messages) == 1
    user_message = prompt_with_document.messages[0]
    assert isinstance(user_message, PromptUserMessage)
    assert len(user_message.content) == 2

    # Check text content
    text_content = user_message.content[0]
    assert isinstance(text_content, PromptTextContent)
    assert text_content.text == "Please summarize this document."

    # Check document content
    doc_content = user_message.content[1]
    assert isinstance(doc_content, PromptDocumentContent)
    assert doc_content.name == "test_document.pdf"
    assert doc_content.mime_type == "application/pdf"
    assert doc_content.value == base64_content
    assert doc_content.sub_type == "base64"


@pytest.mark.asyncio
@pytest.mark.real_selector
async def test_generate_endpoint_resolves_short_model_slug(monkeypatch):
    """The prompt endpoint upgrades a slug into the canonical model id."""

    captured: dict[str, str] = {}

    class _RecordedResponse:
        def __init__(self, model: str) -> None:
            self.model = model

        def excluding_raw_response(self) -> dict[str, str]:
            return {"model": self.model}

    async def _record_model(self, prompt, model: str):
        captured["model"] = model
        return _RecordedResponse(model)

    monkeypatch.setattr(
        "agent_platform.server.kernel.model_platform.AgentServerPlatformInterface.generate_response",
        _record_model,
    )

    fake_prompt = SimpleNamespace(
        finalize_messages=AsyncMock(return_value=None),
        messages=[],
    )

    response = cast(
        dict[str, str],
        await prompt_generate(
            prompt=fake_prompt,  # type: ignore[arg-type]
            user=User(user_id="testing", sub="testing"),
            request=Request(scope={"type": "http", "method": "POST", "path": "/"}),
            storage=_DummyStorage(),  # type: ignore[arg-type]
            platform_config_raw={"kind": "openai", "openai_api_key": "testing"},
            model="gpt-4-1",
        ),
    )

    expected = "openai/openai/gpt-4-1"
    assert response["model"] == expected
    assert captured["model"] == expected


@pytest.mark.asyncio
@pytest.mark.real_selector
async def test_generate_endpoint_resolves_full_generic_id(monkeypatch):
    """Canonical ids keep working alongside short slugs."""

    captured: dict[str, str] = {}

    class _RecordedResponse:
        def __init__(self, model: str) -> None:
            self.model = model

        def excluding_raw_response(self) -> dict[str, str]:
            return {"model": self.model}

    async def _record_model(self, prompt, model: str):
        captured["model"] = model
        return _RecordedResponse(model)

    monkeypatch.setattr(
        "agent_platform.server.kernel.model_platform.AgentServerPlatformInterface.generate_response",
        _record_model,
    )

    fake_prompt = SimpleNamespace(
        finalize_messages=AsyncMock(return_value=None),
        messages=[],
    )

    canonical = "openai/openai/gpt-4-1"
    response = cast(
        dict[str, str],
        await prompt_generate(
            prompt=fake_prompt,  # type: ignore[arg-type]
            user=User(user_id="testing", sub="testing"),
            request=Request(scope={"type": "http", "method": "POST", "path": "/"}),
            storage=_DummyStorage(),  # type: ignore[arg-type]
            platform_config_raw={"kind": "openai", "openai_api_key": "testing"},
            model=canonical,
        ),
    )

    assert response["model"] == canonical
    assert captured["model"] == canonical


@pytest.mark.asyncio
async def test_generate_endpoint_respects_minimize_reasoning(monkeypatch):
    """The minimize_reasoning query flag is forwarded to the prompt."""

    observed: dict[str, Any] = {}

    converters = OpenAIConverters()
    platform_configs = PlatformModelConfigs()

    async def _convert_prompt(
        self,
        prompt,
        model_id: str | None = None,
    ):
        converted = await converters.convert_prompt(prompt, model_id=model_id)
        observed["converted_prompt"] = converted
        observed["convert_model_id"] = model_id
        observed["convert_minimize_reasoning"] = prompt.minimize_reasoning
        return converted

    monkeypatch.setattr(
        _DummyConverters,
        "convert_prompt",
        _convert_prompt,
    )

    class _RecordedResponse:
        def __init__(self, model: str) -> None:
            self.model = model

        def excluding_raw_response(self) -> dict[str, str]:
            return {"model": self.model}

    async def _record_generate(
        self,
        converted_prompt,
        model: str,
    ):
        observed["generate_model"] = model
        generic_model_id = model if model.count("/") == 2 else f"openai/openai/{model}"
        platform_specific_model = platform_configs.models_to_platform_specific_model_ids[
            generic_model_id
        ]
        request_payload = converted_prompt.as_platform_request(platform_specific_model)
        observed["request_payload"] = request_payload
        return _RecordedResponse(platform_specific_model)

    monkeypatch.setattr(
        _DummyPlatformClient,
        "generate_response",
        _record_generate,
    )

    prompt = Prompt(
        messages=[PromptUserMessage([PromptTextContent(text="Hello")])],
    )

    response = await prompt_generate(
        prompt=prompt,
        user=User(user_id="testing", sub="testing"),
        request=Request(scope={"type": "http", "method": "POST", "path": "/"}),
        storage=_DummyStorage(),  # type: ignore[arg-type]
        platform_config_raw={"kind": "openai", "openai_api_key": "testing"},
        model="gpt-5-high",
        minimize_reasoning=True,
    )

    assert prompt.minimize_reasoning is True
    assert observed["convert_model_id"] == "gpt-5-high"
    assert observed["convert_minimize_reasoning"] is True

    assert observed["generate_model"] == "gpt-5-high"

    converted_prompt = observed["converted_prompt"]
    assert isinstance(converted_prompt, OpenAIPrompt)
    assert "effort" in converted_prompt.reasoning
    assert converted_prompt.reasoning["effort"] == "minimal"
    assert "summary" in converted_prompt.reasoning
    assert converted_prompt.reasoning["summary"] == "concise"

    request_payload = observed["request_payload"]
    assert request_payload["model"].startswith("gpt-5")
    assert request_payload["reasoning"]["effort"] == "minimal"
    assert request_payload["reasoning"]["summary"] == "concise"
    assert response["model"] == request_payload["model"]  # type: ignore
