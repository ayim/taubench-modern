"""Tests for SQL generation helper functions in server/kernel/sql.py."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.server.kernel.sql import (
    AgenticSqlStrategy,
    LegacySqlStrategy,
    _create_sql_agent,
    _find_sdm_id_by_name,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_storage():
    """Create a mock storage instance for testing."""
    storage = AsyncMock()
    return storage


@pytest.fixture
def mock_kernel():
    """Create a mock kernel with all necessary attributes for testing."""
    kernel = MagicMock()

    # Mock user
    kernel.user.user_id = "test-user-123"

    # Mock thread
    kernel.thread.thread_id = "test-thread-456"

    # Mock agent
    kernel.agent.platform_configs = {"openai": {"api_key": "test-key"}}
    kernel.agent.agent_architecture = "experimental"

    return kernel


@pytest.fixture
def sample_sdms() -> list[dict[str, Any]]:
    """Sample semantic data models for testing."""
    return [
        {
            "id": "sdm-001",
            "name": "sales_data",
            "description": "Sales data model",
            "tables": [],
        },
        {
            "id": "sdm-002",
            "name": "customer_data",
            "description": "Customer data model",
            "tables": [],
        },
        {
            "id": "sdm-003",
            "name": "inventory_data",
            "description": "Inventory data model",
            "tables": [],
        },
    ]


@pytest.fixture
def mock_data_frame_tools():
    """Create a mock data frame tools instance."""
    return MagicMock()


@pytest.fixture
def simple_sdm_with_engine() -> tuple[SemanticDataModel, str]:
    """A simple semantic data model with DuckDB engine."""
    return cast(
        tuple[SemanticDataModel, str],
        (
            {
                "name": "test_model",
                "description": "A test model",
                "tables": [
                    {
                        "name": "users",
                        "description": "User table",
                        "dimensions": [
                            {"name": "user_id", "expr": "user_id", "data_type": "INTEGER"},
                            {"name": "username", "expr": "username", "data_type": "VARCHAR"},
                        ],
                    }
                ],
            },
            "duckdb",
        ),
    )


@pytest.fixture
def snowflake_sdm_with_variant() -> tuple[SemanticDataModel, str]:
    """Snowflake SDM with VARIANT columns."""
    return cast(
        tuple[SemanticDataModel, str],
        (
            {
                "name": "snowflake_products",
                "tables": [
                    {
                        "name": "products",
                        "dimensions": [
                            {"name": "product_id", "expr": "product_id", "data_type": "INTEGER"},
                            {"name": "metadata", "expr": "metadata", "data_type": "VARIANT"},
                        ],
                    }
                ],
            },
            "snowflake",
        ),
    )


# ============================================================================
# Tests: _find_sdm_id_by_name
# ============================================================================


class TestFindSdmIdByName:
    """Tests for _find_sdm_id_by_name function."""

    @pytest.mark.asyncio
    async def test_finds_sdm_by_exact_name_match(self, mock_storage, sample_sdms):
        """Should successfully find SDM when name matches exactly."""
        # Arrange
        agent_id = "agent-123"
        sdm_name = "customer_data"

        # Mock storage to return SDM IDs and then the SDM data
        mock_storage.get_agent_semantic_data_model_ids.return_value = [
            "sdm-001",
            "sdm-002",
            "sdm-003",
        ]
        mock_storage.get_semantic_data_model.side_effect = sample_sdms

        # Act
        result = await _find_sdm_id_by_name(mock_storage, agent_id, sdm_name)

        # Assert
        assert result == "sdm-002"
        mock_storage.get_agent_semantic_data_model_ids.assert_called_once_with(agent_id)
        assert mock_storage.get_semantic_data_model.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_sdm_name_not_found(self, mock_storage, sample_sdms):
        """Should return None when no SDM matches the requested name."""
        # Arrange
        agent_id = "agent-123"
        sdm_name = "nonexistent_model"

        mock_storage.get_agent_semantic_data_model_ids.return_value = [
            "sdm-001",
            "sdm-002",
            "sdm-003",
        ]
        mock_storage.get_semantic_data_model.side_effect = sample_sdms

        # Act
        result = await _find_sdm_id_by_name(mock_storage, agent_id, sdm_name)

        # Assert
        assert result is None
        assert mock_storage.get_semantic_data_model.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_correct_sdm_when_multiple_exist(self, mock_storage, sample_sdms):
        """Should return the correct SDM ID when multiple SDMs exist."""
        # Arrange
        agent_id = "agent-123"
        sdm_name = "sales_data"

        mock_storage.get_agent_semantic_data_model_ids.return_value = [
            "sdm-001",
            "sdm-002",
            "sdm-003",
        ]
        mock_storage.get_semantic_data_model.side_effect = sample_sdms

        # Act
        result = await _find_sdm_id_by_name(mock_storage, agent_id, sdm_name)

        # Assert
        assert result == "sdm-001"
        mock_storage.get_semantic_data_model.assert_called_once_with("sdm-001")

    @pytest.mark.asyncio
    async def test_handles_empty_sdm_list(self, mock_storage):
        """Should return None when agent has no SDMs."""
        # Arrange
        agent_id = "agent-123"
        sdm_name = "any_model"

        mock_storage.get_agent_semantic_data_model_ids.return_value = []

        # Act
        result = await _find_sdm_id_by_name(mock_storage, agent_id, sdm_name)

        # Assert
        assert result is None
        mock_storage.get_agent_semantic_data_model_ids.assert_called_once_with(agent_id)
        mock_storage.get_semantic_data_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_sdm_with_missing_name_field(self, mock_storage):
        """Should handle SDMs that don't have a 'name' field."""
        # Arrange
        agent_id = "agent-123"
        sdm_name = "test_model"

        mock_storage.get_agent_semantic_data_model_ids.return_value = [
            "sdm-001",
            "sdm-002",
            "sdm-003",
        ]

        # Some SDMs missing the 'name' field, last one has it
        mock_storage.get_semantic_data_model.side_effect = [
            {"id": "sdm-001", "description": "No name field"},
            {"id": "sdm-002"},  # No name field
            {"id": "sdm-003", "name": "test_model"},
        ]

        # Act
        result = await _find_sdm_id_by_name(mock_storage, agent_id, sdm_name)

        # Assert
        assert result == "sdm-003"
        assert mock_storage.get_semantic_data_model.call_count == 3

    @pytest.mark.asyncio
    async def test_handles_sdm_with_none_name(self, mock_storage):
        """Should handle SDMs where 'name' field is None."""
        # Arrange
        agent_id = "agent-123"
        sdm_name = "valid_model"

        mock_storage.get_agent_semantic_data_model_ids.return_value = [
            "sdm-001",
            "sdm-002",
        ]

        mock_storage.get_semantic_data_model.side_effect = [
            {"id": "sdm-001", "name": None},  # None name
            {"id": "sdm-002", "name": "valid_model"},
        ]

        # Act
        result = await _find_sdm_id_by_name(mock_storage, agent_id, sdm_name)

        # Assert
        assert result == "sdm-002"


