import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from agent_platform.core.agent_package.package_parsed import AgentPackageParsed
from agent_platform.core.agent_package.upsert_from_package import upsert_agent_from_package
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.payloads.agent_package import (
    AgentPackagePayload,
    AgentPackagePayloadActionServer,
    AgentPackagePayloadLangsmith,
)
from agent_platform.core.selected_tools import SelectedTools
from agent_platform.core.user import User
from agent_platform.core.utils import SecretString
from agent_platform.server.api.package_content_handler import (
    _create_payload_from_form_data,
    _parse_json_payload,
)
from agent_platform.server.api.private_v2.agents import (
    create_agent_from_package,
    update_agent_from_package,
)
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.storage.errors import AgentNotFoundError

# Test data directory
TEST_AGENTS_DIR = Path(__file__).parent / "test-agents"


@pytest.fixture
def mock_user():
    """Mock authenticated user for testing."""
    return User(user_id="test-user-123", sub="tenant:test-tenant:user:test-user")


@pytest.fixture
def mock_storage():
    """Mock storage dependency for testing."""
    storage = AsyncMock()
    storage.upsert_agent = AsyncMock()
    # This mimics the "agent does not yet exist" branch exercised in these tests;
    # the helper under test looks up the agent first and treats the
    # `AgentNotFoundError` as a signal to create a fresh one.
    storage.get_agent = AsyncMock(side_effect=AgentNotFoundError())
    return storage


@pytest.fixture
def sample_agent_spec():
    """Sample agent specification structure that would be returned by
    extract_and_validate_agent_package."""
    return {
        "spec": {
            "agent-package": {
                "spec-version": "v2",
                "agents": [
                    {
                        "name": "Test Agent",
                        "description": "A test agent for package endpoints",
                        "version": "1.0.0",
                        "action-packages": [
                            {
                                "name": "test-action-package",
                                "organization": "test-org",
                                "version": "1.0.0",
                            }
                        ],
                        "metadata": {"mode": "conversational"},
                    }
                ],
            }
        },
        "runbook_text": "# Test Runbook\nYou are a helpful assistant.",
    }


@pytest.fixture
def sample_agent_package_payload():
    """Sample AgentPackagePayload for testing."""
    return AgentPackagePayload(
        name="Test Package Agent",
        agent_package_url="https://example.com/agent-package.zip",
        model={"provider": "OpenAI", "name": "gpt-4"},
        action_servers=[
            AgentPackagePayloadActionServer(
                url="https://action-server.example.com",
                api_key="test-api-key-123",
            )
        ],
        mcp_servers=[MCPServer(name="test-mcp", url="https://mcp.example.com")],
        langsmith=AgentPackagePayloadLangsmith(
            api_key="langsmith-key-123",
            api_url="https://langsmith.example.com",
            project_name="test-project",
        ),
    )


@pytest.fixture
def sample_agent_package_payload_base64():
    """Sample AgentPackagePayload with base64 content for testing."""
    # Create a simple base64 encoded content for testing
    test_content = json.dumps(
        {
            "agent-package": {
                "spec-version": "v2",
                "agents": [
                    {
                        "name": "Base64 Test Agent",
                        "description": "Test agent from base64",
                        "version": "1.0.0",
                        "action-packages": [],
                        "metadata": {"mode": "conversational"},
                    }
                ],
            }
        }
    )
    encoded_content = base64.b64encode(test_content.encode()).decode()

    return AgentPackagePayload(
        name="Base64 Package Agent",
        agent_package_base64=encoded_content,
        model={"provider": "OpenAI", "name": "gpt-4"},
        action_servers=[],
        mcp_servers=[],
    )


@pytest.mark.asyncio
async def test_parse_json_payload_selected_tools_dict():
    body_json = {
        "name": "Selected Tools JSON Agent",
        "selected_tools": {"tool_names": [{"tool_name": "weather"}]},
    }
    body_bytes = json.dumps(body_json).encode()

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope, receive)

    payload = await _parse_json_payload(request, AgentPackagePayload)

    assert isinstance(payload.selected_tools, SelectedTools)
    assert [tool.tool_name for tool in payload.selected_tools.tool_names] == ["weather"]


@pytest.mark.asyncio
async def test_create_payload_from_form_data_selected_tools_str():
    form_data = {
        "name": "Selected Tools Form Agent",
        "selected_tools": json.dumps({"tool_names": ["calendar"]}),
    }

    payload = await _create_payload_from_form_data(AgentPackagePayload, form_data)

    assert isinstance(payload.selected_tools, SelectedTools)
    assert [tool.tool_name for tool in payload.selected_tools.tool_names] == ["calendar"]


@pytest.mark.asyncio
async def test_create_payload_from_form_data_selected_tools_null():
    form_data = {
        "name": "Selected Tools Null Form Agent",
        "selected_tools": json.dumps(None),
    }

    payload = await _create_payload_from_form_data(AgentPackagePayload, form_data)

    assert isinstance(payload.selected_tools, SelectedTools)
    assert payload.selected_tools.tool_names == []


@pytest.mark.asyncio
async def test_parse_json_payload_selected_tools_null():
    body_json = {
        "name": "Selected Tools Null Agent",
        "selected_tools": None,
    }
    body_bytes = json.dumps(body_json).encode()

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope, receive)

    payload = await _parse_json_payload(request, AgentPackagePayload)

    assert isinstance(payload.selected_tools, SelectedTools)
    assert payload.selected_tools.tool_names == []


@pytest.mark.asyncio
async def test_create_payload_from_form_data_selected_tools_invalid_json():
    form_data = {
        "name": "Selected Tools Invalid Form Agent",
        "selected_tools": "not-json",
    }

    with pytest.raises(HTTPException) as exc_info:
        await _create_payload_from_form_data(AgentPackagePayload, form_data)

    assert exc_info.value.status_code == 400
    assert "Invalid JSON for selected_tools" in exc_info.value.detail


