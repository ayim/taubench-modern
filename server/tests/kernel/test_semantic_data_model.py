import pytest

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.data_frames.semantic_data_model_validation import References
from agent_platform.server.data_frames.semantic_data_model_collector import (
    SemanticDataModelAndReferences,
)
from agent_platform.server.kernel.semantic_data_model import (
    get_semantic_data_models_with_engines,
    summarize_data_models,
)
from agent_platform.server.kernel.sql import _get_sql_generation_instructions

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def simple_sdm() -> SemanticDataModel:
    """Simple semantic data model without special columns."""
    return SemanticDataModel.model_validate(
        {
            "name": "test_model",
            "description": "A test model",
            "tables": [
                {
                    "name": "users",
                    "base_table": {},
                    "description": "User table",
                    "dimensions": [
                        {"name": "user_id", "expr": "user_id", "data_type": "INTEGER"},
                        {"name": "username", "expr": "username", "data_type": "VARCHAR"},
                    ],
                }
            ],
        },
    )


@pytest.fixture
def snowflake_sdm_with_variant() -> SemanticDataModel:
    """Snowflake SDM with VARIANT columns."""
    return SemanticDataModel.model_validate(
        {
            "name": "snowflake_products",
            "tables": [
                {
                    "name": "products",
                    "base_table": {},
                    "dimensions": [
                        {"name": "product_id", "expr": "product_id", "data_type": "INTEGER"},
                        {"name": "metadata", "expr": "metadata", "data_type": "VARIANT"},
                    ],
                    "facts": [
                        {"name": "attributes", "expr": "attributes", "data_type": "OBJECT"},
                    ],
                }
            ],
        },
    )


@pytest.fixture
def postgres_sdm_with_json() -> SemanticDataModel:
    """PostgreSQL SDM with JSON/JSONB columns."""
    return SemanticDataModel.model_validate(
        {
            "name": "postgres_documents",
            "tables": [
                {
                    "name": "documents",
                    "base_table": {},
                    "dimensions": [
                        {"name": "doc_id", "expr": "doc_id", "data_type": "INTEGER"},
                        {"name": "content", "expr": "content", "data_type": "JSON"},
                        {"name": "metadata", "expr": "metadata", "data_type": "JSONB"},
                    ],
                }
            ],
        },
    )


@pytest.fixture
def mysql_sdm_with_json() -> SemanticDataModel:
    """MySQL SDM with JSON columns."""
    return SemanticDataModel.model_validate(
        {
            "name": "mysql_events",
            "tables": [
                {
                    "name": "events",
                    "base_table": {},
                    "dimensions": [
                        {"name": "event_id", "expr": "event_id", "data_type": "INTEGER"},
                        {"name": "payload", "expr": "payload", "data_type": "JSON"},
                    ],
                }
            ],
        },
    )


# ============================================================================
# Tests: sdm_sql_prompters functions
# ============================================================================


