import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.platforms.configs import PlatformModelConfigs


@dataclass(frozen=True)
class PlatformCandidateSet:
    """Wrapper for a single platform config and how to compute candidate models.

    - config: normalized PlatformParameters
    - explicit_allowlist: whether user explicitly provided an allowlist (models key) in payload
    """

    config: PlatformParameters
    explicit_allowlist: bool


def _parse_arch_requirement(requirement: str) -> tuple[str, str]:
    import re

    m = re.match(r"^([A-Za-z0-9_.-]+)\s*(.*)$", requirement.strip())
    if not m:
        raise ArchitectureResolutionError(f"Invalid architecture requirement: {requirement}")
    name, spec = m.group(1), m.group(2).strip()
    return name, spec


def _arch_requirement_matches(arch: AgentArchitecture, requirement: str) -> bool:
    name, spec = _parse_arch_requirement(requirement)
    if arch.name != name:
        return False
    if not spec:
        return True
    try:
        specs = SpecifierSet(spec)
    except Exception as e:
        raise ArchitectureResolutionError(
            f"Invalid architecture requirement specifier: {requirement}"
        ) from e
    return specs.contains(Version(arch.version), prereleases=True)


def _candidate_models_for_config(
    cfg: PlatformModelConfigs,
    pcs: PlatformCandidateSet,
) -> set[str]:
    candidates: set[str] = set()
    config = pcs.config
    if pcs.explicit_allowlist and config.models:
        for provider, model_list in (config.models or {}).items():
            for model_name in model_list or []:
                candidates.add(f"{config.kind}/{provider}/{model_name}")
    else:
        for generic_id in cfg.models_to_platform_specific_model_ids.keys():
            if generic_id.startswith(f"{config.kind}/"):
                candidates.add(generic_id)
    return candidates


def _arch_satisfies_all_configs(
    arch: AgentArchitecture,
    platform_sets: Iterable[PlatformCandidateSet],
    cfg: PlatformModelConfigs,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for pcs in platform_sets:
        candidates = _candidate_models_for_config(cfg, pcs)
        if not candidates:
            continue
        incompatible: list[tuple[str, list[str]]] = []
        for generic_id in candidates:
            reqs = cfg.models_to_architecture_overrides.get(generic_id, [])
            if not reqs:
                continue
            if not any(_arch_requirement_matches(arch, r) for r in reqs):
                incompatible.append((generic_id, reqs))
        if incompatible:
            errors.append(
                f"kind={pcs.config.kind} architecture {arch.name}=={arch.version} "
                f" fails conjunction for {len(incompatible)} model(s); examples: {incompatible[:3]}"
            )
    return (len(errors) == 0, errors)


def resolve_architecture(
    preferred_arch: AgentArchitecture,
    platform_sets: list[PlatformCandidateSet],
    *,
    cfg_provider: Callable[[], PlatformModelConfigs] | PlatformModelConfigs | None = None,
) -> AgentArchitecture:
    """Resolve a compatible architecture given constraints across platform configs.

    Tries preferred_arch first. If incompatible, scans installed architectures exposed via
    entry points (agent_platform.architectures). Returns the first compatible candidate.
    Raises ValueError when no compatible architecture can be found.
    """
    logger = logging.getLogger(__name__)

    cfg = cfg_provider() if callable(cfg_provider) else (cfg_provider or PlatformModelConfigs())

    ok, _ = _arch_satisfies_all_configs(preferred_arch, platform_sets, cfg)
    if ok:
        return preferred_arch

    # Try installed architectures via entrypoints
    try:
        from importlib import import_module
        from importlib.metadata import entry_points
    except Exception:  # pragma: no cover
        entry_points = None  # type: ignore
        import_module = None  # type: ignore

    if entry_points is not None and import_module is not None:
        try:
            eps = entry_points(group="agent_platform.architectures")
        except TypeError:
            eps = []
        for ep in eps:
            try:
                module_path = ep.value.split(":", 1)[0]
                mod = import_module(module_path)
                version = getattr(mod, "__version__", None)
                if not isinstance(version, str):
                    continue
                candidate = AgentArchitecture(name=ep.name, version=version)
                ok, _errs = _arch_satisfies_all_configs(candidate, platform_sets, cfg)
                if ok:
                    logger.info(
                        "Agent architecture adjusted to satisfy platform model requirements",
                        extra={
                            "from_arch": preferred_arch.model_dump(),
                            "to_arch": candidate.model_dump(),
                        },
                    )
                    return candidate
            except Exception:
                continue

    # No path forward
    _, errors = _arch_satisfies_all_configs(preferred_arch, platform_sets, cfg)
    raise ArchitectureResolutionError(
        "No compatible architecture found across platform configs; tried provided "
        f"architecture {preferred_arch.name}=={preferred_arch.version}. Details: {errors}",
        data={
            "preferred_arch": preferred_arch.model_dump(),
            "errors": errors,
        },
    )


class ArchitectureResolutionError(PlatformHTTPError):
    """Raised when no compatible agent architecture can be resolved for constraints."""

    def __init__(self, message: str, data: dict | None = None) -> None:
        super().__init__(ErrorCode.BAD_REQUEST, message=message, data=data)
