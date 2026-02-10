import pytest

from agent_platform.core.semantic_data_model.types import SemanticDataModel
from agent_platform.core.semantic_data_model.validation import References
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
                    "base_table": {"table": "users_table"},
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
                    "base_table": {"table": "products_tbl"},
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
                    "base_table": {"table": "documents_table"},
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
                    "base_table": {"table": "events_tbl"},
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

    def test_column_expr_appears_as_primary(self):
        """Column expressions should be primary identifiers, not names."""
        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [
                    {
                        "name": "users",
                        "base_table": {"table": "user_table", "data_connection_id": "conn-123"},
                        "dimensions": [
                            {"name": "full_name", "expr": "first_name || ' ' || last_name", "data_type": "VARCHAR"}
                        ],
                    }
                ],
            }
        )

        result = summarize_data_models([(sdm, "postgres")])

        # Expression should appear as column identifier (YAML format)
        assert "first_name || ' ' || last_name" in result

    def test_important_instruction_appears_in_summary(self, simple_sdm: SemanticDataModel):
        """Summary should include column metadata with lowercase labels."""
        result = summarize_data_models([(simple_sdm, "duckdb")])

        # Check that data_type appears with lowercase formatting
        assert "data_type: INTEGER" in result or "data_type: VARCHAR" in result

    def test_multiple_column_types_formatted_correctly(self):
        """Different column types should all use physical-first formatting."""
        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [
                    {
                        "name": "sales",
                        "base_table": {"table": "sales_fact", "data_connection_id": "conn-123"},
                        "dimensions": [{"name": "product_name", "expr": "product", "data_type": "VARCHAR"}],
                        "facts": [{"name": "revenue", "expr": "price * quantity", "data_type": "DECIMAL"}],
                        "metrics": [{"name": "total_revenue", "expr": "SUM(price * quantity)", "data_type": "DECIMAL"}],
                    }
                ],
            }
        )

        result = summarize_data_models([(sdm, "duckdb")])

        # All should show expressions as primary (YAML format with "- name:")
        assert "- name: product" in result
        assert "- name: price * quantity" in result
        assert "- name: SUM(price * quantity)" in result

    def test_file_reference_table_uses_logical_name_as_physical(self):
        """File-based tables should use logical name as physical name."""
        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [
                    {
                        "name": "my_data",
                        "base_table": {"file_reference": {"thread_id": "thread-123", "file_ref": "file-456"}},
                        "dimensions": [{"name": "id", "expr": "id", "data_type": "INTEGER"}],
                    }
                ],
            }
        )

        result = summarize_data_models([(sdm, "duckdb")])

        # For file references, logical name IS the physical name
        assert "Table: my_data" in result

    def test_file_reference_columns_use_name_not_expr(self):
        """File reference tables should show column name (not expr) with no Display Name."""
        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [
                    {
                        "name": "uploaded_data",
                        "base_table": {"file_reference": {"thread_id": "thread-123", "file_ref": "file-456"}},
                        "dimensions": [
                            {"name": "customer_id", "expr": "customer_id", "data_type": "INTEGER"},
                            {"name": "full_name", "expr": "first_name || ' ' || last_name", "data_type": "VARCHAR"},
                        ],
                    }
                ],
            }
        )

        result = summarize_data_models([(sdm, "duckdb")])

        # For file reference tables, use column name (YAML format)
        assert "- name: customer_id" in result
        assert "- name: full_name" in result

        # Data type should be present
        assert "data_type: INTEGER" in result
        assert "data_type: VARCHAR" in result

        # Should NOT show expr for file reference tables
        assert "expr:" not in result

    def test_data_connection_columns_use_expr_with_display_name(self):
        """Data connection tables should show column expr with data type on separate line."""
        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [
                    {
                        "name": "users",
                        "base_table": {"table": "user_table", "data_connection_id": "conn-123"},
                        "dimensions": [
                            {"name": "user_id", "expr": "user_id", "data_type": "INTEGER"},
                            {"name": "full_name", "expr": "first_name || ' ' || last_name", "data_type": "VARCHAR"},
                        ],
                    }
                ],
            }
        )

        result = summarize_data_models([(sdm, "postgres")])

        # For data connection tables, use expr (YAML format)
        assert "- name: user_id" in result
        assert "- name: first_name || ' ' || last_name" in result

        # Data type should be present
        assert "data_type: INTEGER" in result
        assert "data_type: VARCHAR" in result

    def test_data_connection_table_uses_base_table_as_physical(self):
        """Data connection tables should use base_table.table as physical name."""
        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [
                    {
                        "name": "customers",
                        "base_table": {"table": "customer_master", "data_connection_id": "conn-123"},
                        "dimensions": [{"name": "id", "expr": "customer_id", "data_type": "INTEGER"}],
                    }
                ],
            }
        )

        result = summarize_data_models([(sdm, "postgres")])

        # For data connections, base_table.table is physical
        assert "Table: customer_master" in result


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
