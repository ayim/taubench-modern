import asyncio
import sys
import typing
from collections.abc import Generator

import pytest

from agent_platform.core.mcp.mcp_server import MCPServer

if typing.TYPE_CHECKING:
    from agent_platform.core.agent.agent import Agent
    from agent_platform.core.thread.thread import Thread

# Get storage fixtures.
from server.tests.storage_fixtures import *  # noqa: F403

# setup the event loop globally
if sys.platform == "win32":
    # Fix: psycopg.pool - WARNING: error connecting in 'pool-1': Psycopg cannot use the
    # 'ProactorEventLoop' to run in async mode. Please use a compatible event loop,
    # for instance by setting 'asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())'
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def sample_agent(sample_user_id: str) -> "Agent":
    from datetime import UTC, datetime
    from uuid import uuid4

    from agent_platform.core.actions.action_package import ActionPackage
    from agent_platform.core.agent.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.agent.observability_config import ObservabilityConfig
    from agent_platform.core.agent.question_group import QuestionGroup
    from agent_platform.core.runbook.runbook import Runbook
    from agent_platform.core.utils.secret_str import SecretString

    return Agent(
        user_id=sample_user_id,
        agent_id=str(uuid4()),
        name="Test Agent",
        description="Test Description",
        runbook_structured=Runbook(
            raw_text="# Objective\nYou are a helpful assistant.",
            content=[],
        ),
        version="1.0.0",
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        action_packages=[
            ActionPackage(
                name="test-action-package",
                organization="test-organization",
                version="1.0.0",
                url="https://api.test.com",
                api_key=SecretString("test"),
                allowed_actions=["action_1", "action_2"],
            ),
            ActionPackage(
                name="test-action-package-2",
                organization="test-organization-2",
                version="1.0.0",
                url="https://api.test-2.com",
                api_key=SecretString("test-2"),
                allowed_actions=[],
            ),
        ],
        agent_architecture=AgentArchitecture(
            name="agent-architecture-default-v2",
            version="1.0.0",
        ),
        question_groups=[
            QuestionGroup(
                title="Test Question Group",
                questions=[
                    "Here's one question",
                    "Here's another question",
                ],
            ),
        ],
        observability_configs=[
            ObservabilityConfig(
                type="langsmith",
                api_key="test",
                api_url="https://api.langsmith.com",
                settings={"some_extra_setting": "some_extra_value"},
            ),
        ],
        platform_configs=[],
        extra={"agent_extra": "some_extra_value"},
    )


@pytest.fixture
def sample_thread(
    sample_user_id: str,
    sample_agent: "Agent",
) -> "Thread":
    from datetime import UTC, datetime
    from uuid import uuid4

    from agent_platform.core.thread.base import ThreadMessage, ThreadTextContent
    from agent_platform.core.thread.thread import Thread

    return Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Test Thread",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello, how are you?")],
            ),
            ThreadMessage(
                role="agent",
                content=[ThreadTextContent(text="I'm fine, thank you!")],
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={"thread_metadata": "some_metadata"},
    )


@pytest.fixture
def sample_mcp_server_http() -> MCPServer:
    """Sample MCP server using HTTP transport."""
    return MCPServer(
        name="test-http-server",
        transport="streamable-http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer test-token"},
    )


@pytest.fixture
def sample_mcp_server_stdio() -> MCPServer:
    """Sample MCP server using stdio transport."""
    return MCPServer(
        name="test-stdio-server",
        transport="stdio",
        command="python",
        args=["-m", "mcp_test_server"],
        env={"TEST_ENV": "test_value"},
        cwd="/tmp",
    )


@pytest.fixture
def sample_mcp_server_sse() -> MCPServer:
    """Sample MCP server using SSE transport."""
    return MCPServer(
        name="test-sse-server",
        transport="sse",
        url="https://example.com/sse",
    )


@pytest.fixture(scope="session", autouse=True)
def _disable_logging() -> Generator[None, None, None]:
    """Disable verbose logging for the entire session."""
    from logging import CRITICAL, INFO, getLogger

    getLogger("agent_platform.server.storage.postgres.migrations").setLevel(CRITICAL)
    getLogger("agent_platform.server.storage.postgres.postgres").setLevel(CRITICAL)

    getLogger("agent_platform.storage.sqlite.migrations").setLevel(CRITICAL)
    getLogger("agent_platform.storage.sqlite.sqlite").setLevel(CRITICAL)

    yield

    getLogger("agent_platform.storage.sqlite.migrations").setLevel(INFO)
    getLogger("agent_platform.storage.sqlite.sqlite").setLevel(INFO)

    getLogger("agent_platform.server.storage.postgres.migrations").setLevel(INFO)
    getLogger("agent_platform.server.storage.postgres.postgres").setLevel(INFO)
