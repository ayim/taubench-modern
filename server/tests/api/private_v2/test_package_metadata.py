"""Unit tests for package_metadata module.

Tests the happy paths for agent package metadata generation classes and functions.
"""

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.metadata.action_packages import (
    ActionPackageMetadataReader,
    get_datasource_name,
    get_raw_datasources,
)
from agent_platform.core.agent_package.metadata.agent_metadata import (
    AgentPackageDockerMcpGateway,
    AgentPackageMcpServer,
)
from agent_platform.core.agent_package.metadata.agent_metadata_generator import (
    AgentMetadataGenerator,
)
from agent_platform.core.agent_package.spec import (
    SpecActionPackage,
    SpecAgent,
    SpecDockerMcpGateway,
    SpecKnowledge,
    SpecMCPServer,
)
from agent_platform.core.errors import PlatformHTTPError


def create_agent_package_zip(spec_yaml: str, files: dict[str, bytes] | None = None) -> bytes:
    """Create an in-memory agent package zip file.

    Args:
        spec_yaml: Content of agent-spec.yaml.
        files: Additional files to include (path -> content).

    Returns:
        Bytes of the zip file.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("agent-spec.yaml", spec_yaml)
        if files:
            for path, content in files.items():
                zf.writestr(path, content)
    return buffer.getvalue()


def create_mock_handler() -> MagicMock:
    """Create a mock BasePackageHandler for testing."""
    handler = MagicMock()
    handler.read_file = AsyncMock()
    handler.file_exists = AsyncMock(return_value=False)
    handler.list_files = AsyncMock(return_value=[])
    handler.load_icon = AsyncMock(return_value="")
    return handler


class TestGenerateMcpServersMetadata:
    """Tests for AgentPackageMcpServer.from_spec method."""

    def test_stdio_transport(self):
        """Test MCP server with stdio transport."""
        spec = SpecMCPServer.model_validate(
            {
                "name": "test-server",
                "description": "A test MCP server",
                "transport": "stdio",
                "command-line": ["python", "-m", "mcp_server", "--port", "8080"],
                "cwd": "/tmp",
                "force-serial-tool-calls": True,
            }
        )

        result = AgentPackageMcpServer.from_spec(spec)

        assert result.name == "test-server"
        assert result.description == "A test MCP server"
        assert result.transport == "stdio"
        assert result.command == "python"
        assert result.arguments == ["-m", "mcp_server", "--port", "8080"]
        assert result.cwd == "/tmp"
        assert result.force_serial_tool_calls is True
        assert result.url == ""

    def test_stdio_transport_with_env(self):
        """Test MCP server with stdio transport and environment variables."""
        spec = SpecMCPServer.model_validate(
            {
                "name": "env-server",
                "transport": "stdio",
                "command-line": ["node", "server.js"],
                "env": {
                    "API_KEY": {"type": "string", "value": "secret123"},
                    "DEBUG": {"type": "string", "value": "true"},
                },
            }
        )

        result = AgentPackageMcpServer.from_spec(spec)

        assert result.name == "env-server"
        assert "API_KEY" in result.env
        assert result.env["API_KEY"].value == "secret123"
        assert result.env["DEBUG"].value == "true"

    def test_sse_transport(self):
        """Test MCP server with SSE transport."""
        spec = SpecMCPServer.model_validate(
            {
                "name": "sse-server",
                "transport": "sse",
                "url": "https://api.example.com/sse",
                "headers": {"Authorization": {"type": "string", "value": "Bearer token123"}},
            }
        )

        result = AgentPackageMcpServer.from_spec(spec)

        assert result.name == "sse-server"
        assert result.transport == "sse"
        assert result.url == "https://api.example.com/sse"
        assert "Authorization" in result.headers
        assert result.headers["Authorization"].value == "Bearer token123"

    def test_streamable_http_transport(self):
        """Test MCP server with streamable-http transport."""
        spec = SpecMCPServer.model_validate(
            {
                "name": "http-server",
                "transport": "streamable-http",
                "url": "https://api.example.com/mcp",
            }
        )

        result = AgentPackageMcpServer.from_spec(spec)

        assert result.name == "http-server"
        assert result.transport == "streamable-http"
        assert result.url == "https://api.example.com/mcp"

    def test_auto_transport_with_url(self):
        """Test auto transport detection with URL."""
        spec = SpecMCPServer.model_validate(
            {
                "name": "auto-url",
                "transport": "auto",
                "url": "https://api.example.com",
            }
        )

        result = AgentPackageMcpServer.from_spec(spec)

        assert result.name == "auto-url"
        assert result.url == "https://api.example.com"
        assert result.command == ""

    def test_auto_transport_with_command(self):
        """Test auto transport detection with command."""
        spec = SpecMCPServer.model_validate(
            {
                "name": "auto-cmd",
                "transport": "auto",
                "command-line": ["python", "server.py"],
            }
        )

        result = AgentPackageMcpServer.from_spec(spec)

        assert result.name == "auto-cmd"
        assert result.command == "python"
        assert result.url == ""

    def test_default_transport(self):
        """Test default transport when not specified."""
        spec = SpecMCPServer.model_validate(
            {
                "name": "default-server",
                "command-line": ["python", "server.py"],
            }
        )

        result = AgentPackageMcpServer.from_spec(spec)

        assert result.name == "default-server"
        assert result.transport == "auto"


class TestBuildMcpServerVariable:
    """Tests for AgentPackageMcpServer._build_mcp_server_variable method."""

    def test_string_value(self):
        """Test building variable from string value."""
        result = AgentPackageMcpServer._build_mcp_server_variable("simple_value")

        assert result.value == "simple_value"
        assert result.type == ""
        assert result.description == ""

    def test_dict_value(self):
        """Test building variable from dict value."""
        value = {
            "type": "secret",
            "description": "API key",
            "provider": "oauth",
            "scopes": ["read", "write"],
            "value": "token123",
        }

        result = AgentPackageMcpServer._build_mcp_server_variable(value)

        assert result.value == "token123"
        assert result.type == "secret"
        assert result.description == "API key"
        assert result.provider == "oauth"
        assert result.scopes == ["read", "write"]


class TestGetDatasourceName:
    """Tests for get_datasource_name function."""

    def test_files_engine(self):
        """Test datasource name for files engine."""
        ds = {"created_table": "my_table", "name": "other_name"}
        result = get_datasource_name(ds, "files")
        assert result == "my_table"

    def test_lightwood_engine(self):
        """Test datasource name for prediction:lightwood engine."""
        ds = {"model_name": "predictor", "name": "other_name"}
        result = get_datasource_name(ds, "prediction:lightwood")
        assert result == "predictor"

    def test_default_engine(self):
        """Test datasource name for default engines."""
        ds = {"name": "db_source"}
        result = get_datasource_name(ds, "postgres")
        assert result == "db_source"


class TestGetRawDatasources:
    """Tests for get_raw_datasources function."""

    def test_with_datasources(self):
        """Test extracting datasources from metadata."""
        raw_metadata = {
            "metadata": {
                "data": {
                    "datasources": [
                        {"name": "ds1", "engine": "postgres"},
                        {"name": "ds2", "engine": "mysql"},
                    ]
                }
            }
        }

        result = get_raw_datasources(raw_metadata)

        assert len(result) == 2
        assert result[0]["name"] == "ds1"
        assert result[1]["name"] == "ds2"

    def test_without_datasources(self):
        """Test extracting from metadata without datasources."""
        raw_metadata = {"metadata": {"data": {}}}
        result = get_raw_datasources(raw_metadata)
        assert result == []

    def test_empty_metadata(self):
        """Test extracting from empty metadata."""
        result = get_raw_datasources({})
        assert result == []


class TestAgentMetadataGeneratorKnowledge:
    """Tests for AgentMetadataGenerator._extract_knowledge method."""

    def test_with_knowledge(self):
        """Test extracting knowledge files."""
        knowledge_spec = [
            SpecKnowledge(name="doc1.pdf", embedded=True, digest="abc123"),
            SpecKnowledge(name="doc2.txt", embedded=False, digest="def456"),
        ]

        handler = create_mock_handler()
        generator = AgentMetadataGenerator(handler)
        result = generator._extract_knowledge(knowledge_spec)

        assert len(result) == 2
        assert result[0].name == "doc1.pdf"
        assert result[0].embedded is True
        assert result[0].digest == "abc123"
        assert result[1].name == "doc2.txt"
        assert result[1].embedded is False

    def test_without_knowledge(self):
        """Test extracting when no knowledge files."""
        handler = create_mock_handler()
        generator = AgentMetadataGenerator(handler)
        result = generator._extract_knowledge([])
        assert result == []


class TestAgentMetadataGeneratorSelectedTools:
    """Tests for AgentMetadataGenerator._extract_selected_tools method."""

    def test_with_tools(self):
        """Test extracting selected tools."""
        agent = SpecAgent.model_validate(
            {
                "name": "test-agent",
                "description": "Test agent",
                "version": "1.0.0",
                "action-packages": [],
                "selected-tools": {
                    "tools": [
                        {"name": "tool1"},
                        {"name": "tool2"},
                    ]
                },
            }
        )

        handler = create_mock_handler()
        generator = AgentMetadataGenerator(handler)
        result = generator._extract_selected_tools(agent)

        assert [t.name for t in result.tools] == ["tool1", "tool2"]

    def test_without_tools(self):
        """Test extracting when no tools selected."""
        agent = SpecAgent.model_validate(
            {
                "name": "test-agent",
                "description": "Test agent",
                "version": "1.0.0",
                "action-packages": [],
            }
        )
        handler = create_mock_handler()
        generator = AgentMetadataGenerator(handler)
        result = generator._extract_selected_tools(agent)
        assert result.tools == []


class TestToAgentPackageDockerMcpGateway:
    """Tests for AgentPackageDockerMcpGateway.from_spec method."""

    def test_with_gateway(self):
        """Test converting Docker MCP Gateway spec."""
        spec = SpecDockerMcpGateway(
            catalog="/path/to/catalog.yaml",
            servers={
                "server1": {"tool1": {}, "tool2": {}},
                "server2": {"tool3": {}},
            },
        )

        result = AgentPackageDockerMcpGateway.from_spec(spec)

        assert result is not None
        assert result.catalog == "/path/to/catalog.yaml"
        assert "server1" in result.servers
        assert "server2" in result.servers
        assert "tool1" in result.servers["server1"]
        assert "tool2" in result.servers["server1"]
        assert "tool3" in result.servers["server2"]

    def test_with_none(self):
        """Test with None spec."""
        result = AgentPackageDockerMcpGateway.from_spec(None)
        assert result is None


class TestAgentMetadataGenerator:
    """Tests for AgentMetadataGenerator.generate method."""

    @pytest.mark.asyncio
    async def test_basic_agent_project(self):
        """Test generating metadata from a basic agent project."""
        spec_yaml = """
