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
    create_agent_from_package,
    update_agent_from_package,
)
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.api.private_v2.package import create_or_update_agent_from_package

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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
    @patch("agent_platform.server.api.private_v2.package.ToolDefinitionCache")
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
        await create_or_update_agent_from_package(
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
        result = await create_or_update_agent_from_package(
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
        await create_or_update_agent_from_package(
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
    @patch("agent_platform.server.api.private_v2.package.extract_and_validate_agent_package")
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
