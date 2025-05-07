import json
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Request

from agent_platform.core.user import User
from agent_platform.server.api.private_v2.prompt import (
    _create_platform_client_and_get_model,
    prompt_generate,
    prompt_stream,
)


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
                # Mirrors the example “generate” payload
                return {
                    "content": [{"kind": "text", "text": "Madison."}],
                    "role": "agent",
                    "stop_reason": None,
                    "model": self.model,
                    "usage": {},
                }

        return _FakeResponse(kwargs["model"] if "model" in kwargs else "")

    async def generate_stream_response(
        self, *args, **kwargs
    ) -> AsyncGenerator[_DummyDelta, None]:
        yield _DummyDelta("/role", "add", "agent")
        yield _DummyDelta("/content", "add", [])
        yield _DummyDelta("/content/0/text", "add", "Mad")
        yield _DummyDelta("/content/0/text", "add", "is")
        yield _DummyDelta("/content/0/text", "add", "on.")


_DUMMY_KERNEL = SimpleNamespace()
_DUMMY_CTX = SimpleNamespace(
    user_context=SimpleNamespace(
        user=User(user_id="testing", sub="testing"),
    ),
)


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

    platform_client, model = _create_platform_client_and_get_model(
        request=Request(
            scope={
                "type": "http",
                "method": "POST",
                "path": "/api/v2/prompts/generate",
            }
        ),
        user=User(user_id="testing", sub="testing"),
        platform_config_raw=raw_config,
    )

    assert isinstance(platform_client, _DummyPlatformClient)
    assert platform_client.kind == config_copy["kind"]
    assert model == "dummy-model"


# ──────────────────────────────────────────────────────────────────────────────
# 2a.  /generate:  make sure the JSON serialises cleanly
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_endpoint_serialises(monkeypatch):
    """The /generate route should emit exactly what the dummy client returns."""
    # Minimal “Prompt” stand-in where only .finalise_messages() is called.
    fake_prompt = SimpleNamespace(finalize_messages=AsyncMock())

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
    )

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

    # Fire the endpoint ---------------------------------------------------------
    fake_prompt = SimpleNamespace(finalize_messages=AsyncMock())
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
    )

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
