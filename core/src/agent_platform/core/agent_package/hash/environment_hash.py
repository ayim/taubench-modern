#!/usr/bin/env python3
"""
RCC Environment Hash Calculator

This module replicates the environment hash calculation algorithm used by RCC
for holotree blueprints. It reads conda.yaml files and calculates the same
hash that RCC would produce.

Repo: https://github.com/Sema4AI/rcc
Entrypoint: https://github.com/Sema4AI/rcc/blob/master/common/algorithms.go#L77

"""

from typing import Any

import yaml

from agent_platform.core.agent_package.hash.blueprint_hash import blueprint_hash


class Dependency:
    """Represents a conda or pip dependency with parsed components."""

    def __init__(self, original: str, name: str = "", qualifier: str = "", versions: str = ""):
        self.original = original
        self.name = name
        self.qualifier = qualifier
        self.versions = versions

    def is_exact(self) -> bool:
        return (len(self.qualifier) + len(self.versions)) > 0

    def same_as(self, right: "Dependency") -> bool:
        return not self.name.startswith("-") and self.name == right.name

    def exactly_same(self, right: "Dependency") -> bool:
        return self.name == right.name and self.qualifier == right.qualifier and self.versions == right.versions

    def choose_specific(self, right: "Dependency") -> "Dependency":
        if not self.same_as(right):
            raise ValueError(f"Not same component: {self.name} vs. {right.name}")
        if self.is_exact() and not right.is_exact():
            return self
        if not self.is_exact() and right.is_exact():
            return right
        if self.exactly_same(right):
            return self
        raise ValueError(f"Wont choose between dependencies: {self.original} vs. {right.original}")

    def representation(self) -> str:
        # Lowercase and cut extras in brackets
        parts = self.name.lower().split("[", 1)
        return parts[0]


class Environment:
    """Represents a conda environment with channels, dependencies, and post-install scripts."""

    def __init__(self):
        self.name: str = ""
        self.prefix: str = ""
        self.channels: list[str] = []
        self.conda: list[Dependency] = []
        self.pip: list[Dependency] = []
        self.post_install: list[str] = []

    def push_channel(self, channel: str):
        """Add a channel if not already present."""
        if channel not in self.channels:
            self.channels.append(channel)

    def push_conda(self, dependency: Dependency):
        """Add a conda dependency using semi-smart push (choose more specific if duplicate)."""
        for idx, existing in enumerate(self.conda):
            if existing.same_as(dependency):
                chosen = existing.choose_specific(dependency)
                self.conda[idx] = chosen
                return
        self.conda.append(dependency)

    def push_pip(self, dependency: Dependency):
        """Add a pip dependency using semi-smart push (choose more specific if duplicate)."""
        for idx, existing in enumerate(self.pip):
            if existing.same_as(dependency):
                chosen = existing.choose_specific(dependency)
                self.pip[idx] = chosen
                return
        self.pip.append(dependency)

    def push_post_install(self, script: str):
        if script not in self.post_install:
            self.post_install.append(script)

    def conda_list(self) -> list[str]:
        """Return conda dependencies as original strings."""
        return [dep.original for dep in self.conda]

    def pip_list(self) -> list[str]:
        """Return pip dependencies as original strings."""
        return [dep.original for dep in self.pip]

    def pip_map(self) -> dict[str, list[str]]:
        """Return pip dependencies in the format expected by conda.yaml."""
        return {"pip": self.pip_list()}

    def as_yaml(self) -> str:
        """Convert environment to normalized YAML format matching RCC's blueprint structure."""
        # Build the internal environment structure that matches RCC's internalEnvironment
        result = {}

        # Only include non-empty fields (omitempty behavior)
        if self.name:
            result["name"] = self.name

        if self.channels:
            result["channels"] = self.channels

        # Dependencies start with conda dependencies
        dependencies = self.conda_list()

        # Add pip dependencies as a map if they exist
        if self.pip:
            dependencies.append(self.pip_map())  # type: ignore[arg-type]

        if dependencies:
            result["dependencies"] = dependencies

        if self.prefix:
            result["prefix"] = self.prefix

        if self.post_install:
            result["rccPostInstall"] = self.post_install

        # Convert to YAML and normalize whitespace
        yaml_content = yaml.dump(result, default_flow_style=False, sort_keys=False)
        return yaml_content.strip()

    def pip_promote(self) -> None:
        """Promote overlapping pip deps to conda and remove them from pip, choosing specificity."""
        removed_indices: list[int] = []
        for p_index, pip_dep in enumerate(self.pip):
            for c_index, conda_dep in enumerate(self.conda):
                if pip_dep.same_as(conda_dep):
                    removed_indices.append(p_index)
                    chosen = conda_dep.choose_specific(pip_dep)
                    self.conda[c_index] = chosen
        # remove marked pip dependencies
        for i, value in enumerate(removed_indices):
            del self.pip[value - i]

    def merge(self, right: "Environment") -> "Environment":
        """Mirror Go's Environment.Merge behavior."""
        result = Environment()
        name_parts = [n for n in (self.name, right.name) if n]
        if name_parts:
            result.name = "+".join(name_parts)

        # channels (dedup, preserve order)
        _append_unique_preserve_order(result.channels, self.channels, right.channels)

        # post install (dedup, preserve order)
        _append_unique_preserve_order(result.post_install, self.post_install, right.post_install)

        # dependencies using push semantics
        for dep in list(self.conda) + list(right.conda):
            result.push_conda(dep)
        for dep in list(self.pip) + list(right.pip):
            result.push_pip(dep)

        # promote pip where overlapping
        result.pip_promote()
        return result


