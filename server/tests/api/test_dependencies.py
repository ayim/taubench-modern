from datetime import UTC, datetime
from urllib.parse import urlparse

import pytest
from starlette.requests import Request

from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent import ActionPackage, AgentArchitecture, Runbook
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import (
    PersistenceMode,
    _is_docint_rag_agent,
    _persistence_mode,
)


@pytest.fixture
def mock_request(
    base_url: str = "http://localhost:8000",
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 80)

    raw_headers: list[tuple[bytes, bytes]] = []
    hdrs = {"host": f"{host}:{port}", **(headers or {})}
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        hdrs["cookie"] = cookie_header
    for k, v in hdrs.items():
        raw_headers.append((k.lower().encode("utf-8"), str(v).encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("testclient", 50000),
        "server": (host, port),
        "app": object(),
    }
    return Request(scope)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Test Agent", False),
        ("Document Insights", True),
        ("Document Intelligence", True),
        ("Document Intelligence 2", False),
    ],
)
def test_is_docint_rag_agent(name, expected):
    """We try to determine if an agent is one of our "RAG" agents via action package name."""
    action_package = ActionPackage(
        name=name,
        organization="Sema4.ai",
        version="1.0.0",
        url="https://document-intelligence.com",
        api_key=SecretString("test"),
        allowed_actions=["foo", "bar"],
    )
    agent = Agent(
        agent_id="test-agent",
        name="Test Agent",
        description="Test Agent Description",
        action_packages=[action_package],
        user_id="test-user",
        runbook_structured=Runbook(raw_text="Test Agent Runbook", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="test-agent-architecture", version="1.0.0"),
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    assert _is_docint_rag_agent(agent) is expected, f"Expected {expected} for agent {name}"


@pytest.mark.asyncio
async def test_agent_persistence_mode_implied():
    # implied from DIv2 RAG agents
    action_package = ActionPackage(
        name="Document Intelligence",  # This is the bespoke action package name.
        organization="Sema4.ai",
        version="1.0.0",
        url="https://document-intelligence.com",
        api_key=SecretString("test"),
        allowed_actions=["foo", "bar"],
    )
    agent = Agent(
        agent_id="test-agent",
        name="Test Agent",
        description="Test Agent Description",
        action_packages=[action_package],
        user_id="test-user",
        runbook_structured=Runbook(raw_text="Test Agent Runbook", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="test-agent-architecture", version="1.0.0"),
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    assert await _persistence_mode(agent) == PersistenceMode.DATABASE


@pytest.mark.asyncio
async def test_agent_persistence_mode_explicit():
    action_package = ActionPackage(
        name="Some Random Action Package",
        organization="Sema4.ai",
        version="1.0.0",
        url="https://document-intelligence.com",
        api_key=SecretString("test"),
        allowed_actions=["foo", "bar"],
    )
    agent = Agent(
        agent_id="test-agent",
        name="Test Agent",
        description="Test Agent Description",
        action_packages=[action_package],
        user_id="test-user",
        runbook_structured=Runbook(raw_text="Test Agent Runbook", content=[]),
        version="1.0.0",
        platform_configs=[],
        extra={"agent_settings": {"di-persistence": "database"}},
        agent_architecture=AgentArchitecture(name="test-agent-architecture", version="1.0.0"),
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    assert await _persistence_mode(agent) == PersistenceMode.DATABASE

    agent = agent.copy(extra={"agent_settings": {"di-persistence": "file"}})
    assert await _persistence_mode(agent) == PersistenceMode.FILE


@pytest.mark.asyncio
async def test_agent_persistence_mode_default():
    action_package = ActionPackage(
        name="Some Random Action Package",
        organization="Sema4.ai",
        version="1.0.0",
        url="https://document-intelligence.com",
        api_key=SecretString("test"),
        allowed_actions=["foo", "bar"],
    )
    agent = Agent(
        agent_id="test-agent",
        name="Test Agent",
        description="Test Agent Description",
        action_packages=[action_package],
        user_id="test-user",
        runbook_structured=Runbook(raw_text="Test Agent Runbook", content=[]),
        version="1.0.0",
        platform_configs=[],
        extra={"agent_settings": {"di-persistence": "file"}},
        agent_architecture=AgentArchitecture(name="test-agent-architecture", version="1.0.0"),
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    assert await _persistence_mode(agent) == PersistenceMode.FILE
