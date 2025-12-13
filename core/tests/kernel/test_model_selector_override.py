from typing import cast

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.model_selector import DefaultModelSelector
from agent_platform.core.model_selector.selection_request import ModelSelectionRequest
from agent_platform.core.platforms.base import PlatformClient


class _DummyParams:
    def __init__(self, models: dict[str, list[str]] | None = None):
        # Allowlist provider -> [models]
        self.models = models or {"openai": ["gpt-4-1"]}


class _DummyClient:
    """Minimal stub to satisfy DefaultModelSelector requirements.

    It only exposes `.name` and `.parameters.models` which the selector reads.
    """

    def __init__(self, name: str = "openai", params: _DummyParams | None = None):
        self.name = name
        self.parameters = params or _DummyParams()


class _DummyPlatform:
    """Simple wrapper that mimics the PlatformInterface shape used by Kernel."""

    def __init__(self, client: _DummyClient):
        self.client = client
        self.name = client.name


class _MinimalKernel(Kernel):
    """Concrete Kernel for tests with only the pieces we need.

    Implements required abstract properties but only `platforms` and
    `model_selector` are actually exercised in these tests.
    """

    def __init__(self, platforms: list[_DummyPlatform]):
        self._platforms = platforms
        self._selector = DefaultModelSelector()

    # Bind a stateful model selector so overrides persist across calls
    @property
    def model_selector(self) -> DefaultModelSelector:  # type: ignore[override]
        return self._selector

    # Only `platforms` is used by the code under test
    @property
    def platforms(self):  # type: ignore[override]
        return self._platforms

    # Unused abstract properties for this test
    @property
    def agent(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def user(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def thread(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def run(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def converters(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def outgoing_events(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def incoming_events(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def files(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def memory(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def prompts(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def runbook(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def storage(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def tools(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def client_tools(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def thread_state(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def user_interactions(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def otel(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def ctx(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def data_frames(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def work_item(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def documents(self):  # type: ignore[override]
        raise NotImplementedError

    @property
    def sql_generation(self):  # type: ignore[override]
        raise NotImplementedError


@pytest.mark.unit
def test_default_selector_accepts_simple_model_slug():
    """Passing a short model slug still resolves to the generic id."""
    selector = DefaultModelSelector()
    platform = _DummyClient(name="openai", params=_DummyParams({"openai": ["gpt-4-1"]}))

    selected = selector.select_model(
        platform=cast(PlatformClient, platform),
        request=ModelSelectionRequest(direct_model_name="gpt-4-1"),
    )

    assert selected == "openai/openai/gpt-4-1"


@pytest.mark.unit
def test_default_selector_accepts_full_generic_id():
    """Passing the canonical generic id still matches exactly."""
    selector = DefaultModelSelector()
    platform = _DummyClient(name="openai", params=_DummyParams({"openai": ["gpt-4-1"]}))

    selected = selector.select_model(
        platform=cast(PlatformClient, platform),
        request=ModelSelectionRequest(direct_model_name="openai/openai/gpt-4-1"),
    )

    assert selected == "openai/openai/gpt-4-1"


@pytest.mark.unit
def test_litellm_single_provider_prefers_direct_model():
    """LiteLLM special-cases a single provider/model into a fully-qualified id."""
    selector = DefaultModelSelector()
    platform = _DummyClient(name="litellm", params=_DummyParams({"custom": ["who-knows"]}))

    selected = selector.select_model(platform=cast(PlatformClient, platform))

    assert selected == "litellm/custom/who-knows"


@pytest.mark.unit
def test_litellm_multi_models_honors_direct_model_name():
    """When multiple LiteLLM models are available, a direct_model_name picks a matching slug."""
    selector = DefaultModelSelector()
    platform = _DummyClient(name="litellm", params=_DummyParams({"custom": ["mistral", "sonnet"]}))

    selected = selector.select_model(
        platform=cast(PlatformClient, platform),
        request=ModelSelectionRequest(direct_model_name="sonnet"),
    )

    assert selected == "litellm/custom/sonnet"


@pytest.mark.unit
def test_litellm_multi_models_without_direct_name_falls_back():
    """Without a direct override, multiple LiteLLM models fall back to the platform default."""
    selector = DefaultModelSelector()
    platform = _DummyClient(name="litellm", params=_DummyParams({"custom": ["mistral", "sonnet"]}))

    selected = selector.select_model(platform=cast(PlatformClient, platform))

    assert selected == "litellm/openai/gpt-5-low"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_platform_and_model_uses_override_when_set():
    """When `override_model_id` is set, the selector returns that ID."""
    # Use an OpenAI-like dummy so DefaultModelSelector finds candidates
    dummy = _DummyPlatform(_DummyClient(name="openai", params=_DummyParams({"openai": ["gpt-4-1", "gpt-4o"]})))
    kernel = _MinimalKernel(platforms=[dummy])

    override_id = "openai/openai/gpt-4-1"
    kernel.model_selector.override_model(override_id)

    platform, model = await kernel.get_platform_and_model(model_type="llm")

    assert platform.name == "openai"
    assert model == override_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_platform_and_model_raises_for_unknown_override():
    """Invalid override IDs for a platform raise a ValueError from the selector."""
    dummy = _DummyPlatform(_DummyClient(name="openai", params=_DummyParams({"openai": ["gpt-4-1"]})))
    kernel = _MinimalKernel(platforms=[dummy])

    # This generic ID does not exist in the configs for the 'openai' platform
    kernel.model_selector.override_model("openai/openai/not-a-real-model")

    with pytest.raises(ValueError, match="Override model id openai/openai/not-a-real-model not found in candidates"):
        await kernel.get_platform_and_model(model_type="llm")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_platform_and_model_without_override_uses_allowlist():
    """Without an override, selection honors the platform allowlist."""
    dummy = _DummyPlatform(_DummyClient(name="openai", params=_DummyParams({"openai": ["gpt-4o"]})))
    kernel = _MinimalKernel(platforms=[dummy])

    platform, model = await kernel.get_platform_and_model(model_type="llm")

    assert platform.name == "openai"
    assert model == "openai/openai/gpt-4o"
