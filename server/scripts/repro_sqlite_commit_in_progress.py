#!/usr/bin/env python3
"""
Reproduce sqlite3.OperationalError: cannot commit transaction - SQL statements in progress

This script targets a server already running at http://localhost:8000 and
then hammers thread APIs with concurrent creates, updates, and list calls to
provoke the issue observed in agent-server.log.*.

Run with:
  uv run --project agent_platform_server python server/scripts/repro_sqlite_commit_in_progress.py
"""

import concurrent.futures
import http
import random
import time
from pathlib import Path
from typing import Any

import requests
from agent_platform.orchestrator.agent_server_client import AgentServerClient


def ensure_server_up(base_url: str) -> None:
    try:
        r = requests.get(f"{base_url}/api/v2/ok", timeout=5)
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(
            f"Server not reachable at {base_url}. Start the debug server on port 8000 and retry."
        ) from e


def create_agent(base_url: str) -> str:
    client = AgentServerClient(base_url)
    # Provide a minimal platform config; not used during this repro
    agent_id = client.create_agent_and_return_agent_id(
        name=f"repro-{int(time.time() * 1000)}",
        runbook="# Objective\nYou are a helpful assistant.",
        platform_configs=[{"kind": "openai", "openai_api_key": "test"}],
    )
    return agent_id


def create_thread(base_url: str, agent_id: str) -> str:
    url = f"{base_url}/api/v2/threads/"
    r = requests.post(
        url,
        json={
            "agent_id": agent_id,
            "name": "repro-thread",
            "messages": [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["thread_id"]


def do_update(base_url: str, agent_id: str, thread_id: str, i: int) -> tuple[int, str]:
    """PUT update on same thread id to trigger ON CONFLICT path in storage."""
    url = f"{base_url}/api/v2/threads/{thread_id}"
    payload = {
        "agent_id": agent_id,
        "name": f"repro-update-{i}",
        "messages": [{"role": "user", "content": [{"type": "input_text", "text": f"u{i}"}]}],
    }
    # Small random jitter to produce interleavings
    time.sleep(random.uniform(0, 0.02))
    r = requests.put(url, json=payload, timeout=15)
    return r.status_code, r.text


def do_create(base_url: str, agent_id: str, i: int) -> tuple[int, str]:
    url = f"{base_url}/api/v2/threads/"
    payload = {
        "agent_id": agent_id,
        "name": f"repro-new-{i}",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": f"m-{i}"}],
            }
        ],
    }
    r = requests.post(url, json=payload, timeout=15)
    return r.status_code, r.text


def do_list(base_url: str, agent_id: str) -> tuple[int, str]:
    """List threads for agent; this calls the UDF in WHERE clause."""
    url = f"{base_url}/api/v2/threads/?agent_id={agent_id}"
    # Small random jitter to mix with writes
    time.sleep(random.uniform(0, 0.02))
    r = requests.get(url, timeout=15)
    return r.status_code, r.text


def main() -> int:  # noqa: C901, PLR0912
    base = "http://localhost:8000"
    ensure_server_up(base)
    print(f"Hitting server at {base}")

    agent_id = create_agent(base)
    print(f"Created agent: {agent_id}")

    # Create base thread that we'll repeatedly update via PUT to hit ON CONFLICT
    tid = create_thread(base, agent_id)
    print(f"Base thread: {tid}")

    # Build workloads
    n_updates = 1000
    n_creates = 500
    n_lists = 1500
    work: list[tuple[str, tuple[Any, ...]]] = []
    for i in range(n_updates):
        work.append(("update", (base, agent_id, tid, i)))
    for i in range(n_creates):
        work.append(("create", (base, agent_id, i)))
    for _ in range(n_lists):
        work.append(("list", (base, agent_id)))

    random.shuffle(work)

    errors: list[tuple[str, int, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
        futs = []
        for kind, args in work:
            if kind == "update":
                futs.append(ex.submit(do_update, *args))
            elif kind == "create":
                futs.append(ex.submit(do_create, *args))
            else:
                futs.append(ex.submit(do_list, *args))

        for kind, fut in zip(
            (k for k, _ in work), concurrent.futures.as_completed(futs), strict=True
        ):
            try:
                status, text = fut.result()
            except Exception as e:
                errors.append((kind, 0, f"exception: {e}"))
                continue
            if status >= http.HTTPStatus.INTERNAL_SERVER_ERROR:
                errors.append((kind, status, text))

    print(f"Total ops: {len(work)}, server errors: {len(errors)}")
    sample = errors[:5]
    for i, (kind, status, text) in enumerate(sample):
        print(f"[{i}] kind={kind} status={status} text_snippet={text[:200]!r}")

    # Look specifically for the sqlite commit-in-progress error
    sig = "cannot commit transaction - SQL statements in progress"
    hits = [e for e in errors if sig in e[2]]

    # Also scan common local log files if present
    file_hits = 0
    log_candidates = [
        Path("agent-server.log"),
        *sorted(Path(".").glob("agent-server.log.*")),
        Path("logs/agent_server-stderr.log"),
    ]
    for log_path in log_candidates:
        if not log_path.exists():
            continue
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
            file_hits += text.count(sig)
        except Exception:
            pass

    total_hits = len(hits) + file_hits
    print(
        f"Found commit-in-progress occurrences: {total_hits} "
        f"(http body: {len(hits)}, logs: {file_hits})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