agent-package:
  spec-version: v2
  agents:
    - name: Test Agent
      description: A test agent
      version: 1.0.0
      architecture: agent
      reasoning: disabled
      model:
        provider: OpenAI
        name: gpt-4
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
"""
        zip_bytes = create_agent_package_zip(spec_yaml)
        handler = await AgentPackageHandler.from_bytes(zip_bytes)

        try:
            generator = AgentMetadataGenerator(handler)
            result = await generator.generate()

            assert result.name == "Test Agent"
            assert result.description == "A test agent"
            assert result.version == "1.0.0"
            assert result.architecture == "agent"
            assert result.reasoning == "disabled"
            assert result.model is not None
            assert result.model.provider == "OpenAI"
            assert result.model.name == "gpt-4"
        finally:
            handler.close()

    @pytest.mark.asyncio
    async def test_agent_with_mcp_servers(self):
        """Test generating metadata with MCP servers."""
        spec_yaml = """
agent-package:
  spec-version: v2
  agents:
    - name: MCP Agent
      description: Agent with MCP servers
      version: 1.0.0
      architecture: agent
      reasoning: disabled
      model:
        provider: OpenAI
        name: gpt-4
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: my-mcp
          transport: stdio
          command-line:
            - python
            - server.py
"""
        zip_bytes = create_agent_package_zip(spec_yaml)
        handler = await AgentPackageHandler.from_bytes(zip_bytes)

        try:
            generator = AgentMetadataGenerator(handler)
            result = await generator.generate()

            assert len(result.mcp_servers) == 1
            assert result.mcp_servers[0].name == "my-mcp"
            assert result.mcp_servers[0].command == "python"
        finally:
            handler.close()

    @pytest.mark.asyncio
    async def test_missing_spec_file(self):
        """Test error when spec file is missing."""
        # Create a zip with no agent-spec.yaml
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dummy.txt", "dummy content")
        zip_bytes = buffer.getvalue()

        with pytest.raises(
            PlatformHTTPError,
            match="agent-spec.yaml is missing in Agent Package",
        ):
            await AgentPackageHandler.from_bytes(zip_bytes)

    @pytest.mark.asyncio
    async def test_agent_with_docker_mcp_gateway_and_selected_tools(self):
        """Test generating metadata with docker-mcp-gateway and selected-tools.

        This test ensures that:
        1. docker-mcp-gateway with empty server configs captures server names
        2. selected-tools are properly parsed and extracted
        """
        spec_yaml = """
