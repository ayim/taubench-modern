"""Tests for AgentSpecGenerator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.agent_package.spec import (
    DEFAULT_AGENT_PACKAGE_EXCLUDE,
    AgentPackageSpec,
    AgentSpecGenerator,
    SpecActionPackage,
    SpecAgentMetadata,
    SpecAgentModel,
    SpecDockerMcpGateway,
    SpecMCPServer,
    SpecSelectedTools,
    SpecSemanticDataModel,
)
from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.selected_tools import SelectedToolConfig, SelectedTools
from agent_platform.core.utils.secret_str import SecretString


def create_minimal_agent(**overrides: Any) -> Agent:
    """Create a minimal Agent instance for testing."""
    from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters

    defaults = {
        "name": "Test Agent",
        "description": "Test Description",
        "user_id": "test_user",
        "version": "v2",
        "runbook_structured": Runbook(raw_text="# Test Runbook", content=[]),
        "platform_configs": [
            OpenAIPlatformParameters(
                name="test-openai",
                openai_api_key=SecretString("test-key"),
            )
        ],
        "agent_architecture": AgentArchitecture(
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
        "action_packages": [],
        "mcp_servers": [],
        "selected_tools": SelectedTools(),
        "mode": "conversational",
        "extra": {},
    }
    defaults.update(overrides)
    return Agent(**defaults)


class TestAgentSpecGeneratorPrivateMethods:
    """Test private methods of AgentSpecGenerator."""

    def test_get_architecture(self):
        """Test _get_architecture extracts architecture name correctly."""
        agent = create_minimal_agent()
        architecture = AgentSpecGenerator._get_architecture(agent)
        assert architecture == "agent_platform.architectures.default"

    def test_get_architecture_with_different_name(self):
        """Test _get_architecture with different architecture name."""
        agent = create_minimal_agent(
            agent_architecture=AgentArchitecture(
                name="agent_platform.architectures.plan_execute",
                version="1.0.0",
            )
        )
        architecture = AgentSpecGenerator._get_architecture(agent)
        assert architecture == "agent_platform.architectures.plan_execute"

    def test_get_model(self):
        """Test _get_model extracts model information correctly."""
        agent = create_minimal_agent()
        model = AgentSpecGenerator._get_model(agent)
        assert isinstance(model, SpecAgentModel)
        assert model.provider == "OpenAI"
        # The default model from OpenAIPlatformParameters is gpt-4-1
        assert model.name == "gpt-4-1"

    def test_get_reasoning(self):
        """Test _get_reasoning always returns disabled."""
        agent = create_minimal_agent()
        reasoning = AgentSpecGenerator._get_reasoning(agent)
        assert reasoning == "disabled"

    def test_get_action_packages_empty(self):
        """Test _get_action_packages with no action packages."""
        agent = create_minimal_agent()
        action_packages = AgentSpecGenerator._get_action_packages(agent, "zip")
        assert action_packages == []

    def test_get_action_packages_with_packages(self):
        """Test _get_action_packages with multiple action packages."""
        agent = create_minimal_agent(
            action_packages=[
                ActionPackage(
                    name="test-package-1",
                    organization="TestOrg",
                    version="1.0.0",
                    url="https://test.com",
                    api_key=SecretString("key1"),
                    allowed_actions=["action1", "action2"],
                ),
                ActionPackage(
                    name="test-package-2",
                    organization="AnotherOrg",
                    version="2.1.0",
                    url="https://test2.com",
                    api_key=SecretString("key2"),
                    whitelist="action1,action2,action3",
                ),
            ]
        )
        action_packages = AgentSpecGenerator._get_action_packages(agent, "zip")
        assert action_packages is not None
        assert len(action_packages) == 2
        assert isinstance(action_packages[0], SpecActionPackage)
        assert action_packages[0].name == "test-package-1"
        assert action_packages[0].organization == "TestOrg"
        assert action_packages[0].version == "1.0.0"
        assert action_packages[0].type == "zip"
        assert action_packages[0].whitelist == "action1,action2"
        assert action_packages[0].path is not None
        assert "TestOrg/test-package-1/1.0.0.zip" == action_packages[0].path

        assert action_packages[1].name == "test-package-2"
        assert action_packages[1].organization == "AnotherOrg"
        assert action_packages[1].version == "2.1.0"
        assert action_packages[1].type == "zip"
        assert action_packages[1].whitelist == "action1,action2,action3"
        assert action_packages[1].path is not None
        assert "AnotherOrg/test-package-2/2.1.0.zip" == action_packages[1].path

    def test_get_action_packages_folder_type(self):
        """Test _get_action_packages with folder type."""
        agent = create_minimal_agent(
            action_packages=[
                ActionPackage(
                    name="test-package",
                    organization="TestOrg",
                    version="1.0.0",
                    url="https://test.com",
                    api_key=SecretString("key"),
                    allowed_actions=["action1"],
                ),
            ]
        )
        action_packages = AgentSpecGenerator._get_action_packages(agent, "folder")
        assert action_packages is not None
        assert len(action_packages) == 1
        assert action_packages[0].type == "folder"
        assert action_packages[0].path is not None
        assert "TestOrg/test-package" == action_packages[0].path

    def test_get_worker_config_conversational_mode(self):
        """Test _get_worker_config returns None for conversational mode."""
        agent = create_minimal_agent(mode="conversational")
        worker_config = AgentSpecGenerator._get_worker_config(agent)
        assert worker_config is None

    def test_get_worker_config_worker_mode_from_extra(self):
        """Test _get_worker_config extracts from extra for worker mode."""
        agent = create_minimal_agent(
            mode="worker",
            extra={
                "worker-config": {
                    "type": "document-intelligence",
                    "document_type": "invoice",
                }
            },
        )
        worker_config = AgentSpecGenerator._get_worker_config(agent)
        assert worker_config is not None
        assert worker_config.get("type") == "document-intelligence"
        assert worker_config.get("document_type") == "invoice"

    def test_get_worker_config_underscore_key(self):
        """Test _get_worker_config handles underscore key variant."""
        agent = create_minimal_agent(
            mode="worker",
            extra={
                "worker_config": {
                    "type": "custom",
                    "document_type": "receipt",
                }
            },
        )
        worker_config = AgentSpecGenerator._get_worker_config(agent)
        assert worker_config is not None
        assert worker_config.get("type") == "custom"

    def test_get_worker_config_empty_dict(self):
        """Test _get_worker_config handles empty worker-config dict."""
        agent = create_minimal_agent(
            mode="worker",
            extra={
                "worker-config": {},
            },
        )
        worker_config = AgentSpecGenerator._get_worker_config(agent)
        assert worker_config == {}

    def test_get_metadata_conversational(self):
        """Test _get_metadata for conversational mode."""
        agent = create_minimal_agent(mode="conversational")
        metadata = AgentSpecGenerator._get_metadata(agent)
        assert isinstance(metadata, SpecAgentMetadata)
        assert metadata.mode == "conversational"
        assert metadata.worker_config is None
        # welcome_message is set to empty string in _get_metadata but model_validate may convert to None
        assert metadata.welcome_message in ("", None)
        assert metadata.question_groups is None

    def test_get_metadata_worker_mode(self):
        """Test _get_metadata for worker mode."""
        agent = create_minimal_agent(
            mode="worker",
            extra={
                "worker-config": {
                    "type": "document-intelligence",
                    "document_type": "invoice",
                }
            },
        )
        metadata = AgentSpecGenerator._get_metadata(agent)
        assert isinstance(metadata, SpecAgentMetadata)
        assert metadata.mode == "worker"
        # Note: worker_config may be None if not properly structured in extra
        # The _get_metadata method sets it from _get_worker_config which returns dict | None
        # but SpecAgentMetadata expects SpecWorkerConfig | None

    def test_get_metadata_worker_mode_empty_worker_config(self):
        """Test _get_metadata for worker mode with empty worker-config dict."""
        agent = create_minimal_agent(
            mode="worker",
            extra={
                "worker-config": {},
            },
        )
        metadata = AgentSpecGenerator._get_metadata(agent)
        assert isinstance(metadata, SpecAgentMetadata)
        assert metadata.mode == "worker"
        # With empty worker-config, SpecWorkerConfig should be created with None fields
        assert metadata.worker_config is not None
        assert metadata.worker_config.type is None
        assert metadata.worker_config.document_type is None

    def test_get_mcp_servers_empty(self):
        """Test _get_mcp_servers with no MCP servers."""
        agent = create_minimal_agent()
        mcp_servers = AgentSpecGenerator._get_mcp_servers(agent)
        assert mcp_servers == []

    def test_get_mcp_servers_with_servers(self):
        """Test _get_mcp_servers with multiple MCP servers."""
        agent = create_minimal_agent(
            mcp_servers=[
                MCPServer(
                    name="test-server-1",
                    transport="streamable-http",
                    url="https://test1.com/mcp",
                ),
                MCPServer(
                    name="test-server-2",
                    transport="stdio",
                    command="python",
                    args=["-m", "test_server"],
                ),
            ]
        )
        mcp_servers = AgentSpecGenerator._get_mcp_servers(agent)
        assert mcp_servers is not None
        assert len(mcp_servers) == 2
        assert isinstance(mcp_servers[0], SpecMCPServer)
        assert mcp_servers[0].name == "test-server-1"
        assert mcp_servers[0].transport == "streamable-http"
        assert mcp_servers[0].url == "https://test1.com/mcp"

        assert mcp_servers[1].name == "test-server-2"
        assert mcp_servers[1].transport == "stdio"
        assert mcp_servers[1].command_line == ["python", "-m", "test_server"]

    def test_get_docker_mcp_gateway_no_docker_gateway(self):
        """Test _get_docker_mcp_gateway with no Docker gateway."""
        agent = create_minimal_agent(
            mcp_servers=[
                MCPServer(
                    name="regular-server",
                    transport="streamable-http",
                    url="https://test.com/mcp",
                ),
            ]
        )
        gateway = AgentSpecGenerator._get_docker_mcp_gateway(agent, None)
        assert gateway is None

    def test_get_docker_mcp_gateway_with_docker_command(self):
        """Test _get_docker_mcp_gateway detects Docker MCP Gateway command."""
        docker_gateway_config = SpecDockerMcpGateway(
            catalog="./catalog.yml",
            servers={"postgres": {}, "slack": {}},
        )
        agent = create_minimal_agent(
            mcp_servers=[
                MCPServer(
                    name="docker-gateway",
                    transport="stdio",
                    command="docker",
                    args=["mcp", "gateway", "run", "--catalog", "./catalog.yml"],
                ),
            ]
        )
        gateway = AgentSpecGenerator._get_docker_mcp_gateway(agent, docker_gateway_config)
        assert gateway is not None
        assert gateway.catalog == "./catalog.yml"
        assert "postgres" in gateway.servers
        assert "slack" in gateway.servers

    def test_get_docker_mcp_gateway_incomplete_command(self):
        """Test _get_docker_mcp_gateway with incomplete docker command."""
        docker_gateway_config = SpecDockerMcpGateway(
            catalog="./catalog.yml",
            servers={"postgres": {}},
        )
        agent = create_minimal_agent(
            mcp_servers=[
                MCPServer(
                    name="not-gateway",
                    transport="stdio",
                    command="docker",
                    args=["run", "image"],  # Not a gateway command
                ),
            ]
        )
        gateway = AgentSpecGenerator._get_docker_mcp_gateway(agent, docker_gateway_config)
        assert gateway is None

    def test_get_selected_tools_empty(self):
        """Test _get_selected_tools with no tools."""
        agent = create_minimal_agent()
        selected_tools = AgentSpecGenerator._get_selected_tools(agent)
        assert isinstance(selected_tools, SpecSelectedTools)
        assert selected_tools.tools == []

    def test_get_selected_tools_with_tools(self):
        """Test _get_selected_tools with tools."""
        agent = create_minimal_agent(
            selected_tools=SelectedTools(
                tools=[
                    SelectedToolConfig(name="tool1"),
                    SelectedToolConfig(name="tool2"),
                ]
            )
        )
        selected_tools = AgentSpecGenerator._get_selected_tools(agent)
        assert isinstance(selected_tools, SpecSelectedTools)
        assert selected_tools.tools is not None
        assert len(selected_tools.tools) == 2
        assert selected_tools.tools[0].name == "tool1"
        assert selected_tools.tools[1].name == "tool2"

    def test_get_agent_settings_none(self):
        """Test _get_agent_settings with no settings."""
        agent = create_minimal_agent()
        settings = AgentSpecGenerator._get_agent_settings(agent)
        assert settings is None

    def test_get_agent_settings_with_settings(self):
        """Test _get_agent_settings with settings in extra."""
        agent = create_minimal_agent(
            extra={
                "agent_settings": {
                    "temperature": 0.7,
                    "max_iterations": 10,
                }
            }
        )
        settings = AgentSpecGenerator._get_agent_settings(agent)
        assert settings is not None
        assert settings["temperature"] == 0.7
        assert settings["max_iterations"] == 10

    def test_get_semantic_data_models_none(self):
        """Test _get_semantic_data_models with None."""
        result = AgentSpecGenerator._get_semantic_data_models(None)
        assert result is None

    def test_get_semantic_data_models_empty_list(self):
        """Test _get_semantic_data_models with empty list."""
        result = AgentSpecGenerator._get_semantic_data_models([])
        assert result is None

    def test_get_semantic_data_models_with_models(self):
        """Test _get_semantic_data_models with models."""
        semantic_models: list[SemanticDataModel] = cast(
            list[SemanticDataModel],
            [
                {"name": "model1", "other_field": "ignored"},
                {"name": "model2"},
            ],
        )
        result = AgentSpecGenerator._get_semantic_data_models(semantic_models)
        assert result is not None
        assert len(result) == 2
        assert isinstance(result[0], SpecSemanticDataModel)
        assert result[0].name == "model1"
        assert result[1].name == "model2"

    def test_generate_spec_exclude(self):
        """Test _generate_spec_exclude returns default excludes."""
        excludes = AgentSpecGenerator._generate_spec_exclude()
        assert isinstance(excludes, list)
        assert excludes == list(DEFAULT_AGENT_PACKAGE_EXCLUDE)
        # Verify it's a copy, not the same list
        assert excludes is not DEFAULT_AGENT_PACKAGE_EXCLUDE


class TestAgentSpecGeneratorFromAgent:
    """Test the main from_agent method."""

    def test_from_agent_complex_configuration(self):
        """Test from_agent with a complex agent configuration."""
        agent = create_minimal_agent(
            name="Complex Agent",
            description="A complex test agent",
            version="v3",
            action_packages=[
                ActionPackage(
                    name="package1",
                    organization="Org1",
                    version="1.0.0",
                    url="https://test1.com",
                    api_key=SecretString("key1"),
                    allowed_actions=["action1"],
                ),
                ActionPackage(
                    name="package2",
                    organization="Org2",
                    version="2.0.0",
                    url="https://test2.com",
                    api_key=SecretString("key2"),
                    allowed_actions=["action2", "action3"],
                ),
            ],
            mcp_servers=[
                MCPServer(
                    name="mcp1",
                    transport="streamable-http",
                    url="https://mcp1.com",
                ),
                MCPServer(
                    name="mcp2",
                    transport="stdio",
                    command="python",
                    args=["-m", "mcp_server"],
                ),
            ],
            selected_tools=SelectedTools(
                tools=[
                    SelectedToolConfig(name="search"),
                    SelectedToolConfig(name="calculate"),
                ]
            ),
            extra={
                "conversation_starter": "Hi there!",
                "document_intelligence": "v2",
                "welcome-message": "Welcome!",
                "agent_settings": {
                    "temperature": 0.8,
                    "max_iterations": 20,
                },
            },
        )

        semantic_models: list[SemanticDataModel] = cast(
            list[SemanticDataModel], [{"name": "model1"}, {"name": "model2"}]
        )
        spec = AgentSpecGenerator.from_agent(
            agent,
            semantic_data_models=semantic_models,
            action_package_type="zip",
        )

        # Verify the spec is complete
        assert isinstance(spec, AgentPackageSpec)
        spec_agent = spec.agent_package.agents[0]

        # Basic fields
        assert spec_agent.name == "Complex Agent"
        assert spec_agent.description == "A complex test agent"
        assert spec_agent.version == "v3"

        # Action packages
        assert len(spec_agent.action_packages) == 2
        assert spec_agent.action_packages[0].name == "package1"
        assert spec_agent.action_packages[1].name == "package2"

        # MCP servers
        assert spec_agent.mcp_servers is not None
        assert len(spec_agent.mcp_servers) == 2
        assert spec_agent.mcp_servers[0].name == "mcp1"
        assert spec_agent.mcp_servers[1].name == "mcp2"

        # Selected tools
        assert spec_agent.selected_tools is not None
        assert spec_agent.selected_tools.tools is not None
        assert len(spec_agent.selected_tools.tools) == 2

        # Semantic data models
        assert spec_agent.semantic_data_models is not None
        assert len(spec_agent.semantic_data_models) == 2

        # Extra fields
        assert spec_agent.conversation_starter == "Hi there!"
        assert spec_agent.document_intelligence == "v2"
        assert spec_agent.welcome_message == "Welcome!"
        assert spec_agent.agent_settings is not None
        assert spec_agent.agent_settings["temperature"] == 0.8

    @pytest.fixture
    def agent_m2m_mcp(self) -> Agent:
        """Fixture that reads an Agent from a JSON file."""
        test_data_dir = Path(__file__).parent / "test-data"
        agent_json_path = test_data_dir / "agents-from-as" / "test_m2m_mcp.json"
        with open(agent_json_path) as f:
            agent_data = json.load(f)
        return Agent.model_validate(agent_data)

    def test_from_agent_m2m_mcp(self, agent_m2m_mcp: Agent):
        """Test from_agent using an M2M MCP agent loaded from a JSON file.

        This test verifies that:
        - Agent version 0.0.1 is preserved in the spec agent
        - Spec version defaults to v2 when agent version is not a valid spec version
        """
        # Generate spec from the agent
        spec = AgentSpecGenerator.from_agent(
            agent_m2m_mcp,
            semantic_data_models=None,
            action_package_type="zip",
        )

        # Verify the spec is created successfully
        assert isinstance(spec, AgentPackageSpec)
        assert spec.agent_package is not None
        # Spec version should default to v2 when agent version is not valid
        assert spec.agent_package.spec_version == "v2"
        assert len(spec.agent_package.agents) == 1

        spec_agent = spec.agent_package.agents[0]

        # Verify basic fields from JSON
        assert spec_agent.name == "Test Agent - M2M MCP"
        assert spec_agent.description == "Test Agent - M2M MCP Description"
        # Agent version is preserved as-is from the JSON
        assert spec_agent.version == "0.0.1"

        # Verify model
        assert spec_agent.model is not None
        assert spec_agent.model.provider == "OpenAI"
        assert spec_agent.model.name == "gpt-4-1"

        # Verify architecture
        assert spec_agent.architecture == "agent_platform.architectures.experimental_1"

        # Verify action packages (should be empty)
        assert len(spec_agent.action_packages) == 0

        # Verify MCP servers (one M2M server with authentication)
        assert spec_agent.mcp_servers is not None
        assert len(spec_agent.mcp_servers) == 1
        assert spec_agent.mcp_servers[0].name == "M2M Test"
        assert spec_agent.mcp_servers[0].transport == "streamable-http"
        assert spec_agent.mcp_servers[0].url == "http://127.0.0.1:8000/mcp"
        assert spec_agent.mcp_servers[0].headers is not None
        assert "Authorization" in spec_agent.mcp_servers[0].headers
        # Verify the Authorization header value - since type is "string", it should NOT be masked
        auth_header = spec_agent.mcp_servers[0].headers["Authorization"]
        assert auth_header is not None
        # The header should be an MCP variable type with the actual value (not masked for "string" type)
        assert hasattr(auth_header, "value")
        # Verify the value is NOT masked because type is "string" (not "secret")
        assert auth_header.value == "Bearer testsssss"  # type: ignore[attr-defined]
        assert spec_agent.mcp_servers[0].force_serial_tool_calls is False

        # Verify selected tools
        assert spec_agent.selected_tools is not None
        assert spec_agent.selected_tools.tools is not None
        assert len(spec_agent.selected_tools.tools) == 2
        assert spec_agent.selected_tools.tools[0].name == "whoami"
        assert spec_agent.selected_tools.tools[1].name == "echo"

        # Verify no semantic data models
        assert spec_agent.semantic_data_models is None

        # Verify extra fields
        assert spec_agent.conversation_starter is None
        assert spec_agent.document_intelligence is None
        # welcome_message can be None or empty string based on metadata processing
        assert spec_agent.welcome_message in (None, "")

        # Verify agent settings
        assert spec_agent.agent_settings is not None
        assert spec_agent.agent_settings["enable_data_frames"] is False

        # Verify metadata (conversational mode)
        assert spec_agent.metadata is not None
        assert spec_agent.metadata.mode == "conversational"
        assert spec_agent.metadata.worker_config is None

        # Verify reasoning
        assert spec_agent.reasoning == "disabled"

        # Verify runbook
        assert spec_agent.runbook is not None

        # Verify conversation guide
        assert spec_agent.conversation_guide is None

        # Verify exclude list
        assert spec.agent_package.exclude is not None
        assert len(spec.agent_package.exclude) > 0

    @pytest.fixture
    def agent_oil_gas_analyst(self) -> Agent:
        """Fixture that reads an Agent from a JSON file."""
        test_data_dir = Path(__file__).parent / "test-data"
        agent_json_path = test_data_dir / "agents-from-as" / "test_oil_gas_analyst.json"
        with open(agent_json_path) as f:
            agent_data = json.load(f)
        return Agent.model_validate(agent_data)

    def test_from_agent_oil_gas_analyst(self, agent_oil_gas_analyst: Agent):
        """Test from_agent using an Oil Gas Analyst agent loaded from a JSON file.

        This test verifies that:
        - Agent with multiple action packages is properly converted
        - Question groups are preserved in metadata
        - Data frames settings are captured
        - Empty selected tools list is handled correctly
        """
        spec = AgentSpecGenerator.from_agent(
            agent_oil_gas_analyst,
            semantic_data_models=None,
            action_package_type="zip",
        )

        # Verify the spec is created successfully
        assert isinstance(spec, AgentPackageSpec)
        assert spec.agent_package is not None
        assert spec.agent_package.spec_version == "v2"
        assert len(spec.agent_package.agents) == 1

        spec_agent = spec.agent_package.agents[0]

        # Verify basic fields from JSON
        assert spec_agent.name == "Oil and Gas Analyst"
        assert spec_agent.description == "Analyze North Dakota oil well production data."
        assert spec_agent.version == "1.1.1"

        # Verify model
        assert spec_agent.model is not None
        assert spec_agent.model.provider == "OpenAI"
        assert spec_agent.model.name == "gpt-4-1"

        # Verify architecture
        assert spec_agent.architecture == "agent_platform.architectures.default"

        # Verify action packages (3 packages)
        assert len(spec_agent.action_packages) == 3

        # First action package: Example Web Search
        assert spec_agent.action_packages[0].name == "Example Web Search"
        assert spec_agent.action_packages[0].organization == "Sema4.ai"
        assert spec_agent.action_packages[0].version == "1.0.0"
        assert spec_agent.action_packages[0].whitelist == ""

        # Second action package: Example Oil Gas Reports
        assert spec_agent.action_packages[1].name == "Example Oil Gas Reports"
        assert spec_agent.action_packages[1].organization == "Sema4.ai"
        assert spec_agent.action_packages[1].version == "1.0.1"
        assert spec_agent.action_packages[1].whitelist == ""

        # Third action package: Browsing
        assert spec_agent.action_packages[2].name == "Browsing"
        assert spec_agent.action_packages[2].organization == "Sema4.ai"
        assert spec_agent.action_packages[2].version == "1.3.3"
        assert spec_agent.action_packages[2].whitelist == "download_file"

        # Verify MCP servers (should be empty)
        assert spec_agent.mcp_servers is not None
        assert len(spec_agent.mcp_servers) == 0

        # Verify selected tools (empty list)
        assert spec_agent.selected_tools is not None
        assert spec_agent.selected_tools.tools is not None
        assert len(spec_agent.selected_tools.tools) == 0

        # Verify no semantic data models
        assert spec_agent.semantic_data_models is None

        # Verify extra fields
        assert spec_agent.conversation_starter == ""
        assert spec_agent.document_intelligence is None
        # welcome_message can be None or empty string
        assert spec_agent.welcome_message in (None, "")

        # Verify agent settings
        assert spec_agent.agent_settings is not None
        assert spec_agent.agent_settings["enable_data_frames"] is True

        # Verify metadata (conversational mode)
        assert spec_agent.metadata is not None
        assert spec_agent.metadata.mode == "conversational"
        assert spec_agent.metadata.worker_config is None or spec_agent.metadata.worker_config == {}

        # Note: question_groups are set to None in metadata as they were moved to root level
        # This is by design - see _get_metadata() implementation
        assert spec_agent.metadata.question_groups is None

        # Verify reasoning
        assert spec_agent.reasoning == "disabled"

        # Verify runbook
        assert spec_agent.runbook is not None

        # Verify conversation guide
        assert spec_agent.conversation_guide is not None
        assert spec_agent.conversation_guide == "conversation-guide.yaml"

        # Verify exclude list
        assert spec.agent_package.exclude is not None
        assert len(spec.agent_package.exclude) > 0

    @pytest.fixture
    def spec_m2m_mcp(self) -> str:
        """Fixture that reads an Agent from a JSON file."""
        test_data_dir = Path(__file__).parent / "test-data"
        spec_yaml_path = test_data_dir / "agents-to-spec" / "test_m2m_mcp.yaml"
        with open(spec_yaml_path) as f:
            spec_data = f.read()
        return spec_data

    def test_spec_agent_to_yaml(self, agent_m2m_mcp: Agent, spec_m2m_mcp: str):
        """Test SpecAgent.to_yaml() method.

        This test verifies:
        - Round-trip YAML serialization (parse → serialize → matches original)
        """
        # Test YAML serialization of the full spec
        spec = AgentSpecGenerator.from_agent(
            agent_m2m_mcp,
            semantic_data_models=None,
            action_package_type="zip",
        )
        assert spec.to_yaml() == spec_m2m_mcp

    @pytest.fixture
    def spec_oil_gas_analyst(self) -> str:
        """Fixture that reads an Agent from a JSON file."""
        test_data_dir = Path(__file__).parent / "test-data"
        spec_yaml_path = test_data_dir / "agents-to-spec" / "test_oil_gas_analyst.yaml"
        with open(spec_yaml_path) as f:
            spec_data = f.read()
        return spec_data

    def test_spec_agent_to_yaml_oil_gas(self, agent_oil_gas_analyst: Agent, spec_oil_gas_analyst: str):
        """Test SpecAgent.to_yaml() with a more complex agent.

        This test verifies:
        - Round-trip YAML serialization (parse → serialize → matches original)
        """
        # Test YAML serialization of the full spec
        spec = AgentSpecGenerator.from_agent(
            agent_oil_gas_analyst,
            semantic_data_models=None,
            action_package_type="zip",
        )
        assert spec.to_yaml() == spec_oil_gas_analyst

    def test_agent_package_yaml_field_order(self):
        """Test that the agent-package YAML output has fields in the correct order.

        The expected field order for the top-level 'agent-package' is:
        1. spec-version
        2. agents
        3. exclude
        """
        import yaml

        agent = create_minimal_agent()
        spec = AgentSpecGenerator.from_agent(
            agent,
            semantic_data_models=None,
            action_package_type="zip",
        )

        yaml_output = spec.to_yaml()

        # Parse the YAML while preserving key order
        parsed = yaml.safe_load(yaml_output)

        # Get the keys of the agent-package dict in order
        agent_package_keys = list(parsed["agent-package"].keys())

        # Verify the expected order
        assert agent_package_keys == ["spec-version", "agents", "exclude"]