@pytest.mark.asyncio
async def test_parse_json_payload_selected_tools_invalid_type():
    body_json = {
        "name": "Selected Tools Invalid JSON Agent",
        "selected_tools": 1234,
    }
    body_bytes = json.dumps(body_json).encode()

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope, receive)

    with pytest.raises(HTTPException) as exc_info:
        await _parse_json_payload(request, AgentPackagePayload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "selected_tools must be an object or null"


@pytest.mark.asyncio
async def test_create_payload_from_form_data_selected_tools_invalid_type():
    form_data = {
        "name": "Selected Tools Invalid Type Agent",
        "selected_tools": json.dumps(1234),
    }

    with pytest.raises(HTTPException) as exc_info:
        await _create_payload_from_form_data(AgentPackagePayload, form_data)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "selected_tools must be an object or null"


class TestCreateAgentFromPackage:
    """Test cases for POST /api/v2/agents/package endpoint."""

    @pytest.mark.asyncio
    async def test_create_agent_from_package_with_mcp_servers_objects(
        self, mock_user, mock_storage, sample_agent_spec, monkeypatch
    ):
        """Direct function call path with dataclass payload should accept MCPServer objects."""
        # Mock extraction of the package spec
        monkeypatch.setattr(
            "agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package",
            AsyncMock(return_value=AgentPackageParsed(**sample_agent_spec)),
        )

        from agent_platform.core.mcp.mcp_server import MCPServer

        payload = AgentPackagePayload(
            name="MCP JSON Agent",
            agent_package_url="https://example.com/agent.zip",
            mcp_servers=[
                MCPServer.model_validate(
                    {
                        "name": "mcp-http",
                        "url": "https://mcp.example.com/sse",
                        "transport": "auto",
                        "headers": {"Authorization": "Bearer token"},
                        "force_serial_tool_calls": False,
                    }
                ),
                MCPServer.model_validate(
                    {
                        "name": "mcp-stdio",
                        "command": "docker",
                        "args": ["run", "--rm", "my-mcp"],
                        "env": {"FOO": "BAR"},
                        "cwd": "/work",
                        "transport": "stdio",
                    }
                ),
            ],
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        mock_storage.upsert_agent.assert_called_once()

        created_agent = mock_storage.upsert_agent.call_args[0][1]
        assert len(created_agent.mcp_servers) == 2
        assert created_agent.mcp_servers[0].url == "https://mcp.example.com/sse"
        assert created_agent.mcp_servers[1].is_stdio is True

    @pytest.mark.asyncio
    async def test_deploy_agent_with_mcp_servers_json(
        self, mock_user, mock_storage, sample_agent_spec, monkeypatch
    ):
        """
        Deploy endpoint should accept JSON with mcp/action/langsmith
        and convert before saving.
        """
        # Mock extraction of the package spec
        monkeypatch.setattr(
            "agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package",
            AsyncMock(return_value=AgentPackageParsed(**sample_agent_spec)),
        )

        # Build a Starlette Request with JSON body
        body_json = {
            "name": "Deploy JSON Agent",
            "agent_package_url": "https://example.com/agent.zip",
            "mcp_servers": [
                {
                    "name": "deploy-mcp",
                    "url": "https://mcp.example.com/endpoint",
                    "headers": {"X-API-Key": "abc"},
                    "transport": "auto",
                }
            ],
            "action_servers": [{"url": "https://actions.example.com", "api_key": "secret-act"}],
            "langsmith": {
                "api_key": "ls-key",
                "api_url": "https://langsmith.example.com",
                "project_name": "proj",
            },
        }

        body_bytes = json.dumps(body_json).encode()

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
            "client": ("testclient", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
        request = Request(scope, receive)

        # Execute deploy handler
        from agent_platform.server.api.private_v2.package import deploy_agent_from_package

        result = await deploy_agent_from_package(
            user=mock_user, request=request, storage=mock_storage, _=None
        )

        assert isinstance(result, AgentCompat)
        created_agent = mock_storage.upsert_agent.call_args[0][1]
        # mcp converted
        assert len(created_agent.mcp_servers) == 1
        assert created_agent.mcp_servers[0].url == "https://mcp.example.com/endpoint"
        # action server propagated to action_packages
        assert created_agent.action_packages[0].url == "https://actions.example.com"
        # langsmith moved under advanced_config via conversion
        as_legacy = AgentCompat.from_agent(created_agent, reveal_sensitive=True)
        assert as_legacy.advanced_config.get("langsmith", {}).get("api_key") == "ls-key"

    @pytest.mark.asyncio
    async def test_deploy_agent_multipart_with_json_strings(
        self, mock_user, mock_storage, sample_agent_spec, monkeypatch
    ):
        """
        Deploy endpoint should accept multipart/form-data where structured fields
        (model, mcp_servers, action_servers, langsmith) are JSON strings, and the
        server should coerce them before legacy conversion. This mirrors the UI behavior.
        """
        # Mock extraction of the package spec
        monkeypatch.setattr(
            "agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package",
            AsyncMock(return_value=AgentPackageParsed(**sample_agent_spec)),
        )

        # Build a Starlette Request with multipart form-data
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        fields = {
            "name": "Multipart JSON Agent",
            "agent_package_base64": "dGVzdA==",  # minimal, bypass URL/base64 validation path
            "public": "true",
            "model": json.dumps(
                {
                    "provider": "OpenAI",
                    "name": "gpt-4o",
                    "config": {"openai_api_key": "sk-test"},
                }
            ),
            "mcp_servers": json.dumps(
                [
                    {
                        "name": "time-mcp",
                        "url": "https://mcp.example.com/mcp",
                        "transport": "auto",
                        "headers": {"X": "y"},
                    }
                ]
            ),
            "action_servers": json.dumps(
                [{"url": "https://actions.example.com", "api_key": "act"}]
            ),
            "langsmith": json.dumps(
                {
                    "api_key": "ls",
                    "api_url": "https://ls.example.com",
                    "project_name": "proj",
                }
            ),
            "selected_tools": json.dumps({"tool_names": ["calendar"]}),
        }

        # Compose raw multipart payload
        def part(name: str, value: str) -> bytes:
            return (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
            ).encode()

        body = b"".join(part(k, v) for k, v in fields.items()) + f"--{boundary}--\r\n".encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/",
            "headers": [(b"content-type", f"multipart/form-data; boundary={boundary}".encode())],
            "query_string": b"",
            "client": ("testclient", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
        request = Request(scope, receive)

        # Execute deploy handler
        from agent_platform.server.api.private_v2.package import deploy_agent_from_package

        result = await deploy_agent_from_package(
            user=mock_user, request=request, storage=mock_storage, _=None
        )

        assert isinstance(result, AgentCompat)
        created_agent = mock_storage.upsert_agent.call_args[0][1]
        # mcp converted and present
        assert len(created_agent.mcp_servers) == 1
        assert created_agent.mcp_servers[0].url == "https://mcp.example.com/mcp"
        # action server propagated
        assert created_agent.action_packages[0].url == "https://actions.example.com"
        assert isinstance(created_agent.selected_tools, SelectedTools)
        assert [tool.tool_name for tool in created_agent.selected_tools.tool_names] == ["calendar"]

    async def test_create_agent_from_real_package_openai(
        self,
        mock_user,
        mock_storage,
    ):
        """Test successful agent creation from real OpenAI agent package."""
        test_package_path = TEST_AGENTS_DIR / "test-openai.zip"
        if not test_package_path.exists():
            pytest.skip("test-openai.zip not found")

        # Read the package file and encode it as base64
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Test OpenAI Agent",
            agent_package_base64=package_base64,
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Test OpenAI Agent"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_from_real_package_azure(
        self,
        mock_user,
        mock_storage,
    ):
        """Test successful agent creation from real Azure agent package."""
        test_package_path = TEST_AGENTS_DIR / "test-azure.zip"
        if not test_package_path.exists():
            pytest.skip("test-azure.zip not found")

        # Read the package file and encode it as base64
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Test Azure Agent",
            agent_package_base64=package_base64,
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Test Azure Agent"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_from_real_package_bedrock(
        self,
        mock_user,
        mock_storage,
    ):
        """Test successful agent creation from real Bedrock agent package."""
        test_package_path = TEST_AGENTS_DIR / "test-bedrock.zip"
        if not test_package_path.exists():
            pytest.skip("test-bedrock.zip not found")

        # Read the package file and encode it as base64
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Test Bedrock Agent",
            agent_package_base64=package_base64,
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Test Bedrock Agent"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_from_real_package_snowflake(
        self,
        mock_user,
        mock_storage,
    ):
        """Test successful agent creation from real snowflake agent package."""
        test_package_path = TEST_AGENTS_DIR / "test-sf.zip"
        if not test_package_path.exists():
            pytest.skip("test-sf.zip not found")

        # Read the package file and encode it as base64
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Test SF Agent",
            agent_package_base64=package_base64,
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Test SF Agent"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_from_real_package_complex_1(
        self,
        mock_user,
        mock_storage,
    ):
        """Test successful agent creation from real more complex agent package."""
        test_package_path = TEST_AGENTS_DIR / "call-center-planner.zip"
        if not test_package_path.exists():
            pytest.skip("call-center-planner.zip not found")

        # Read the package file and encode it as base64
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Call Center Planner",
            agent_package_base64=package_base64,
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Call Center Planner"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_from_real_package_complex_2(
        self,
        mock_user,
        mock_storage,
    ):
        """Test successful agent creation from real more complex agent package."""
        test_package_path = TEST_AGENTS_DIR / "document-extraction-agent.zip"
        if not test_package_path.exists():
            pytest.skip("document-extraction-agent.zip not found")

        # Read the package file and encode it as base64
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Test doc Agent",
            agent_package_base64=package_base64,
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Test doc Agent"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_from_complex_package(
        self,
        mock_user,
        mock_storage,
    ):
        """Test agent creation from complex document extraction agent package."""
        test_package_path = TEST_AGENTS_DIR / "document-extraction-agent.zip"
        if not test_package_path.exists():
            pytest.skip("document-extraction-agent.zip not found")

        # Read the package file and encode it as base64
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Document Extraction Agent",
            agent_package_base64=package_base64,
            model={"provider": "OpenAI", "name": "gpt-4"},
            action_servers=[
                AgentPackagePayloadActionServer(
                    url="https://document-actions.example.com",
                    api_key="doc-extraction-key-123",
                )
            ],
            langsmith=AgentPackagePayloadLangsmith(
                api_key="langsmith-key-123",
                api_url="https://langsmith.example.com",
                project_name="document-extraction-project",
            ),
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Document Extraction Agent"
        mock_storage.upsert_agent.assert_called_once()

        # Verify the created agent has expected configurations
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]

        # Should have langsmith config
        as_legacy = AgentCompat.from_agent(created_agent, reveal_sensitive=True)
        assert "langsmith" in as_legacy.advanced_config
        assert as_legacy.advanced_config["langsmith"]["api_key"] == "langsmith-key-123"

        # Should have action packages with action server config
        if created_agent.action_packages:
            action_package = created_agent.action_packages[0]
            assert action_package.url == "https://document-actions.example.com"
            assert isinstance(action_package.api_key, SecretString)

    @pytest.mark.asyncio
    async def test_create_agent_from_package_with_knowledge_file(self, mock_user, mock_storage):
        """
        Test that an agent with knowledge files is created successfully.
        Knowledge files are not supported in Agent Server v2;
        this test is here to make sure that an agent package with knowledge files
        does not affect agent creation in v2.
        """
        test_package_path = TEST_AGENTS_DIR / "agent-package-with-knowledge-file.zip"
        if not test_package_path.exists():
            pytest.skip("agent-package-with-knowledge-file.zip not found")

        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="VS Code One Changed",
            agent_package_base64=package_base64,
        )

        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        assert isinstance(result, AgentCompat)
        assert result.name == "VS Code One Changed"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_from_real_package_openai_gpt_5_new_arch(
        self,
        mock_user,
        mock_storage,
    ):
        """Test successful agent creation from real OpenAI agent package with new architecture."""
        test_package_path = TEST_AGENTS_DIR / "gpt-5-testing.zip"
        if not test_package_path.exists():
            pytest.skip("gpt-5-testing.zip not found")

        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Test OpenAI Agent",
            agent_package_base64=package_base64,
        )

        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        assert isinstance(result, AgentCompat)
        assert result.name == "Test OpenAI Agent"
        assert result.agent_architecture.name == "agent_platform.architectures.experimental_1"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_create_agent_from_package_url_success(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_spec,
        sample_agent_package_payload,
    ):
        """Test successful agent creation from package URL."""
        # Setup mock
        mock_extract_package.return_value = AgentPackageParsed(**sample_agent_spec)

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=sample_agent_package_payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Test Package Agent"
        mock_storage.upsert_agent.assert_called_once()
        mock_extract_package.assert_called_once_with(
            path=None,
            url="https://example.com/agent-package.zip",
            package_base64=None,
            include_knowledge=False,
            knowledge_return="stream",
        )

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_create_agent_from_package_base64_success(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_spec,
        sample_agent_package_payload_base64,
    ):
        """Test successful agent creation from base64 package."""
        # Setup mock
        mock_extract_package.return_value = AgentPackageParsed(**sample_agent_spec)

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=sample_agent_package_payload_base64,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Base64 Package Agent"
        mock_storage.upsert_agent.assert_called_once()
        mock_extract_package.assert_called_once_with(
            path=None,
            url=None,
            package_base64=sample_agent_package_payload_base64.agent_package_base64,
            include_knowledge=False,
            knowledge_return="stream",
        )

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_create_agent_from_package_with_action_servers(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_spec,
    ):
        """Test agent creation with action server configuration."""
        # Setup payload with action servers
        payload = AgentPackagePayload(
            name="Action Server Agent",
            agent_package_url="https://example.com/agent.zip",
            model={"provider": "OpenAI", "name": "gpt-4"},
            action_servers=[
                AgentPackagePayloadActionServer(
                    url="https://action1.example.com",
                    api_key=SecretString("secret-key-1"),
                ),
                AgentPackagePayloadActionServer(
                    url="https://action2.example.com",
                    api_key="secret-key-2",
                ),
            ],
        )

        mock_extract_package.return_value = AgentPackageParsed(**sample_agent_spec)

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        mock_storage.upsert_agent.assert_called_once()

        # Verify the created agent has action packages with correct config
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]  # Second argument is the agent
        assert len(created_agent.action_packages) > 0

        # Should use config from first action server only (as per code comment)
        action_package = created_agent.action_packages[0]
        assert action_package.url == "https://action1.example.com"
        assert isinstance(action_package.api_key, SecretString)

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_create_agent_from_package_with_langsmith(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_spec,
    ):
        """Test agent creation with Langsmith configuration."""
        payload = AgentPackagePayload(
            name="Langsmith Agent",
            agent_package_url="https://example.com/agent.zip",
            model={"provider": "OpenAI", "name": "gpt-4"},
            langsmith=AgentPackagePayloadLangsmith(
                api_key="langsmith-123",
                api_url="https://langsmith.example.com",
                project_name="test-project",
            ),
        )

        mock_extract_package.return_value = AgentPackageParsed(**sample_agent_spec)

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        mock_storage.upsert_agent.assert_called_once()

        # Verify langsmith config is included
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]
        as_legacy = AgentCompat.from_agent(created_agent, reveal_sensitive=True)
        assert "langsmith" in as_legacy.advanced_config
        assert as_legacy.advanced_config["langsmith"]["api_key"] == "langsmith-123"

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_create_agent_package_extraction_error(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_package_payload,
    ):
        """Test handling of package extraction errors."""
        # Setup mock to raise exception
        mock_extract_package.side_effect = ValueError("Invalid package format")

        # Execute and verify exception is raised
        with pytest.raises(ValueError, match="Invalid package format"):
            await create_agent_from_package(
                user=mock_user,
                payload=sample_agent_package_payload,
                storage=mock_storage,
                _=None,
            )

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_create_agent_missing_agent_in_spec(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_package_payload,
    ):
        """Test handling when package spec has no agents."""
        # Setup mock with empty agents list
        spec_no_agents = {
            "spec": {"agent-package": {"agents": []}},
            "runbook_text": "Empty runbook",
        }
        mock_extract_package.return_value = AgentPackageParsed(**spec_no_agents)

        # Execute and verify exception is raised
        with pytest.raises(IndexError):
            await create_agent_from_package(
                user=mock_user,
                payload=sample_agent_package_payload,
                storage=mock_storage,
                _=None,
            )


