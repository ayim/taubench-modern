import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from agent_platform.core.agent_spec.package_parsed import AgentPackageParsed
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.payloads.agent_package import (
    AgentPackagePayload,
    AgentPackagePayloadActionServer,
    AgentPackagePayloadLangsmith,
)
from agent_platform.core.user import User
from agent_platform.core.utils import SecretString
from agent_platform.server.api.private_v2.agents import (
    _create_or_update_agent_from_package,
    create_agent_from_package,
    update_agent_from_package,
)
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat

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
    storage.get_agent = AsyncMock()
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


class TestCreateAgentFromPackage:
    """Test cases for POST /api/v2/agents/package endpoint."""

    @pytest.mark.asyncio
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
        )

        assert isinstance(result, AgentCompat)
        assert result.name == "VS Code One Changed"
        mock_storage.upsert_agent.assert_called_once()

    @pytest.mark.asyncio
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
            )

    @pytest.mark.asyncio
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
    @patch("agent_platform.server.api.private_v2.agents.ToolDefinitionCache")
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
        await _create_or_update_agent_from_package(
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
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
        result = await _create_or_update_agent_from_package(
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
    @patch("agent_platform.server.api.private_v2.agents.extract_and_validate_agent_package")
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
        await _create_or_update_agent_from_package(
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
        )

        # Verify the string was converted to SecretString
        call_args = mock_storage.upsert_agent.call_args[0]
        created_agent = call_args[1]
        if created_agent.action_packages:
            action_package = created_agent.action_packages[0]
            assert isinstance(action_package.api_key, SecretString)
            assert action_package.api_key.get_secret_value() == "plain-string-key"