def _parse_dependency(value: str) -> Dependency | None:
    """Parse a dependency string into components (name, qualifier, versions)."""
    import re

    # Pattern from RCC: ^([^<=~!> ]+)\s*(?:([<=~!>]*)\s*(\S+.*?))?$
    pattern = re.compile(r"^([^<=~!> ]+)\s*(?:([<=~!>]*)\s*(\S+.*?))?$")

    trimmed = value.strip()
    match = pattern.match(trimmed)

    if not match:
        return None

    name = match.group(1)
    qualifier = match.group(2) or ""
    versions = match.group(3) or ""

    return Dependency(original=match.group(0), name=name, qualifier=qualifier, versions=versions)


def _append_unique_preserve_order(target: list[str], *sources: list[str]) -> None:
    """Append unique items from sources to target preserving order."""
    seen = set(target)
    for source in sources:
        for item in source:
            if item not in seen:
                seen.add(item)
                target.append(item)


def _push_dependencies(env: Environment, section: dict[str, Any]) -> None:
    """Push conda and pip dependencies from a section mapping into env."""
    for dep in section.get("conda-forge", []) or []:
        parsed = _parse_dependency(dep)
        if parsed:
            env.push_conda(parsed)
    for dep in section.get("pypi", []) or []:
        parsed = _parse_dependency(dep)
        if parsed:
            if parsed.qualifier == "=":
                parsed.original = f"{parsed.name}=={parsed.versions}"
                parsed.qualifier = "=="
            env.push_pip(parsed)


def _read_package_yaml_from_contents(data: dict[str, Any], dev_dependencies: bool) -> Environment:
    env = Environment()
    # default channel
    env.push_channel("conda-forge")

    # dependencies
    deps = data.get("dependencies")
    deps_dict: dict[str, Any] = deps if isinstance(deps, dict) else {}
    _push_dependencies(env, deps_dict)

    # dev-dependencies
    if dev_dependencies:
        dev = data.get("dev-dependencies")
        dev_dict: dict[str, Any] = dev if isinstance(dev, dict) else {}
        _push_dependencies(env, dev_dict)

    # post install
    for script in data.get("post-install", []) or []:
        env.push_post_install(script)

    # normalize (pip promote)
    env.pip_promote()
    return env


def calculate_environment_hash(yaml_files: list[str], dev_dependencies: bool = False) -> tuple[str, str]:
    """
    Calculate the environment hash for given YAML files.

    Args:
        yaml_files: List of conda.yaml or package.yaml file paths
        dev_dependencies: Whether to include dev dependencies

    Returns:
        Tuple of (hash, blueprint_yaml)
    """
    if not yaml_files:
        raise ValueError("At least one YAML file must be provided")

    # Merge multiple files (left-to-right) using Go-like merge
    left_env: Environment | None = None
    right_env: Environment | None = None
    for yaml_file in yaml_files:
        left_env = right_env
        data = yaml.safe_load(yaml_file) or {}

        right_env = _read_package_yaml_from_contents(data, dev_dependencies)
        if left_env is None:
            continue
        right_env = left_env.merge(right_env)
    if right_env is None:
        raise ValueError("Missing environment specification(s).")

    # Convert to blueprint YAML
    blueprint_yaml = right_env.as_yaml()
    blueprint_bytes = blueprint_yaml.encode("utf-8")

    # Calculate hash
    hash_value = blueprint_hash(blueprint_bytes)

    return hash_value, blueprint_yaml
