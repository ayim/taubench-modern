from typing import Any, cast

import pytest

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.server.kernel.semantic_data_model import (
    summarize_data_models,
)
from agent_platform.server.kernel.sql import _get_sql_generation_instructions

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def simple_sdm() -> SemanticDataModel:
    """Simple semantic data model without special columns."""
    return cast(
        SemanticDataModel,
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
    )


@pytest.fixture
def snowflake_sdm_with_variant() -> SemanticDataModel:
    """Snowflake SDM with VARIANT columns."""
    return cast(
        SemanticDataModel,
        {
            "name": "snowflake_products",
            "tables": [
                {
                    "name": "products",
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
    return cast(
        SemanticDataModel,
        {
            "name": "postgres_documents",
            "tables": [
                {
                    "name": "documents",
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
    return cast(
        SemanticDataModel,
        {
            "name": "mysql_events",
            "tables": [
                {
                    "name": "events",
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
        sdm2 = {**simple_sdm, "name": "second_model"}
        sdm3 = {**simple_sdm, "name": "third_model"}

        result = summarize_data_models(
            [
                (cast(SemanticDataModel, simple_sdm), "duckdb"),
                (cast(SemanticDataModel, sdm2), "postgres"),
                (cast(SemanticDataModel, sdm3), "mysql"),
            ]
        )

        assert "test_model" in result
        assert "second_model" in result
        assert "third_model" in result

    def test_sql_dialect_appears_in_summary(self, simple_sdm: dict[str, Any]):
        """SQL dialect should be included in the summary."""
        result = summarize_data_models([(cast(SemanticDataModel, simple_sdm), "postgres")])

        assert "postgres" in result.lower()

    def test_snowflake_guidance(self, snowflake_sdm_with_variant: dict[str, Any]):
        """Snowflake guidance"""
        result = _get_sql_generation_instructions([(cast(SemanticDataModel, snowflake_sdm_with_variant), "snowflake")])

        # Unique to Snowflake: bracket notation requirement
        assert "bracket notation" in result.lower() or "col['field']" in result

        # Unique warning for Snowflake
        assert "colon notation" in result.lower() or "col:field" in result

    def test_postgres_guidance(self, postgres_sdm_with_json: dict[str, Any]):
        """PostgreSQL guidance"""
        result = _get_sql_generation_instructions([(cast(SemanticDataModel, postgres_sdm_with_json), "postgres")])

        # Unique to PostgreSQL: LATERAL for JSON aggregation
        assert "LATERAL" in result or "lateral" in result.lower()

        # Should mention both function types
        assert "json_array_elements" in result.lower()
        assert "jsonb_array_elements" in result.lower()

    def test_mysql_guidance(self, mysql_sdm_with_json: dict[str, Any]):
        """MySQL guidance"""
        result = _get_sql_generation_instructions([(cast(SemanticDataModel, mysql_sdm_with_json), "mysql")])

        # Unique to MySQL: mandatory $.path syntax
        assert "$.path" in result or "'$.field'" in result

        # Unique to MySQL: JSON_TABLE for array processing
        assert "JSON_TABLE" in result
