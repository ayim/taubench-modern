"""Stress test for SQLAlchemy-backed endpoints to catch sqlite commit-in-progress errors."""

import concurrent.futures
import http
import random
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import requests
from agent_platform.orchestrator.agent_server_client import AgentServerClient


@dataclass(slots=True)
class Workload:
    name: str
    fn: Callable[[], tuple[int, str]]


def _run_request(fn: Callable[[], requests.Response]) -> tuple[int, str]:
    try:
        response = fn()
    except Exception as exc:
        return 0, f"exception: {exc}"
    return response.status_code, response.text


def _scenario_create_workload(base_url: str, thread_id: str) -> Callable[[], tuple[int, str]]:
    def _fn() -> tuple[int, str]:
        payload = {
            "name": f"scenario-{time.time_ns()}",
            "description": "load test scenario",
            "thread_id": thread_id,
        }
        return _run_request(
            lambda: requests.post(
                f"{base_url}/api/v2/evals/scenarios",
                json=payload,
                timeout=20,
            )
        )

    return _fn


def _scenario_list_workload(base_url: str) -> Callable[[], tuple[int, str]]:
    def _fn() -> tuple[int, str]:
        params = {"limit": random.randint(1, 10)}
        time.sleep(random.uniform(0, 0.015))
        return _run_request(
            lambda: requests.get(
                f"{base_url}/api/v2/evals/scenarios",
                params=params,
                timeout=15,
            )
        )

    return _fn


def _data_connection_update_workload(
    base_url: str, base_connection: dict[str, Any]
) -> Callable[[], tuple[int, str]]:
    def _fn() -> tuple[int, str]:
        idx = str(uuid.uuid4())
        payload = {
            "id": base_connection["id"],
            "name": f"{base_connection['name']}-{idx}",
            "description": f"{base_connection['description']} update {idx[:8]}",
            "engine": base_connection["engine"],
            "configuration": base_connection["configuration"],
            "created_at": base_connection.get("created_at"),
            "updated_at": base_connection.get("updated_at"),
            "external_id": base_connection.get("external_id"),
        }
        time.sleep(random.uniform(0, 0.02))
        return _run_request(
            lambda: requests.put(
                f"{base_url}/api/v2/data-connections/{base_connection['id']}",
                json=payload,
                timeout=15,
            )
        )

    return _fn


def _create_scenario(base_url: str, thread_id: str) -> dict[str, Any]:
    payload = {
        "name": f"repro-scenario-{int(time.time() * 1000)}",
        "description": "scenario for sqlite repro",
        "thread_id": thread_id,
    }
    response = requests.post(
        f"{base_url}/api/v2/evals/scenarios",
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _run_workloads(
    workloads: list[Workload], *, max_workers: int = 50
) -> list[tuple[str, int, str]]:
    errors: list[tuple[str, int, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(workload.fn) for workload in workloads]
        for workload, future in zip(
            workloads, concurrent.futures.as_completed(futures), strict=False
        ):
            status, text = future.result()
            if status >= http.HTTPStatus.INTERNAL_SERVER_ERROR or status == 0:
                errors.append((workload.name, status, text))
    return errors


def _collect_log_hits(log_dir: Path, signature: str) -> int:
    hits = 0
    inspected_files = 0
    for log_path in log_dir.glob("agent_server*.log*"):
        if not log_path.is_file():
            continue
        inspected_files += 1
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        hits += text.count(signature)

    if inspected_files == 0:
        raise AssertionError(f"No log files found in {log_dir!s}; cannot verify signature")

    return hits


@pytest.mark.parametrize(
    ("create_count", "list_count", "update_count"),
    [(200, 400, 200)],
)
def test_sqlalchemy_commit_in_progress(  # noqa: PLR0913
    base_url_agent_server_evals_sqlite: str,
    agent_factory,
    logs_dir: Path,
    tmp_path: Path,
    create_count: int,
    list_count: int,
    update_count: int,
):
    agent_id = agent_factory()
    client = AgentServerClient(base_url_agent_server_evals_sqlite)
    thread_id = client.create_thread_and_return_thread_id(agent_id)
    data_connection = client.create_data_connection(
        name=f"repro-sqlite-{time.time_ns()}",
        description="repro data connection",
        engine="sqlite",
        configuration={"db_file": str(tmp_path / f"repro-{time.time_ns()}.db")},
    )

    _create_scenario(base_url_agent_server_evals_sqlite, thread_id)

    workloads: list[Workload] = []

    for _ in range(create_count):
        workloads.append(
            Workload(
                "scenario-create",
                _scenario_create_workload(base_url_agent_server_evals_sqlite, thread_id),
            )
        )
    for _ in range(list_count):
        workloads.append(
            Workload(
                "scenario-list",
                _scenario_list_workload(base_url_agent_server_evals_sqlite),
            )
        )
    for _ in range(update_count):
        workloads.append(
            Workload(
                "data-connection-update",
                _data_connection_update_workload(
                    base_url_agent_server_evals_sqlite,
                    data_connection,
                ),
            )
        )

    random.shuffle(workloads)
    errors = _run_workloads(workloads, max_workers=60)

    signature = "cannot commit transaction - SQL statements in progress"
    http_hits = [error for error in errors if signature in error[2]]
    log_hits = _collect_log_hits(logs_dir, signature)

    assert not http_hits, "Detected SQLite commit-in-progress errors in HTTP responses"
    assert log_hits == 0, "Detected SQLite commit-in-progress errors in logs"