# ============================================================================
# Tests: LegacySqlStrategy.get_context_additions
# ============================================================================


class TestLegacySqlStrategy:
    """Tests for LegacySqlStrategy.get_context_additions method."""

    @pytest.fixture
    def strategy(self, mock_data_frame_tools):
        """Create a LegacySqlStrategy instance for testing."""
        return LegacySqlStrategy(data_frame_tools=mock_data_frame_tools)

    def test_returns_empty_string_for_empty_models_list(self, strategy):
        """Should return empty string when no models are provided."""
        # Act
        result = strategy.get_context_additions([])

        # Assert
        assert result == ""

    def test_includes_sql_generation_instructions(self, strategy, simple_sdm_with_engine):
        """Should include SQL generation instructions for Legacy strategy."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Legacy strategy includes SQL syntax rules
        assert "SQL SYNTAX RULES" in result or "FROM my_table" in result

    def test_includes_sdm_summary(self, strategy, simple_sdm_with_engine):
        """Should include semantic data model summary."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should contain the model name and table name
        assert "test_model" in result
        assert "users" in result

    def test_includes_snowflake_variant_guidance_for_snowflake_models(
        self, strategy, snowflake_sdm_with_variant
    ):
        """Should include Snowflake VARIANT guidance for Snowflake databases."""
        # Act
        result = strategy.get_context_additions([snowflake_sdm_with_variant])

        # Assert
        # Should have Snowflake-specific VARIANT guidance
        assert "SNOWFLAKE" in result or "VARIANT" in result
        assert "bracket notation" in result.lower() or "col['field']" in result

    def test_handles_multiple_models(
        self, strategy, simple_sdm_with_engine, snowflake_sdm_with_variant
    ):
        """Should handle multiple semantic data models."""
        # Act
        result = strategy.get_context_additions(
            [simple_sdm_with_engine, snowflake_sdm_with_variant]
        )

        # Assert
        # Should contain both model names
        assert "test_model" in result
        assert "snowflake_products" in result


# ============================================================================
# Tests: AgenticSqlStrategy.get_context_additions
# ============================================================================