class TestSdmSqlPrompters:
    """Tests for sdm_sql_prompters functions."""

    # ========================================================================
    # summarize_data_models tests
    # ========================================================================

    def test_empty_models_returns_no_models_message(self):
        """Empty model list should return appropriate message."""
        result = summarize_data_models([])

        assert "no semantic data models" in result.lower()

    def test_sdm_name_appears_in_summary(self, simple_sdm: SemanticDataModel):
        """SDM name should appear in the summary output."""
        result = summarize_data_models([(simple_sdm, "duckdb")])

        assert "test_model" in result

    def test_multiple_sdm_names_appear_in_summary(self, simple_sdm: SemanticDataModel):
        """All SDM names should appear when multiple models provided."""
        sdm2 = SemanticDataModel.model_validate({**simple_sdm.model_dump(), "name": "second_model"})
        sdm3 = SemanticDataModel.model_validate({**simple_sdm.model_dump(), "name": "third_model"})

        result = summarize_data_models(
            [
                (simple_sdm, "duckdb"),
                (sdm2, "postgres"),
                (sdm3, "mysql"),
            ]
        )

        assert "test_model" in result
        assert "second_model" in result
        assert "third_model" in result

    def test_sql_dialect_appears_in_summary(self, simple_sdm: SemanticDataModel):
        """SQL dialect should be included in the summary."""
        result = summarize_data_models([(simple_sdm, "postgres")])

        assert "postgres" in result.lower()

    def test_snowflake_guidance(self, snowflake_sdm_with_variant: SemanticDataModel):
        """Snowflake guidance"""
        result = _get_sql_generation_instructions([(snowflake_sdm_with_variant, "snowflake")])

        # Unique to Snowflake: bracket notation requirement
        assert "bracket notation" in result.lower() or "col['field']" in result

        # Unique warning for Snowflake
        assert "colon notation" in result.lower() or "col:field" in result

    def test_postgres_guidance(self, postgres_sdm_with_json: SemanticDataModel):
        """PostgreSQL guidance"""
        result = _get_sql_generation_instructions([(postgres_sdm_with_json, "postgres")])

        # Unique to PostgreSQL: LATERAL for JSON aggregation
        assert "LATERAL" in result or "lateral" in result.lower()

        # Should mention both function types
        assert "json_array_elements" in result.lower()
        assert "jsonb_array_elements" in result.lower()

    def test_mysql_guidance(self, mysql_sdm_with_json: SemanticDataModel):
        """MySQL guidance"""
        result = _get_sql_generation_instructions([(mysql_sdm_with_json, "mysql")])

        # Unique to MySQL: mandatory $.path syntax
        assert "$.path" in result or "'$.field'" in result

        # Unique to MySQL: JSON_TABLE for array processing
        assert "JSON_TABLE" in result


class TestGetSemanticDataModelsWithEngines:
    """Tests for get_semantic_data_models_with_engines function."""

    def test_returns_model_with_base_table_intact(self):
        """Verify that get_semantic_data_models_with_engines returns models with base_table preserved.

        This test ensures the function does not strip required fields like base_table,
        which would cause downstream validation errors.
        """
        # Create a SemanticDataModelAndReferences with a valid base_table
        sdm_and_refs = SemanticDataModelAndReferences(
            semantic_data_model_info={
                "semantic_data_model": SemanticDataModel.model_validate(
                    {
                        "name": "Video Rental Analytics",
                        "description": "Test semantic data model",
                        "tables": [
                            {
                                "name": "actor",
                                "base_table": {
                                    "table": "actor",
                                    "data_connection_id": "test-connection-id",
                                },
                                "dimensions": [
                                    {
                                        "name": "actor_id",
                                        "expr": "actor_id",
                                        "data_type": "int32",
                                    },
                                    {
                                        "name": "first_name",
                                        "expr": "first_name",
                                        "data_type": "string(45)",
                                    },
                                ],
                            }
                        ],
                    }
                ),
                "semantic_data_model_id": "test-sdm-id",
                "agent_ids": set("test-agent-id"),
                "thread_ids": set("test-thread-id"),
                "updated_at": "now",
            },
            references=References(
                data_connection_ids={"test-connection-id"},
                data_frame_names=set(),
                file_references=set(),
                data_connection_id_to_logical_table_names={"test-connection-id": {"actor"}},
                file_reference_to_logical_table_names={},
                logical_table_name_to_connection_info={},
                errors=[],
                _structured_errors=[],
                tables_with_unresolved_file_references=set(),
                semantic_data_model_with_errors=None,
            ),
        )

        data_connection_id_to_engine = {"test-connection-id": "postgresql"}

        # This should not raise a ValidationError
        result = get_semantic_data_models_with_engines(
            [sdm_and_refs],
            data_connection_id_to_engine,
        )

        # Verify we got one result
        assert len(result) == 1

        model, engine = result[0]

        # Verify the engine was inferred correctly
        assert engine == "postgresql"

        # Verify the model has the expected structure
        assert model.name == "Video Rental Analytics"
        assert len(model.tables) == 1

        # Verify base_table is still present (this is the key assertion)
        table = model.tables[0]
        assert table.get("name") == "actor"
        assert table.get("base_table") is not None
        assert table["base_table"].get("table") == "actor"
        assert table["base_table"].get("data_connection_id") == "test-connection-id"
