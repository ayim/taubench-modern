import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from httpx import AsyncClient

from agent_platform.core.work_items import WorkItemStatus


class CallbackServer:
    """A test HTTP server that captures callback requests."""

    def __init__(self, statuses: list[str]):
        self.statuses = statuses
        self.requests: list[dict[str, Any]] = []
        self.events: dict[str, threading.Event] = {status: threading.Event() for status in statuses}
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.url: str = ""

    def start(self) -> None:
        """Start the callback server."""
        callback_server = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                # Only accept requests to the /webhook path
                if self.path != "/webhook":
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Not found"}')
                    return

                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                request_data = {
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": json.loads(body),
                }
                callback_server.requests.append(request_data)

                # Signal the appropriate event based on status
                status = request_data["body"].get("status")
                if status in callback_server.events:
                    callback_server.events[status].set()

                # Send response
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "received"}')

            def log_message(self, format, *args):  # noqa: A002
                # Suppress HTTP server logs during tests
                pass

        self.server = HTTPServer(("localhost", 0), CallbackHandler)
        port = self.server.server_address[1]
        self.url = f"http://localhost:{port}/webhook"

        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def stop(self) -> None:
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for(self, status: str, timeout: float = 30.0) -> bool:
        """Wait for a callback with the specified status."""
        if status not in self.events:
            raise ValueError(f"Status {status} not configured for this server")
        return self.events[status].wait(timeout)

    def get_requests_for_status(self, status: str) -> list[dict[str, Any]]:
        """Get all requests received for a specific status."""
        return [req for req in self.requests if req["body"].get("status") == status]

    def single_request(self) -> dict[str, Any]:
        """Get the single request (raises if not exactly one)."""
        if len(self.requests) != 1:
            raise AssertionError(f"Expected exactly 1 request, got {len(self.requests)}")
        return self.requests[0]


@pytest.fixture
def callback_server():
    """Factory fixture for creating callback servers."""
    servers = []

    def _create_server(statuses: list[str]) -> CallbackServer:
        server = CallbackServer(statuses)
        server.start()
        servers.append(server)
        return server

    yield _create_server

    # Cleanup
    for server in servers:
        server.stop()


@pytest.fixture
def agent_factory(base_url_agent_server_with_work_items: str, openai_api_key: str):
    """Factory fixture for creating agents."""
    agents = []

    def _create_agent(
        runbook: str = "You are a helpful assistant.",
        platform_configs: list[dict[str, Any]] | None = None,
    ) -> str:
        if platform_configs is None:
            platform_configs = [{"kind": "openai", "openai_api_key": openai_api_key}]

        client = AgentServerClient(base_url_agent_server_with_work_items)
        agent_id = client.create_agent_and_return_agent_id(
            platform_configs=platform_configs,
            runbook=runbook,
        )
        agents.append((client, agent_id))
        return agent_id

    yield _create_agent

    # Cleanup - agents are cleaned up when the client context manager exits
    for client, _ in agents:
        client.__exit__(None, None, None)


class WorkItemPoller:
    """Helper for polling work item status."""

    def __init__(self, client: AsyncClient, work_item_id: str):
        self.client = client
        self.work_item_id = work_item_id

    async def wait_for_status(self, target_status: str, timeout: float = 120.0) -> None:
        """Wait for the work item to reach the target status."""

        async def _check_status():
            resp = await self.client.get(f"/{self.work_item_id}")
            assert resp.status_code == 200
            status = WorkItemStatus(resp.json()["status"])
            return status.value == target_status

        await self._wait_until(_check_status, timeout=timeout)

    async def wait_for_final_status(self, timeout: float = 120.0) -> str:
        """Wait for the work item to reach any final status and return it."""

        async def _check_final():
            resp = await self.client.get(f"/{self.work_item_id}")
            assert resp.status_code == 200
            status = WorkItemStatus(resp.json()["status"])
            return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

        await self._wait_until(_check_final, timeout=timeout)

        # Get the final status
        resp = await self.client.get(f"/{self.work_item_id}")
        return WorkItemStatus(resp.json()["status"]).value

    async def _wait_until(self, condition, timeout: float = 120.0) -> None:
        """Wait until condition returns True or timeout expires."""
        import time

        start = time.time()
        while True:
            if await condition():
                return
            if time.time() - start > timeout:
                raise TimeoutError("Condition not met before timeout")
            await asyncio.sleep(1.0)


@pytest.fixture
def work_item_factory(base_url_agent_server_with_work_items: str):
    """Factory fixture for creating work items."""

    async def _create_work_item(
        agent_id: str,
        messages: list[dict[str, Any]],
        callbacks: list[dict[str, Any]] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[str, WorkItemPoller]:
        if payload is None:
            payload = {"workflow": "test"}

        work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

        async with AsyncClient(base_url=work_items_url) as client:
            request_data = {
                "agent_id": agent_id,
                "messages": messages,
                "payload": payload,
            }
            if callbacks:
                request_data["callbacks"] = callbacks

            resp = await client.post("/", json=request_data)
            assert resp.status_code == 200
            work_item_id = resp.json()["work_item_id"]

            # Return work_item_id and a poller that uses a new client
            # (since the current client will be closed when this function returns)
            return work_item_id, WorkItemPoller(AsyncClient(base_url=work_items_url), work_item_id)

    return _create_work_item


async def wait_for_callback(event: threading.Event, timeout: float = 30.0) -> bool:
    """Wait for a callback event with the specified timeout."""
    return event.wait(timeout)