agent-package:
  spec-version: v2
  agents:
  - name: mcp-test-docker
    description: mcp-test-docker
    model:
      provider: LiteLLM
      name: gpt-5-low
    version: 0.0.1
    architecture: agent_platform.architectures.experimental_1
    reasoning: disabled
    runbook: runbook.md
    action-packages: []
    docker-mcp-gateway:
      servers:
        curl: {}
        duckduckgo: {}
        wikipedia-mcp: {}
    knowledge: []
    metadata:
      mode: conversational
    selected-tools:
      tools:
      - name: curl
      - name: extract_key_facts
      - name: fetch_content
      - name: get_article
      - name: search
"""
        zip_bytes = create_agent_package_zip(spec_yaml, {"runbook.md": b"# Runbook"})
        handler = await AgentPackageHandler.from_bytes(zip_bytes)

        try:
            generator = AgentMetadataGenerator(handler)
            result = await generator.generate()

            # Verify docker_mcp_gateway contains the server names
            assert result.docker_mcp_gateway is not None
            assert len(result.docker_mcp_gateway.servers) == 3
            assert "curl" in result.docker_mcp_gateway.servers
            assert "duckduckgo" in result.docker_mcp_gateway.servers
            assert "wikipedia-mcp" in result.docker_mcp_gateway.servers

            # Verify selected_tools are properly extracted
            assert len(result.selected_tools.tools) == 5
            tool_names = [t.name for t in result.selected_tools.tools]
            assert "curl" in tool_names
            assert "extract_key_facts" in tool_names
            assert "fetch_content" in tool_names
            assert "get_article" in tool_names
            assert "search" in tool_names
        finally:
            handler.close()


class TestActionPackageMetadataReader:
    """Tests for ActionPackageMetadataReader.generate_metadata method."""

    @pytest.mark.asyncio
    async def test_basic_action_package(self):
        """Test generating action package metadata."""
        raw_metadata = {
            "metadata": {
                "name": "my-actions",
                "description": "My action package",
                "action_package_version": "1.0.0",
                "secrets": {"API_KEY": {"type": "string"}},
            },
            "openapi.json": {
                "paths": {
                    "/action1": {
                        "post": {
                            "operationId": "action1",
                            "summary": "First action",
                            "description": "Does something",
                            "x-operation-kind": "action",
                        }
                    },
                    "/action2": {
                        "post": {
                            "operationId": "action2",
                            "summary": "Second action",
                            "description": "Does something else",
                        }
                    },
                }
            },
        }

        action_package_spec = SpecActionPackage(
            name="my-actions",
            organization="my-org",
            version="1.0.0",
            path="my-org/my-actions",
            whitelist="action1,action2",
        )

        # Create a mock handler
        handler = create_mock_handler()
        handler.file_exists.return_value = False  # No icon

        reader = ActionPackageMetadataReader(handler)
        result = await reader.get_agent_package_action_packages_metadata(raw_metadata, action_package_spec)

        assert result.name == "my-actions"
        assert result.description == "My action package"
        assert result.version == "1.0.0"
        assert result.whitelist == "action1,action2"
        assert result.path == "my-org"  # Folder path (dirname of full path)
        assert result.full_path == "my-org/my-actions"  # Full path including filename
        assert len(result.actions) == 2
        assert result.actions[0].name == "action1"
        assert result.actions[0].operation_kind == "action"
        # Default operation_kind when not specified
        assert result.actions[1].operation_kind == "action"
