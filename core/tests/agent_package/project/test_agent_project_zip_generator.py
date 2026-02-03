"""Tests for create_agent_project_zip function."""

import zipfile
from collections.abc import AsyncGenerator
from io import BytesIO
from typing import Any

import pytest
import yaml

from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.create import create_agent_project_zip
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.selected_tools import SelectedToolConfig, SelectedTools
from agent_platform.core.semantic_data_model.types import SemanticDataModel
from agent_platform.core.utils.secret_str import SecretString


async def collect_async_generator(gen: AsyncGenerator[bytes, None]) -> bytes:
    """Collect all bytes from an async generator into a single bytes object."""
    result = b""
    async for chunk in gen:
        result += chunk
    return result


def create_minimal_agent(**overrides: Any) -> Agent:
    """Create a minimal Agent instance for testing."""
    from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters

    defaults = {
        "name": "Test Agent",
        "description": "Test Description",
        "user_id": "test_user",
        "version": "1.0.0",
        "runbook_structured": Runbook(raw_text="# Test Runbook\n\nYou are a helpful assistant.", content=[]),
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
        "question_groups": [],
        "mode": "conversational",
        "extra": {},
    }
    defaults.update(overrides)
    return Agent(**defaults)


@pytest.fixture
def sample_semantic_data_models() -> list[SemanticDataModel]:
    """Create sample semantic data models for testing."""
    return [
        SemanticDataModel(
            name="test_model_1",
            description="First test model",
            tables=[
                {
                    "name": "users",
                    "base_table": {
                        "database": "test_db",
                        "schema": "public",
                        "table": "users",
                    },
                    "dimensions": [
                        {"name": "user_id", "expr": "id", "data_type": "INTEGER"},
                    ],
                }
            ],
        ),
        SemanticDataModel(
            name="test_model_2",
            description="Second test model",
            tables=[
                {
                    "name": "orders",
                    "base_table": {
                        "database": "test_db",
                        "schema": "public",
                        "table": "orders",
                    },
                    "dimensions": [
                        {"name": "order_id", "expr": "id", "data_type": "INTEGER"},
                    ],
                }
            ],
        ),
    ]