class TestUpdateAgentFromPackage:
    """Test cases for PUT /api/v2/agents/package/{aid} endpoint."""

    @pytest.mark.asyncio
    async def test_update_agent_from_real_package(
        self,
        mock_user,
        mock_storage,
    ):
        """Test successful agent update from real package."""
        test_package_path = TEST_AGENTS_DIR / "test-sf.zip"
        if not test_package_path.exists():
            pytest.skip("test-sf.zip not found")

        aid = str(uuid4())

        # Read the package file and encode it as base64
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Updated SF Agent",
            agent_package_base64=package_base64,
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Execute
        result = await update_agent_from_package(
            user=mock_user,
            aid=aid,
            payload=payload,
            storage=mock_storage,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Updated SF Agent"
        mock_storage.upsert_agent.assert_called_once()

        # Verify the agent ID is preserved
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]
        assert created_agent.agent_id == aid

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_update_agent_from_package_success(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_spec,
        sample_agent_package_payload,
    ):
        """Test successful agent update from package."""
        aid = str(uuid4())
        mock_extract_package.return_value = AgentPackageParsed(**sample_agent_spec)

        # Execute
        result = await update_agent_from_package(
            user=mock_user,
            aid=aid,
            payload=sample_agent_package_payload,
            storage=mock_storage,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Test Package Agent"
        mock_storage.upsert_agent.assert_called_once()

        # Verify the agent ID is preserved
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]
        assert created_agent.agent_id == aid


