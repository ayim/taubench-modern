#!/usr/bin/env python3
"""Thin wrapper around tau2.cli that stubs gymnasium and wires custom agents."""

from __future__ import annotations

import atexit
import importlib
import os
import sys
import types
from pathlib import Path
from typing import Any, ClassVar

RUNNER_DIR = Path(__file__).resolve().parent
DEFAULT_AGENT_SERVER_ROOT = RUNNER_DIR / ".agent-server"
_AGENT_SERVER_STATE: dict[str, Any] = {"process": None, "ws_url": None}


def _ensure_gymnasium_stub() -> None:
    """Install a minimal gymnasium stub if the package is not available."""
    try:
        importlib.import_module("gymnasium")
        return
    except ModuleNotFoundError:
        pass

    stub = types.ModuleType("gymnasium")

    class _Space:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def sample(self, *args, **kwargs):
            raise RuntimeError(
                "gymnasium is not installed. Install gymnasium to use RL/Gym features."
            )

        def contains(self, *_args, **_kwargs):
            return False

    class _Env:
        metadata: ClassVar[dict[str, Any]] = {}

        def __init__(self, *args, **kwargs) -> None:
            pass

        def reset(self, *args, **kwargs):
            raise RuntimeError(
                "gymnasium is not installed. Install gymnasium to use RL/Gym features."
            )

        def step(self, *args, **kwargs):
            raise RuntimeError(
                "gymnasium is not installed. Install gymnasium to use RL/Gym features."
            )

        def close(self):
            return None

    spaces_module = types.ModuleType("gymnasium.spaces")
    spaces_module.Space = _Space  # type: ignore

    registration_module = types.ModuleType("gymnasium.envs.registration")

    def _register(*args, **kwargs):
        raise RuntimeError("gymnasium is not installed. Install gymnasium to use RL/Gym features.")

    registration_module.register = _register  # type: ignore

    envs_module = types.ModuleType("gymnasium.envs")
    envs_module.registration = registration_module  # type: ignore

    stub.spaces = spaces_module  # type: ignore
    stub.Env = _Env  # type: ignore
    stub.envs = envs_module  # type: ignore

    sys.modules["gymnasium"] = stub
    sys.modules["gymnasium.spaces"] = spaces_module
    sys.modules["gymnasium.envs"] = envs_module
    sys.modules["gymnasium.envs.registration"] = registration_module


def main() -> None:
    agent_spec = _extract_agent_spec(sys.argv[1:])
    if agent_spec and agent_spec.startswith("sema4ai"):
        ws_url = _ensure_sema4ai_base_url()
        if ws_url:
            _maybe_register_sema4ai_agent(agent_spec, ws_url)

    _ensure_gymnasium_stub()
    from tau2.cli import main as tau2_main  # type: ignore

    tau2_main()


def _extract_agent_spec(argv: list[str]) -> str | None:
    for idx, arg in enumerate(argv):
        if arg == "--agent" and idx + 1 < len(argv):
            return argv[idx + 1]
        if arg.startswith("--agent="):
            return arg.split("=", 1)[1]
    return os.getenv("TAU2_AGENT")


def _ensure_sema4ai_base_url() -> str | None:
    existing = os.getenv("SEMA4AI_BASE_URL")
    if existing:
        return existing

    if not _bootstrap_enabled():
        raise RuntimeError(
            "SEMA4AI_BASE_URL is required when using the Sema4AI agent shim. "
            "Set TAU2_BOOTSTRAP_AGENT_SERVER=true to auto-start the local agent server."
        )

    return _start_local_agent_server()


def _bootstrap_enabled() -> bool:
    raw = (os.getenv("TAU2_BOOTSTRAP_AGENT_SERVER") or "true").strip().lower()
    return raw not in {"0", "false", "no"}


def _start_local_agent_server() -> str:
    if _AGENT_SERVER_STATE["ws_url"]:
        return _AGENT_SERVER_STATE["ws_url"]

    try:
        from agent_platform.orchestrator.bootstrap_agent_server import AgentServerProcess
    except Exception as exc:  # pragma: no cover - guard rails
        raise RuntimeError(
            "Failed to import AgentServerProcess; ensure the workspace dependencies are synced."
        ) from exc

    data_root = Path(os.getenv("TAU2_AGENTSERVER_HOME", str(DEFAULT_AGENT_SERVER_ROOT)))
    data_dir = data_root / "data"
    logs_dir = data_root / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    server_process = AgentServerProcess(datadir=data_dir)
    server_process.SHOW_OUTPUT = False  # type: ignore[assignment]
    server_process.start(logs_dir=logs_dir)

    ws_url = f"ws://{server_process.host}:{server_process.port}"
    os.environ.setdefault("SEMA4AI_BASE_URL", ws_url)
    _AGENT_SERVER_STATE["process"] = server_process
    _AGENT_SERVER_STATE["ws_url"] = ws_url
    atexit.register(_stop_agent_server)
    return ws_url


def _stop_agent_server() -> None:
    process = _AGENT_SERVER_STATE.get("process")
    if process is not None:
        try:
            process.stop()
        finally:
            _AGENT_SERVER_STATE["process"] = None


def _maybe_register_sema4ai_agent(agent_spec: str, ws_url: str) -> None:
    try:
        from sema4_agent_shim import register_sema4ai_agent
    except ImportError as exc:  # pragma: no cover - shim dependency guard
        raise RuntimeError(
            "Failed to import the Sema4AI agent shim. "
            "Run 'uv pip install --python .venv/bin/python -e .'"
        ) from exc

    register_sema4ai_agent(agent_spec, ws_url=ws_url)


if __name__ == "__main__":
    main()
