from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.user import User
from agent_platform.server.api.private_v2.capabilities import (
    router as capabilities_router,
)
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.kernel.tools import AgentServerToolsInterface


@dataclass
class DummyTool:
    name: str
    description: str
    input_schema: dict

    def model_dump(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@pytest.fixture
def stub_user() -> User:
    return User(user_id="00000000-0000-0000-0000-000000000000", sub="tenant:test:user")


@pytest.fixture
def fastapi_app(stub_user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(capabilities_router, prefix="/capabilities")

    app.dependency_overrides[auth_user] = lambda: stub_user
    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app)


@pytest.mark.asyncio
async def test_list_mcp_tools_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    dummy_tool = DummyTool(name="echo", description="", input_schema={})

    async def fake_from_mcp_servers(self, servers, additional_headers=None):
        return [dummy_tool], []

    monkeypatch.setattr(AgentServerToolsInterface, "from_mcp_servers", fake_from_mcp_servers)

    payload = {"mcp_servers": [{"name": "test", "url": "https://example.com"}]}

    resp = client.post("/capabilities/mcp/tools", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {
        "results": [
            {
                "server": {
                    "name": "test",
                    # Default transport is streamable-http
                    "transport": "streamable-http",
                    "url": "https://example.com",
                    "headers": None,
                    "type": "generic_mcp",
                    "command": None,
                    "args": None,
                    "env": None,
                    "cwd": None,
                    "force_serial_tool_calls": False,
                    "mcp_server_metadata": None,
                },
                "tools": [dummy_tool.model_dump()],
                "issues": [],
            }
        ]
    }


@pytest.mark.asyncio
async def test_list_mcp_tools_endpoint_with_different_transport(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    dummy_tool = DummyTool(name="echo", description="", input_schema={})

    async def fake_from_mcp_servers(self, servers, additional_headers=None):
        return [dummy_tool], []

    monkeypatch.setattr(AgentServerToolsInterface, "from_mcp_servers", fake_from_mcp_servers)

    payload = {
        "mcp_servers": [
            {"name": "test", "transport": "stdio", "command": "echo", "args": ["-n", "hello"]},
            {"name": "test2", "url": "http://example.com", "transport": "sse"},
        ],
    }

    resp = client.post("/capabilities/mcp/tools", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {
        "results": [
            {
                "server": {
                    "name": "test",
                    "transport": "stdio",
                    "url": None,
                    "headers": None,
                    "type": "generic_mcp",
                    "command": "echo",
                    "args": ["-n", "hello"],
                    "env": None,
                    "cwd": None,
                    "force_serial_tool_calls": False,
                    "mcp_server_metadata": None,
                },
                "tools": [dummy_tool.model_dump()],
                "issues": [],
            },
            {
                "server": {
                    "name": "test2",
                    "transport": "sse",
                    "url": "http://example.com",
                    "headers": None,
                    "type": "generic_mcp",
                    "command": None,
                    "args": None,
                    "env": None,
                    "cwd": None,
                    "force_serial_tool_calls": False,
                    "mcp_server_metadata": None,
                },
                "tools": [dummy_tool.model_dump()],
                "issues": [],
            },
        ]
    }