class TestCreateOrUpdateAgentFromPackageHelper:
    """Test cases for the _create_or_update_agent_from_package helper function."""

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    @patch("agent_platform.core.agent_package.upsert_from_package.ToolDefinitionCache")
    async def test_tools_cache_cleared(  # noqa: PLR0913
        self,
        mock_cache_class,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_spec,
        sample_agent_package_payload,
    ):
        """Test that tools cache is cleared after agent creation/update."""
        # Set up the mock so that ToolDefinitionCache() returns a mock instance
        mock_cache_instance = AsyncMock()
        mock_cache_class.return_value = mock_cache_instance
        mock_extract_package.return_value = AgentPackageParsed(**sample_agent_spec)

        # Execute
        await upsert_agent_from_package(
            user=mock_user,
            aid=str(uuid4()),
            payload=sample_agent_package_payload,
            storage=mock_storage,
        )

        # Verify cache constructor was called
        mock_cache_class.assert_called_once()
        # Verify cache was cleared
        mock_cache_instance.clear_for_agent.assert_called_once()

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_complex_agent_spec_processing(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
    ):
        """Test processing of complex agent specifications."""
        # Complex agent spec with multiple action packages
        complex_spec = {
            "spec": {
                "agent-package": {
                    "spec-version": "v2",
                    "agents": [
                        {
                            "name": "Complex Agent",
                            "description": "An agent with multiple action packages",
                            "version": "2.1.0",
                            "action-packages": [
                                {
                                    "name": "action-package-1",
                                    "organization": "org-1",
                                    "version": "1.0.0",
                                },
                                {
                                    "name": "action-package-2",
                                    "organization": "org-2",
                                    "version": "2.0.0",
                                },
                            ],
                            "metadata": {
                                "mode": "conversational",
                                "extra_field": "extra_value",
                            },
                        }
                    ],
                }
            },
            "runbook_text": "# Complex Runbook\nYou are a very capable assistant.",
        }

        payload = AgentPackagePayload(
            name="Override Complex Agent",  # Name should come from payload, not spec
            agent_package_url="https://example.com/complex-agent.zip",
            model={"provider": "OpenAI", "name": "gpt-4"},
            action_servers=[
                AgentPackagePayloadActionServer(
                    url="https://complex-actions.example.com",
                    api_key="complex-key-123",
                )
            ],
        )

        mock_extract_package.return_value = AgentPackageParsed(**complex_spec)

        # Execute
        result = await upsert_agent_from_package(
            user=mock_user,
            aid=str(uuid4()),
            payload=payload,
            storage=mock_storage,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Override Complex Agent"  # Should use payload name

        # Verify agent creation
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]

        # Should have action packages from spec with action server config from payload
        assert len(created_agent.action_packages) == 2
        for action_package in created_agent.action_packages:
            assert action_package.url == "https://complex-actions.example.com"
            assert isinstance(action_package.api_key, SecretString)
            assert action_package.api_key.get_secret_value() == "complex-key-123"

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_agent_architecture_mapping(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
        sample_agent_spec,
        sample_agent_package_payload,
    ):
        """Test that agent architecture is always mapped to default for v2."""
        mock_extract_package.return_value = AgentPackageParsed(**sample_agent_spec)

        # Execute
        await upsert_agent_from_package(
            user=mock_user,
            aid=str(uuid4()),
            payload=sample_agent_package_payload,
            storage=mock_storage,
        )

        # Verify architecture is mapped to default
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]
        assert created_agent.agent_architecture.name == "agent_platform.architectures.default"
        assert created_agent.agent_architecture.version == "1.0.0"