class TestAgenticSqlStrategy:
    """Tests for AgenticSqlStrategy."""

    @pytest.fixture
    def strategy(self, mock_data_frame_tools):
        """Create an AgenticSqlStrategy instance for testing."""
        return AgenticSqlStrategy(data_frame_tools=mock_data_frame_tools)

    # ========================================================================
    # get_context_additions tests
    # ========================================================================

    def test_returns_empty_string_for_empty_models_list(self, strategy):
        """Should return empty string when no models are provided."""
        # Act
        result = strategy.get_context_additions([])

        # Assert
        assert result == ""

    def test_includes_sdm_summary(self, strategy, simple_sdm_with_engine):
        """Should include semantic data model summary."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should contain the model name
        assert "test_model" in result

    def test_includes_coaching_on_generate_sql_usage(self, strategy, simple_sdm_with_engine):
        """Should include coaching on how to use generate_sql tool."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should mention the generate_sql tool
        assert "generate_sql" in result
        # Should mention choosing semantic data model
        assert "Choose Semantic Data Model" in result or "Semantic Data Model" in result

    def test_includes_coaching_on_create_data_frame_from_sql_usage(
        self, strategy, simple_sdm_with_engine
    ):
        """Should include coaching on when to use create_data_frame_from_sql."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should mention the data_frames_create_from_sql tool (the actual tool name)
        assert "data_frames_create_from_sql" in result

    def test_does_not_include_sql_syntax_instructions(self, strategy, simple_sdm_with_engine):
        """Should NOT include SQL syntax instructions (delegated to sub-agent)."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should NOT have SQL syntax rules (those go to the sub-agent)
        assert "SQL SYNTAX RULES" not in result

    def test_does_not_include_snowflake_variant_guidance(
        self, strategy, snowflake_sdm_with_variant
    ):
        """Should NOT include Snowflake VARIANT guidance (delegated to sub-agent)."""
        # Act
        result = strategy.get_context_additions([snowflake_sdm_with_variant])

        # Assert
        # Should NOT have Snowflake-specific syntax guidance
        # (The banner and detailed VARIANT instructions should not be in parent agent context)
        assert "🚨 CRITICAL: SNOWFLAKE VARIANT" not in result

    def test_includes_status_handling_coaching(self, strategy, simple_sdm_with_engine):
        """Should include coaching on handling different status responses."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should mention different status codes
        assert "success" in result.lower()
        assert "needs_info" in result.lower() or "clarification" in result.lower()
        assert "failure" in result.lower()

    # ========================================================================
    # _create_sql_agent tests (tests the agent factory used by agentic strategy)
    # ========================================================================

    def test_creates_agent_with_correct_name_pattern(self, mock_kernel):
        """Should create agent with name including parent thread ID."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert agent.name == "SQL Generation Agent: test-thread-456"
        assert "test-thread-456" in agent.name

    def test_sets_correct_description(self, mock_kernel):
        """Should set appropriate description for SQL generation agent."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert agent.description == "Generates SQL from natural language queries"

    def test_disables_data_frames_in_agent_settings(self, mock_kernel):
        """Should set enable_data_frames=False in agent settings."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert "agent_settings" in agent.extra
        assert agent.extra["agent_settings"]["enable_data_frames"] is False

    def test_enables_sql_generation_in_agent_settings(self, mock_kernel):
        """Should set enable_sql_generation=True in agent settings."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert "agent_settings" in agent.extra
        assert agent.extra["agent_settings"]["enable_sql_generation"] is True

    def test_inherits_platform_configs_from_parent(self, mock_kernel):
        """Should inherit platform_configs from parent kernel's agent."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert agent.platform_configs == mock_kernel.agent.platform_configs
        assert agent.platform_configs == {"openai": {"api_key": "test-key"}}

    def test_sets_fixed_agent_architecture(self, mock_kernel):
        """Should inherit agent_architecture from parent kernel's agent."""
        from agent_platform.core.agent.agent_architecture import AgentArchitecture

        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert agent.agent_architecture == AgentArchitecture(
            name="agent_platform.architectures.experimental_1", version="2.0.0"
        )

    def test_sets_user_id_from_kernel(self, mock_kernel):
        """Should set user_id from parent kernel's user."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert agent.user_id == mock_kernel.user.user_id
        assert agent.user_id == "test-user-123"

    def test_has_runbook_loaded(self, mock_kernel):
        """Should have runbook_structured set from loaded runbook."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert agent.runbook_structured is not None
        assert hasattr(agent.runbook_structured, "raw_text")

    def test_sets_version(self, mock_kernel):
        """Should set version to 1.0.0."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert agent.version == "1.0.0"

    def test_agent_settings_structure(self, mock_kernel):
        """Should have correct agent_settings structure in extra."""
        # Act
        agent = _create_sql_agent(mock_kernel)

        # Assert
        assert "extra" in dir(agent)
        assert isinstance(agent.extra, dict)
        assert "agent_settings" in agent.extra
        assert isinstance(agent.extra["agent_settings"], dict)
        assert len(agent.extra["agent_settings"]) == 2
        assert set(agent.extra["agent_settings"].keys()) == {
            "enable_data_frames",
            "enable_sql_generation",
        }