class TestGenerateAgentProjectZip:
    """Tests for create_agent_project_zip function."""

    @pytest.mark.asyncio
    async def test_generate_minimal_agent_project_zip(self):
        """Test generating a zip file for a minimal agent with no extras."""
        agent = create_minimal_agent()
        semantic_data_models: list[SemanticDataModel] = []

        zip_stream = await create_agent_project_zip(agent, semantic_data_models)
        zip_bytes = await collect_async_generator(zip_stream)

        # Verify zip_bytes is returned
        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0

        # Verify the zip file is valid and contains expected files
        with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
            file_list = zf.namelist()
            # Should contain at least agent-spec.yaml and runbook.md
            assert AgentPackageConfig.agent_spec_filename in file_list
            assert AgentPackageConfig.runbook_filename in file_list

            # Read and parse agent-spec.yaml as YAML
            agent_spec_content = zf.read(AgentPackageConfig.agent_spec_filename).decode("utf-8")
            spec_data = yaml.safe_load(agent_spec_content)

            # Verify YAML structure and content
            assert isinstance(spec_data, dict), "Agent spec should be a valid YAML dictionary"
            assert "agent-package" in spec_data, "Agent spec should have 'agent-package' key"
            assert "agents" in spec_data["agent-package"], "Agent package should have 'agents' list"
            assert len(spec_data["agent-package"]["agents"]) == 1, "Should have exactly one agent"

            agent_data = spec_data["agent-package"]["agents"][0]
            assert agent_data["name"] == "Test Agent", "Agent name should match"
            assert agent_data["version"] == "1.0.0", "Agent version should match"
            assert agent_data["description"] == "Test Description", "Agent description should match"

            # Read and verify runbook.md contains runbook text
            runbook_content = zf.read(AgentPackageConfig.runbook_filename).decode("utf-8")
            assert "Test Runbook" in runbook_content
            assert "helpful assistant" in runbook_content

    @pytest.mark.asyncio
    async def test_create_agent_project_zip_with_semantic_data_models(self, sample_semantic_data_models):
        """Test generating a zip file with semantic data models."""
        agent = create_minimal_agent()

        zip_stream = await create_agent_project_zip(agent, sample_semantic_data_models)
        zip_bytes = await collect_async_generator(zip_stream)

        # Verify zip is created
        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0

        # Verify the zip contains semantic data models
        with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
            file_list = zf.namelist()

            # Should contain semantic data model files
            sdm_dir = AgentPackageConfig.semantic_data_models_dirname
            assert f"{sdm_dir}/test_model_1" in file_list
            assert f"{sdm_dir}/test_model_2" in file_list

            # Read and parse semantic data model content as YAML
            sdm1_content = zf.read(f"{sdm_dir}/test_model_1").decode("utf-8")
            sdm1_data = yaml.safe_load(sdm1_content)
            assert isinstance(sdm1_data, dict), "SDM should be valid YAML dictionary"
            assert sdm1_data["name"] == "test_model_1", "SDM name should match"
            assert sdm1_data["description"] == "First test model", "SDM description should match"
            assert "tables" in sdm1_data, "SDM should have tables"
            assert len(sdm1_data["tables"]) == 1, "SDM should have one table"
            assert sdm1_data["tables"][0]["name"] == "users", "Table name should match"

            sdm2_content = zf.read(f"{sdm_dir}/test_model_2").decode("utf-8")
            sdm2_data = yaml.safe_load(sdm2_content)
            assert isinstance(sdm2_data, dict), "SDM should be valid YAML dictionary"
            assert sdm2_data["name"] == "test_model_2", "SDM name should match"
            assert sdm2_data["description"] == "Second test model", "SDM description should match"
            assert sdm2_data["tables"][0]["name"] == "orders", "Table name should match"

    @pytest.mark.asyncio
    async def test_create_agent_project_zip_with_conversation_guide(self):
        """Test generating a zip file with conversation guide (question groups)."""
        question_groups = [
            QuestionGroup(
                title="Getting Started",
                questions=[
                    "What can you do?",
                    "How do I get started?",
                ],
            ),
            QuestionGroup(
                title="Advanced",
                questions=[
                    "How do I configure advanced settings?",
                ],
            ),
        ]

        agent = create_minimal_agent(question_groups=question_groups)
        semantic_data_models: list[SemanticDataModel] = []

        zip_stream = await create_agent_project_zip(agent, semantic_data_models)
        zip_bytes = await collect_async_generator(zip_stream)

        # Verify the zip contains conversation guide
        with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
            file_list = zf.namelist()
            assert AgentPackageConfig.conversation_guide_filename in file_list

            # Read and parse conversation guide as YAML
            guide_content = zf.read(AgentPackageConfig.conversation_guide_filename).decode("utf-8")
            guide_data = yaml.safe_load(guide_content)

            # Verify YAML structure
            assert isinstance(guide_data, dict), "Conversation guide should be valid YAML dictionary"
            assert "question-groups" in guide_data, "Should have 'question-groups' key"
            assert len(guide_data["question-groups"]) == 2, "Should have 2 question groups"

            # Verify first question group
            first_group = guide_data["question-groups"][0]
            assert first_group["title"] == "Getting Started", "First group title should match"
            assert len(first_group["questions"]) == 2, "First group should have 2 questions"
            assert "What can you do?" in first_group["questions"], "First question should be present"
            assert "How do I get started?" in first_group["questions"], "Second question should be present"

            # Verify second question group
            second_group = guide_data["question-groups"][1]
            assert second_group["title"] == "Advanced", "Second group title should match"
            assert len(second_group["questions"]) == 1, "Second group should have 1 question"
            assert "How do I configure advanced settings?" in second_group["questions"]

    @pytest.mark.asyncio
    async def test_create_agent_project_zip_with_complex_agent(self, sample_semantic_data_models):
        """Test generating a zip file with a complex agent configuration."""
        agent = create_minimal_agent(
            name="Complex Agent With Spaces",
            description="A complex agent for testing",
            version="2.1.0",
            mcp_servers=[
                MCPServer(
                    name="test-mcp",
                    transport="streamable-http",
                    url="https://mcp.test.com",
                ),
            ],
            selected_tools=SelectedTools(
                tools=[
                    SelectedToolConfig(name="search"),
                    SelectedToolConfig(name="calculator"),
                ]
            ),
            extra={
                "agent_settings": {
                    "temperature": 0.7,
                    "max_iterations": 10,
                }
            },
        )

        zip_stream = await create_agent_project_zip(agent, sample_semantic_data_models)
        zip_bytes = await collect_async_generator(zip_stream)

        # Verify the zip is valid
        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0

        # Verify all expected files are present
        with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
            file_list = zf.namelist()
            assert AgentPackageConfig.agent_spec_filename in file_list
            assert AgentPackageConfig.runbook_filename in file_list

            # Parse and verify agent spec YAML structure
            agent_spec_content = zf.read(AgentPackageConfig.agent_spec_filename).decode("utf-8")
            spec_data = yaml.safe_load(agent_spec_content)

            # Verify basic structure
            assert isinstance(spec_data, dict), "Agent spec should be valid YAML dictionary"
            agent_data = spec_data["agent-package"]["agents"][0]
            assert agent_data["name"] == "Complex Agent With Spaces", "Agent name should match"
            assert agent_data["version"] == "2.1.0", "Agent version should match"
            assert agent_data["description"] == "A complex agent for testing", "Description should match"

            # Verify MCP servers
            assert "mcp-servers" in agent_data, "Should have MCP servers section"
            assert len(agent_data["mcp-servers"]) == 1, "Should have one MCP server"
            mcp_server = agent_data["mcp-servers"][0]
            assert mcp_server["name"] == "test-mcp", "MCP server name should match"
            assert mcp_server["transport"] == "streamable-http", "MCP transport should match"
            assert mcp_server["url"] == "https://mcp.test.com", "MCP URL should match"

            # Verify selected tools
            assert "selected-tools" in agent_data, "Should have selected-tools section"
            assert "tools" in agent_data["selected-tools"], "Should have tools list"
            tools = agent_data["selected-tools"]["tools"]
            assert len(tools) == 2, "Should have 2 selected tools"
            tool_names = [t["name"] for t in tools]
            assert "search" in tool_names, "Should have search tool"
            assert "calculator" in tool_names, "Should have calculator tool"

            # Verify agent settings
            assert "agent-settings" in agent_data, "Should have agent-settings section"
            assert agent_data["agent-settings"]["temperature"] == 0.7, "Temperature should match"
            assert agent_data["agent-settings"]["max_iterations"] == 10, "Max iterations should match"

    @pytest.mark.asyncio
    async def test_generated_zip_can_be_read_by_agent_package_handler(self):
        """Test that the generated zip can be read back by AgentPackageHandler."""
        agent = create_minimal_agent(
            name="Readable Agent",
            version="1.5.0",
        )
        semantic_data_models: list[SemanticDataModel] = []

        # Generate the zip
        zip_stream = await create_agent_project_zip(agent, semantic_data_models)
        zip_bytes = await collect_async_generator(zip_stream)

        # Verify the zip can be read by AgentPackageHandler
        with await AgentPackageHandler.from_bytes(zip_bytes) as handler:
            # Verify we can read the spec
            spec = await handler.read_agent_spec()
            assert spec is not None
            assert spec.agent_package.agents[0].name == "Readable Agent"
            assert spec.agent_package.agents[0].version == "1.5.0"

            # Verify we can read the runbook
            runbook = await handler.read_runbook()
            assert isinstance(runbook, str)
            assert len(runbook) > 0

    @pytest.mark.asyncio
    async def test_create_agent_project_zip_with_various_agent_names(self):
        """Test that agent project zips can be created with various agent names."""
        test_cases = [
            ("Simple Agent", "1.0.0"),
            ("Agent-With-Dashes", "2.0.0"),
            ("Agent With Spaces", "3.0.0"),
            ("Agent_With_Underscores", "4.0.0"),
            ("Agent!@#$%Special", "5.0.0"),
        ]

        for agent_name, version in test_cases:
            agent = create_minimal_agent(name=agent_name, version=version)
            semantic_data_models: list[SemanticDataModel] = []

            zip_stream = await create_agent_project_zip(agent, semantic_data_models)
            zip_bytes = await collect_async_generator(zip_stream)

            # Verify the zip is valid and can be read
            assert isinstance(zip_bytes, bytes)
            assert len(zip_bytes) > 0
            with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
                assert AgentPackageConfig.agent_spec_filename in zf.namelist()

    @pytest.mark.asyncio
    async def test_create_agent_project_zip_empty_semantic_data_models(self):
        """Test that empty semantic data models list doesn't create SDM files."""
        agent = create_minimal_agent()
        semantic_data_models: list[SemanticDataModel] = []

        zip_stream = await create_agent_project_zip(agent, semantic_data_models)
        zip_bytes = await collect_async_generator(zip_stream)

        # Verify no semantic data model files are created
        with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
            file_list = zf.namelist()
            sdm_files = [f for f in file_list if f.startswith(AgentPackageConfig.semantic_data_models_dirname + "/")]
            assert len(sdm_files) == 0