class TestConversationFields:
    """Test cases for conversation-related fields in agent specifications."""

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_agent_spec_with_conversation_fields(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
    ):
        """Test agent creation with conversation-guide, conversation-starter, welcome-message,
        and agent-settings."""
        # Agent spec with all conversation fields
        agent_spec_with_conversation = {
            "spec": {
                "agent-package": {
                    "spec-version": "v2.1",
                    "agents": [
                        {
                            "name": "Conversation Test Agent",
                            "description": "An agent for testing conversation fields",
                            "version": "1.0.0",
                            "model": {"provider": "OpenAI", "name": "gpt-4"},
                            "architecture": "agent",
                            "reasoning": "enabled",
                            "runbook": "runbook.md",
                            "conversation-guide": "conversation-guide.yaml",
                            "conversation-starter": "Hello! I'm ready to help you with your tasks. "
                            "What can I do for you today?",
                            "welcome-message": "Welcome! I'm here to assist you. "
                            "Let me know how I can help.",
                            "agent-settings": {
                                "max_iterations": 10,
                                "temperature": 0.7,
                                "enable_memory": True,
                                "custom_config": {"timeout": 30, "retry_attempts": 3},
                            },
                            "action-packages": [
                                {
                                    "name": "test-actions",
                                    "organization": "test-org",
                                    "version": "1.0.0",
                                }
                            ],
                            "metadata": {"mode": "conversational"},
                        }
                    ],
                }
            },
            "runbook_text": "# Conversation Agent\n"
            "You are a helpful assistant with conversation capabilities.",
        }

        payload = AgentPackagePayload(
            name="Conversation Test Agent",
            agent_package_url="https://example.com/conversation-agent.zip",
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Extract conversation fields from the agent spec
        agent0 = agent_spec_with_conversation["spec"]["agent-package"]["agents"][0]
        mock_extract_package.return_value = AgentPackageParsed(
            **agent_spec_with_conversation,
            conversation_starter=agent0.get("conversation-starter"),
            welcome_message=agent0.get("welcome-message"),
            agent_settings=agent0.get("agent-settings"),
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Conversation Test Agent"
        mock_storage.upsert_agent.assert_called_once()

        # Verify the extraction was called with correct parameters
        mock_extract_package.assert_called_once_with(
            path=None,
            url="https://example.com/conversation-agent.zip",
            package_base64=None,
            include_knowledge=False,
            knowledge_return="stream",
        )

        # Verify conversation fields are properly stored in the agent
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]

        # Check conversation-starter is stored in extra
        assert "conversation_starter" in created_agent.extra
        assert created_agent.extra["conversation_starter"] == (
            "Hello! I'm ready to help you with your tasks. What can I do for you today?"
        )

        # Check welcome-message is stored in extra
        assert "welcome_message" in created_agent.extra
        assert created_agent.extra["welcome_message"] == (
            "Welcome! I'm here to assist you. Let me know how I can help."
        )

        # Check agent-settings is stored in both agent_settings field and extra
        expected_settings = {
            "max_iterations": 10,
            "temperature": 0.7,
            "enable_memory": True,
            "custom_config": {"timeout": 30, "retry_attempts": 3},
        }
        assert "agent_settings" in created_agent.extra
        assert created_agent.extra["agent_settings"] == expected_settings

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_agent_spec_with_minimal_conversation_fields(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
    ):
        """Test agent creation with only some conversation fields (testing optional nature)."""
        # Agent spec with only welcome-message and conversation-starter
        minimal_conversation_spec = {
            "spec": {
                "agent-package": {
                    "spec-version": "v2.1",
                    "agents": [
                        {
                            "name": "Minimal Conversation Agent",
                            "description": "An agent with minimal conversation fields",
                            "version": "1.0.0",
                            "model": {"provider": "OpenAI", "name": "gpt-4"},
                            "architecture": "agent",
                            "reasoning": "disabled",
                            "runbook": "runbook.md",
                            "conversation-starter": "Hi there! How can I assist you?",
                            "welcome-message": "Welcome to our service!",
                            "action-packages": [
                                {
                                    "name": "minimal-actions",
                                    "organization": "test-org",
                                    "version": "1.0.0",
                                }
                            ],
                            "metadata": {"mode": "conversational"},
                        }
                    ],
                }
            },
            "runbook_text": "# Minimal Agent\nYou are a simple assistant.",
        }

        payload = AgentPackagePayload(
            name="Minimal Conversation Agent",
            agent_package_base64="dGVzdC1jb250ZW50",  # base64 encoded "test-content"
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Extract conversation fields from the agent spec
        agent0 = minimal_conversation_spec["spec"]["agent-package"]["agents"][0]
        mock_extract_package.return_value = AgentPackageParsed(
            **minimal_conversation_spec,
            conversation_starter=agent0.get("conversation-starter"),
            welcome_message=agent0.get("welcome-message"),
            agent_settings=agent0.get("agent-settings"),
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Minimal Conversation Agent"
        mock_storage.upsert_agent.assert_called_once()

        # Verify minimal conversation fields are properly stored in the agent
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]

        # Check conversation-starter is stored in extra
        assert "conversation_starter" in created_agent.extra
        assert created_agent.extra["conversation_starter"] == "Hi there! How can I assist you?"

        # Check welcome-message is stored in extra
        assert "welcome_message" in created_agent.extra
        assert created_agent.extra["welcome_message"] == "Welcome to our service!"

        # Check that agent-settings is empty dict since not provided
        assert created_agent.extra["agent_settings"] == {}

        # Check that question_groups is empty since no conversation-guide was provided
        assert created_agent.question_groups == []

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_agent_spec_with_complex_agent_settings(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
    ):
        """Test agent creation with complex agent-settings structure."""
        # Agent spec with complex agent-settings
        complex_settings_spec = {
            "spec": {
                "agent-package": {
                    "spec-version": "v2.1",
                    "agents": [
                        {
                            "name": "Complex Settings Agent",
                            "description": "An agent with complex settings configuration",
                            "version": "2.0.0",
                            "model": {"provider": "Azure", "name": "gpt-4"},
                            "architecture": "plan_execute",
                            "reasoning": "verbose",
                            "runbook": "runbook.md",
                            "conversation-guide": "advanced-guide.yaml",
                            "conversation-starter": "I'm an advanced AI assistant. "
                            "What complex task can I help you with?",
                            "welcome-message": "Welcome! I have advanced capabilities "
                            "and can handle complex workflows.",
                            "agent-settings": {
                                "execution": {
                                    "max_planning_iterations": 5,
                                    "max_execution_iterations": 15,
                                    "allow_replanning": True,
                                },
                                "llm_config": {
                                    "temperature": 0.3,
                                    "max_tokens": 2048,
                                    "top_p": 0.9,
                                },
                                "behavior": {
                                    "verbose_reasoning": True,
                                    "include_thinking_steps": True,
                                    "auto_retry_on_failure": True,
                                },
                                "integrations": {
                                    "enable_web_search": True,
                                    "enable_file_operations": False,
                                    "allowed_domains": ["example.com", "api.service.com"],
                                },
                            },
                            "action-packages": [
                                {
                                    "name": "advanced-actions",
                                    "organization": "enterprise-org",
                                    "version": "2.1.0",
                                }
                            ],
                            "metadata": {
                                "mode": "worker",
                                "worker-config": {
                                    "type": "Document Intelligence",
                                    "document-type": "Financial Report Analysis",
                                },
                            },
                        }
                    ],
                }
            },
            "runbook_text": "# Advanced Agent\n"
            "You are an enterprise-grade AI assistant with advanced planning "
            "capabilities.",
        }

        payload = AgentPackagePayload(
            name="Complex Settings Agent",
            agent_package_url="https://enterprise.example.com/complex-agent.zip",
            model={"provider": "Azure", "name": "gpt-4"},
            langsmith=AgentPackagePayloadLangsmith(
                api_key="enterprise-langsmith-key",
                api_url="https://langsmith.enterprise.com",
                project_name="complex-agent-monitoring",
            ),
        )

        # Extract conversation fields from the agent spec
        agent0 = complex_settings_spec["spec"]["agent-package"]["agents"][0]
        mock_extract_package.return_value = AgentPackageParsed(
            **complex_settings_spec,
            conversation_starter=agent0.get("conversation-starter"),
            welcome_message=agent0.get("welcome-message"),
            agent_settings=agent0.get("agent-settings"),
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Complex Settings Agent"
        mock_storage.upsert_agent.assert_called_once()

        # Verify the created agent has expected configurations
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]

        # Should have langsmith config
        as_legacy = AgentCompat.from_agent(created_agent, reveal_sensitive=True)
        assert "langsmith" in as_legacy.advanced_config
        assert as_legacy.advanced_config["langsmith"]["api_key"] == "enterprise-langsmith-key"

        # Verify all conversation fields are properly stored
        # Check conversation-starter is stored in extra
        assert "conversation_starter" in created_agent.extra
        assert created_agent.extra["conversation_starter"] == (
            "I'm an advanced AI assistant. What complex task can I help you with?"
        )

        # Check welcome-message is stored in extra
        assert "welcome_message" in created_agent.extra
        assert created_agent.extra["welcome_message"] == (
            "Welcome! I have advanced capabilities and can handle complex workflows."
        )

        # Check complex agent-settings is stored in both agent_settings field and extra
        expected_complex_settings = {
            "execution": {
                "max_planning_iterations": 5,
                "max_execution_iterations": 15,
                "allow_replanning": True,
            },
            "llm_config": {
                "temperature": 0.3,
                "max_tokens": 2048,
                "top_p": 0.9,
            },
            "behavior": {
                "verbose_reasoning": True,
                "include_thinking_steps": True,
                "auto_retry_on_failure": True,
            },
            "integrations": {
                "enable_web_search": True,
                "enable_file_operations": False,
                "allowed_domains": ["example.com", "api.service.com"],
            },
        }
        assert "agent_settings" in created_agent.extra
        assert created_agent.extra["agent_settings"] == expected_complex_settings

    @pytest.mark.asyncio
    @patch("agent_platform.core.agent_package.upsert_from_package.read_and_validate_agent_package")
    async def test_agent_spec_with_conversation_guide_question_groups(
        self,
        mock_extract_package,
        mock_user,
        mock_storage,
    ):
        """Test agent creation with conversation guide that generates question groups."""
        from agent_platform.core.agent.question_group import QuestionGroup

        # Agent spec with conversation guide that would generate question groups
        conversation_guide_spec = {
            "spec": {
                "agent-package": {
                    "spec-version": "v2.1",
                    "agents": [
                        {
                            "name": "Guide Agent",
                            "description": "An agent with conversation guide",
                            "version": "1.0.0",
                            "model": {"provider": "OpenAI", "name": "gpt-4"},
                            "architecture": "agent",
                            "reasoning": "enabled",
                            "runbook": "runbook.md",
                            "conversation-guide": "conversation-guide.yaml",
                            "conversation-starter": "Hello! I can help with various tasks.",
                            "welcome-message": "Welcome! Ask me anything.",
                            "action-packages": [
                                {
                                    "name": "guide-actions",
                                    "organization": "test-org",
                                    "version": "1.0.0",
                                }
                            ],
                            "metadata": {"mode": "conversational"},
                        }
                    ],
                }
            },
            "runbook_text": "# Guide Agent\nI help with guided conversations.",
            # Mock question groups that would be extracted from conversation guide
            "question_groups": [
                QuestionGroup(
                    title="Getting Started",
                    questions=[
                        "How do I begin?",
                        "What can you help me with?",
                        "Where should I start?",
                    ],
                ),
                QuestionGroup(
                    title="Advanced Features",
                    questions=[
                        "How do I use advanced features?",
                        "What are the limitations?",
                        "Can you integrate with other tools?",
                    ],
                ),
            ],
        }

        payload = AgentPackagePayload(
            name="Guide Agent",
            agent_package_url="https://example.com/guide-agent.zip",
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Extract conversation fields from the agent spec
        agent0 = conversation_guide_spec["spec"]["agent-package"]["agents"][0]
        mock_extract_package.return_value = AgentPackageParsed(
            **conversation_guide_spec,
            conversation_starter=agent0.get("conversation-starter"),
            welcome_message=agent0.get("welcome-message"),
            agent_settings=agent0.get("agent-settings"),
        )

        # Execute
        result = await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify
        assert isinstance(result, AgentCompat)
        assert result.name == "Guide Agent"
        mock_storage.upsert_agent.assert_called_once()

        # Verify conversation guide fields are properly stored
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]

        # Check conversation-starter and welcome-message
        assert (
            created_agent.extra["conversation_starter"] == "Hello! I can help with various tasks."
        )
        assert created_agent.extra["welcome_message"] == "Welcome! Ask me anything."

        # Check that question_groups from conversation guide are properly stored
        assert len(created_agent.question_groups) == 2

        # Verify first question group
        first_group = created_agent.question_groups[0]
        assert isinstance(first_group, QuestionGroup)
        assert first_group.title == "Getting Started"
        assert len(first_group.questions) == 3
        assert "How do I begin?" in first_group.questions
        assert "What can you help me with?" in first_group.questions
        assert "Where should I start?" in first_group.questions

        # Verify second question group
        second_group = created_agent.question_groups[1]
        assert isinstance(second_group, QuestionGroup)
        assert second_group.title == "Advanced Features"
        assert len(second_group.questions) == 3
        assert "How do I use advanced features?" in second_group.questions
        assert "What are the limitations?" in second_group.questions
        assert "Can you integrate with other tools?" in second_group.questions


class TestSemanticDataModelImport:
    """Test cases for SDM import functionality using sqlite_storage."""

    @pytest.mark.asyncio
    async def test_import_sdm_with_data_connection_name(
        self,
        sqlite_storage,
        tmp_path,
    ):
        """Test SDM import with data_connection_name that resolves successfully."""
        from agent_platform.core.data_connections.data_connections import (
            DataConnection,
            PostgresDataConnectionConfiguration,
        )
        from server.tests.storage.sample_model_creator import SampleModelCreator

        # Setup real data connection in storage
        creator = SampleModelCreator(sqlite_storage, tmp_path)
        await creator.setup()

        # Create real data connection with name "Local postgres"
        # (matches the name in the exported agent-package.zip)
        data_connection = DataConnection(
            id="test-conn-id",
            name="Local postgres",
            description="Test connection",
            engine="postgres",
            configuration=PostgresDataConnectionConfiguration(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password",
            ),
            tags=[],
        )
        await sqlite_storage.set_data_connection(data_connection)

        # Use real agent package ZIP with SDM
        test_package_path = TEST_AGENTS_DIR / "test-sdm-agent.zip"
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="SDM Test Agent",
            agent_package_base64=package_base64,
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Get user for import
        user, _ = await sqlite_storage.get_or_create_user("tenant:test:user:test")
        user_obj = User(user_id=user.user_id, sub=user.sub)

        # Execute real import (no mocks!)
        result = await create_agent_from_package(
            user=user_obj,
            payload=payload,
            storage=sqlite_storage,
            _=None,
        )

        # Verify SDM was imported using real storage queries
        assert isinstance(result, AgentCompat)

        # Query real storage to verify SDM
        sdms = await sqlite_storage.get_agent_semantic_data_models(result.agent_id)
        assert len(sdms) == 1

        # Get the SDM content
        sdm_id = next(iter(sdms[0].keys()))
        stored_sdm = sdms[0][sdm_id]

        # Verify data_connection_id is present in SDM metadata (for querying)
        assert "tables" in stored_sdm
        assert len(stored_sdm["tables"]) > 0
        assert "base_table" in stored_sdm["tables"][0]
        assert stored_sdm["tables"][0]["base_table"]["data_connection_id"] == data_connection.id

        # Verify data_connection_name was removed (only needed during import)
        assert "data_connection_name" not in stored_sdm["tables"][0]["base_table"]

    @pytest.mark.asyncio
    async def test_import_sdm_with_unresolved_connection_name(
        self,
        sqlite_storage,
        tmp_path,
    ):
        """Test SDM import with data_connection_name that cannot be resolved."""
        from server.tests.storage.sample_model_creator import SampleModelCreator

        # Setup storage WITHOUT creating the data connection
        # (so "Local postgres" won't be found)
        creator = SampleModelCreator(sqlite_storage, tmp_path)
        await creator.setup()

        # Use real agent package ZIP with SDM (references "Local postgres")
        test_package_path = TEST_AGENTS_DIR / "test-sdm-agent.zip"
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="SDM Test Agent",
            agent_package_base64=package_base64,
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Get user for import
        user, _ = await sqlite_storage.get_or_create_user("tenant:test:user:test")
        user_obj = User(user_id=user.user_id, sub=user.sub)

        # Execute import
        result = await create_agent_from_package(
            user=user_obj,
            payload=payload,
            storage=sqlite_storage,
            _=None,
        )

        # Verify SDM was still imported (without connection)
        assert isinstance(result, AgentCompat)

        # Query real storage to verify SDM
        sdms = await sqlite_storage.get_agent_semantic_data_models(result.agent_id)
        assert len(sdms) == 1

        # Get the SDM content
        sdm_id = next(iter(sdms[0].keys()))
        stored_sdm = sdms[0][sdm_id]

        # Verify data_connection_name was removed even though it couldn't be resolved
        assert "tables" in stored_sdm
        assert len(stored_sdm["tables"]) > 0
        assert "base_table" in stored_sdm["tables"][0]
        assert "data_connection_name" not in stored_sdm["tables"][0]["base_table"]

        # Verify no data_connection_id was added (since it couldn't be resolved)
        assert "data_connection_id" not in stored_sdm["tables"][0]["base_table"]

    @pytest.mark.asyncio
    async def test_import_sdm_deduplication_within_same_agent(
        self,
        sqlite_storage,
        tmp_path,
    ):
        """Test that duplicate SDMs are not created when re-importing the same agent."""
        from server.tests.storage.sample_model_creator import SampleModelCreator

        # Setup storage
        creator = SampleModelCreator(sqlite_storage, tmp_path)
        await creator.setup()

        # Use real agent package ZIP with SDM
        test_package_path = TEST_AGENTS_DIR / "test-sdm-agent.zip"
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="SDM Test Agent",
            agent_package_base64=package_base64,
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Get user for import
        user, _ = await sqlite_storage.get_or_create_user("tenant:test:user:test")
        user_obj = User(user_id=user.user_id, sub=user.sub)

        # Import agent FIRST time - creates agent and SDM
        result1 = await create_agent_from_package(
            user=user_obj,
            payload=payload,
            storage=sqlite_storage,
            _=None,
        )

        # Get SDM ID from first import
        sdms1 = await sqlite_storage.get_agent_semantic_data_models(result1.agent_id)
        assert len(sdms1) == 1
        first_sdm_id = next(iter(sdms1[0].keys()))

        # Re-import SAME agent (update) - should reuse existing SDM
        result2 = await update_agent_from_package(
            user=user_obj,
            aid=result1.agent_id,  # Same agent ID
            payload=payload,
            storage=sqlite_storage,
        )

        # Verify SDM was reused (same ID)
        sdms2 = await sqlite_storage.get_agent_semantic_data_models(result2.agent_id)
        assert len(sdms2) == 1
        second_sdm_id = next(iter(sdms2[0].keys()))

        # Same SDM ID means deduplication worked
        assert first_sdm_id == second_sdm_id

    @pytest.mark.asyncio
    async def test_import_agent_with_sdm_has_multiple_tables(
        self,
        sqlite_storage,
        tmp_path,
    ):
        """Test that agent with SDM containing multiple tables imports correctly."""
        from agent_platform.core.data_connections.data_connections import (
            DataConnection,
            PostgresDataConnectionConfiguration,
        )
        from server.tests.storage.sample_model_creator import SampleModelCreator

        # Setup storage
        creator = SampleModelCreator(sqlite_storage, tmp_path)
        await creator.setup()

        # Create data connection
        data_connection = DataConnection(
            id="test-conn-id",
            name="Local postgres",
            description="Test connection",
            engine="postgres",
            configuration=PostgresDataConnectionConfiguration(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password",
            ),
            tags=[],
        )
        await sqlite_storage.set_data_connection(data_connection)

        # Use real agent package ZIP (has SDM with 2 tables)
        test_package_path = TEST_AGENTS_DIR / "test-sdm-agent.zip"
        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="SDM Test Agent",
            agent_package_base64=package_base64,
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Get user for import
        user, _ = await sqlite_storage.get_or_create_user("tenant:test:user:test")
        user_obj = User(user_id=user.user_id, sub=user.sub)

        # Execute import
        result = await create_agent_from_package(
            user=user_obj,
            payload=payload,
            storage=sqlite_storage,
            _=None,
        )

        # Verify SDM with multiple tables was imported
        assert isinstance(result, AgentCompat)

        sdms = await sqlite_storage.get_agent_semantic_data_models(result.agent_id)
        assert len(sdms) == 1

        sdm_id = next(iter(sdms[0].keys()))
        stored_sdm = sdms[0][sdm_id]

        # Verify multiple tables are present
        assert "tables" in stored_sdm
        assert len(stored_sdm["tables"]) > 1  # Real ZIP has 2 tables

    @pytest.mark.asyncio
    async def test_import_agent_without_semantic_data_models(
        self,
        sqlite_storage,
        tmp_path,
    ):
        """Test that agents without SDMs import correctly."""
        from server.tests.storage.sample_model_creator import SampleModelCreator

        # Setup storage
        creator = SampleModelCreator(sqlite_storage, tmp_path)
        await creator.setup()

        # Use a real agent package without SDMs (e.g., test-openai.zip)
        test_package_path = TEST_AGENTS_DIR / "test-openai.zip"
        if not test_package_path.exists():
            pytest.skip("test-openai.zip not found")

        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="Basic Agent",
            agent_package_base64=package_base64,
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # Get user for import
        user, _ = await sqlite_storage.get_or_create_user("tenant:test:user:test")
        user_obj = User(user_id=user.user_id, sub=user.sub)

        # Execute import
        result = await create_agent_from_package(
            user=user_obj,
            payload=payload,
            storage=sqlite_storage,
            _=None,
        )

        # Verify agent created successfully without SDMs
        assert isinstance(result, AgentCompat)

        # Verify no SDMs are linked
        sdms = await sqlite_storage.get_agent_semantic_data_models(result.agent_id)
        assert len(sdms) == 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_invalid_package_file(self, mock_user, mock_storage):
        """Test handling of invalid package files."""
        # Try to load a non-existent package
        payload = AgentPackagePayload(
            name="Invalid Package Agent",
            agent_package_base64="invalid-base64-content",
            model={"provider": "OpenAI", "name": "gpt-4"},
        )

        # This should raise an HTTPException from extract_and_validate_agent_package
        with pytest.raises(HTTPException):
            await create_agent_from_package(
                user=mock_user,
                payload=payload,
                storage=mock_storage,
                _=None,
            )

    @pytest.mark.asyncio
    async def test_string_api_key_conversion(self, mock_user, mock_storage):
        """Test that string API keys are properly converted to SecretString."""
        test_package_path = TEST_AGENTS_DIR / "test-openai.zip"
        if not test_package_path.exists():
            pytest.skip("test-openai.zip not found")

        package_base64 = base64.b64encode(test_package_path.read_bytes()).decode()

        payload = AgentPackagePayload(
            name="String Key Agent",
            agent_package_base64=package_base64,
            model={"provider": "OpenAI", "name": "gpt-4"},
            action_servers=[
                AgentPackagePayloadActionServer(
                    url="https://action.example.com",
                    api_key="plain-string-key",  # Plain string
                )
            ],
        )

        await create_agent_from_package(
            user=mock_user,
            payload=payload,
            storage=mock_storage,
            _=None,
        )

        # Verify the string was converted to SecretString
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]
        if created_agent.action_packages:
            action_package = created_agent.action_packages[0]
            assert isinstance(action_package.api_key, SecretString)
            assert action_package.api_key.get_secret_value() == "plain-string-key"
