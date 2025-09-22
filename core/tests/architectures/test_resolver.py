import types
from dataclasses import dataclass, field
from typing import Literal

import pytest

from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.architectures.resolver import (
    ArchitectureResolutionError,
    PlatformCandidateSet,
    resolve_architecture,
)
from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.platforms.configs import PlatformModelConfigs


@dataclass(frozen=True, kw_only=True)
class DummyOpenAIParams(PlatformParameters):
    """Minimal PlatformParameters for kind 'openai' with optional model allowlist.

    This avoids real env requirements while exercising resolver logic.
    """

    kind: Literal["openai"] = field(default="openai", init=False)

    # Inherit `models` from base; default None (no allowlist)

    def model_dump(self, *, exclude_none: bool = True) -> dict:
        return super().model_dump(exclude_none=exclude_none)


@dataclass(frozen=True, kw_only=True)
class DummyBedrockParams(PlatformParameters):
    """Minimal PlatformParameters for kind 'bedrock' with optional model allowlist."""

    kind: Literal["bedrock"] = field(default="bedrock", init=False)

    def model_dump(self, *, exclude_none: bool = True) -> dict:
        return super().model_dump(exclude_none=exclude_none)


def pcs_openai(models: dict[str, list[str]] | None, explicit: bool) -> PlatformCandidateSet:
    """Build a PlatformCandidateSet for the 'openai' platform.

    - models: provider->names allowlist, or None for implicit allowlist
    - explicit: whether the models key was explicitly provided in inbound payload
    """
    params = DummyOpenAIParams(models=models)
    return PlatformCandidateSet(config=params, explicit_allowlist=explicit)


def mock_arch_entrypoints(monkeypatch, items: list[tuple[str, str, str]]):
    """Mock available agent architecture entry points.

    items: list of tuples (entrypoint_name, module_path, version_string).
    Each item yields an entry point and a module with __version__ set accordingly.
    """

    # Prepare fake entry points
    class _EP:
        def __init__(self, name: str, module_path: str) -> None:
            self.name = name
            self.value = f"{module_path}:Architecture"

    eps = [_EP(name, module) for (name, module, _ver) in items]

    import importlib.metadata as importlib_metadata

    def fake_entry_points(group=None):
        if group == "agent_platform.architectures":
            return eps
        return []

    monkeypatch.setattr(importlib_metadata, "entry_points", fake_entry_points)

    # Prepare fake modules for import_module
    module_map = {module: types.SimpleNamespace(__version__=ver) for (_n, module, ver) in items}

    import importlib as importlib_pkg

    def fake_import_module(module_path):
        return module_map[module_path]

    monkeypatch.setattr(importlib_pkg, "import_module", fake_import_module)


def pcs(kind: str, models: dict[str, list[str]] | None, explicit: bool) -> PlatformCandidateSet:
    """Generic helper to build PlatformCandidateSet for supported kinds."""
    if kind == "openai":
        return pcs_openai(models, explicit)
    if kind == "bedrock":
        params = DummyBedrockParams(models=models)
        return PlatformCandidateSet(config=params, explicit_allowlist=explicit)
    raise AssertionError(f"Unsupported kind in tests: {kind}")


@pytest.mark.unit
def test_returns_preferred_when_already_compatible():
    """If the preferred arch satisfies constraints, it is returned unchanged."""
    preferred = AgentArchitecture(
        name="agent_platform.architectures.default",
        version="1.0.0",
    )

    # Explicit allowlist to a model without arch override requirements
    pcs = pcs_openai(models={"openai": ["gpt-4-1"]}, explicit=True)

    resolved = resolve_architecture(
        preferred,
        [pcs],
        cfg_provider=PlatformModelConfigs,  # use real configs
    )
    assert resolved == preferred


@pytest.mark.unit
def test_adjusts_architecture_via_entrypoints_when_incompatible(monkeypatch):
    """When preferred arch is incompatible, pick a compatible one from entry points."""
    preferred = AgentArchitecture(
        name="agent_platform.architectures.default",
        version="1.0.0",
    )

    # Model that requires experimental_1==2.0.0 per PlatformModelConfigs
    params = DummyOpenAIParams(models={"openai": ["gpt-5-medium"]})
    pcs = PlatformCandidateSet(config=params, explicit_allowlist=True)

    # Fake an entry point exposing experimental_1 with version 2.0.0
    mock_arch_entrypoints(
        monkeypatch,
        [("agent_platform.architectures.experimental_1", "fake_module", "2.0.0")],
    )

    resolved = resolve_architecture(
        preferred,
        [pcs],
        cfg_provider=PlatformModelConfigs,
    )

    assert resolved == AgentArchitecture(
        name="agent_platform.architectures.experimental_1",
        version="2.0.0",
    )


@pytest.mark.unit
def test_raises_when_no_compatible_architecture_found(monkeypatch):
    """If no entry point provides a compatible arch, raise ArchitectureResolutionError."""
    preferred = AgentArchitecture(
        name="agent_platform.architectures.default",
        version="1.0.0",
    )

    # Require experimental_1==2.0.0 via model selection; offered EP has wrong version
    pcs = pcs_openai(models={"openai": ["gpt-5-medium"]}, explicit=True)
    mock_arch_entrypoints(
        monkeypatch,
        [("agent_platform.architectures.experimental_1", "fake_module", "1.9.9")],
    )

    with pytest.raises(ArchitectureResolutionError):
        resolve_architecture(
            preferred,
            [pcs],
            cfg_provider=PlatformModelConfigs,
        )


@pytest.mark.unit
def test_multi_platform_complex_but_compatible(monkeypatch):
    """Two platforms, three models; combined requirements are compatible.

    - openai/openai/gpt-5-medium -> requires experimental_1==2.0.0
    - bedrock/anthropic/claude-4-1-opus-thinking-low -> requires experimental_1==2.0.0
    - bedrock/cohere/command-r-plus -> no special requirement
    """
    preferred = AgentArchitecture(
        name="agent_platform.architectures.default",
        version="1.0.0",
    )

    pcs_openai_cfg = pcs(
        "openai",
        models={"openai": ["gpt-5-medium"]},
        explicit=True,
    )
    pcs_bedrock_cfg = pcs(
        "bedrock",
        models={
            "anthropic": ["claude-4-1-opus-thinking-low"],
            "cohere": ["command-r-plus"],
        },
        explicit=True,
    )

    # Provide an experimental architecture that satisfies all constraints
    mock_arch_entrypoints(
        monkeypatch,
        [("agent_platform.architectures.experimental_1", "fake_module", "2.0.0")],
    )

    resolved = resolve_architecture(
        preferred,
        [pcs_openai_cfg, pcs_bedrock_cfg],
        cfg_provider=PlatformModelConfigs,
    )

    assert resolved == AgentArchitecture(
        name="agent_platform.architectures.experimental_1",
        version="2.0.0",
    )


@pytest.mark.unit
def test_adjusts_with_implicit_allowlist(monkeypatch):
    """With implicit allowlist (no models key), resolver still finds a compatible arch.

    Because openai platform has models that require the experimental architecture,
    the preferred default arch is incompatible and must be adjusted via entry points.
    """
    preferred = AgentArchitecture(
        name="agent_platform.architectures.default",
        version="1.0.0",
    )

    # No explicit allowlist; consider all models for the 'openai' platform
    pcs = pcs_openai(models=None, explicit=False)

    # Provide a compatible experimental architecture via entry points
    mock_arch_entrypoints(
        monkeypatch,
        [("agent_platform.architectures.experimental_1", "fake_module", "2.0.0")],
    )

    resolved = resolve_architecture(
        preferred,
        [pcs],
        cfg_provider=PlatformModelConfigs,
    )

    assert resolved == AgentArchitecture(
        name="agent_platform.architectures.experimental_1",
        version="2.0.0",
    )


@pytest.mark.unit
def test_conflicting_requirements_across_allowlist_raise(monkeypatch):
    """Two allowlisted models requiring conflicting versions cause a resolution error."""
    preferred = AgentArchitecture(
        name="agent_platform.architectures.default",
        version="1.0.0",
    )

    # Allowlist two models from different providers within the same platform
    pcs = pcs_openai(models={"p1": ["mA"], "p2": ["mB"]}, explicit=True)

    # Custom minimal configs defining two generic IDs and conflicting arch overrides
    custom_cfg = PlatformModelConfigs(
        models_to_platform_specific_model_ids={
            "openai/p1/mA": "mA-id",
            "openai/p2/mB": "mB-id",
        },
        models_to_architecture_overrides={
            "openai/p1/mA": ["agent_platform.architectures.experimental_1==2.0.0"],
            "openai/p2/mB": ["agent_platform.architectures.experimental_1==3.0.0"],
        },
    )

    # Only provide experimental_1 at version 2.0.0 via entry points (still incompatible overall)
    mock_arch_entrypoints(
        monkeypatch,
        [("agent_platform.architectures.experimental_1", "fake_module", "2.0.0")],
    )

    with pytest.raises(ArchitectureResolutionError):
        resolve_architecture(
            preferred,
            [pcs],
            cfg_provider=lambda: custom_cfg,
        )


@pytest.mark.unit
def test_range_requirements_resolve_to_highest(monkeypatch):
    """Conflicting ranges (>=2.0.0 and >=3.0.0) resolve to the higher compatible version."""
    preferred = AgentArchitecture(
        name="agent_platform.architectures.default",
        version="1.0.0",
    )

    # Allow two models under the same platform; each imposes a minimum version
    pcs_cfg = pcs_openai(models={"p1": ["mA"], "p2": ["mB"]}, explicit=True)

    # Custom config with range specifiers
    custom_cfg = PlatformModelConfigs(
        models_to_platform_specific_model_ids={
            "openai/p1/mA": "mA-id",
            "openai/p2/mB": "mB-id",
        },
        models_to_architecture_overrides={
            "openai/p1/mA": ["agent_platform.architectures.experimental_1>=2.0.0"],
            "openai/p2/mB": ["agent_platform.architectures.experimental_1>=3.0.0"],
        },
    )

    # Provide two candidate versions; first is insufficient (2.5.0), second satisfies both (3.1.0)
    mock_arch_entrypoints(
        monkeypatch,
        [
            ("agent_platform.architectures.experimental_1", "mod_v2", "2.5.0"),
            ("agent_platform.architectures.experimental_1", "mod_v3", "3.1.0"),
        ],
    )

    resolved = resolve_architecture(
        preferred,
        [pcs_cfg],
        cfg_provider=lambda: custom_cfg,
    )

    assert resolved == AgentArchitecture(
        name="agent_platform.architectures.experimental_1",
        version="3.1.0",
    )
