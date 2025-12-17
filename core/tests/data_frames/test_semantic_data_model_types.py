"""Unit tests for SemanticDataModel type functions.

This module tests the public API functions (model_dump, model_validate) and
private helper functions for SemanticDataModel normalization and serialization.
"""

import json
from datetime import UTC, date, datetime
from typing import cast

import pytest

from agent_platform.core.data_frames.semantic_data_model_types import (
    SemanticDataModel,
    _normalize_for_comparison,
    _strip_environment_specific_fields,
    model_dump_sdm,
    model_validate_sdm,
    to_json_string_for_comparison,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_sdm() -> SemanticDataModel:
    """Sample semantic data model for testing."""
    return cast(
        SemanticDataModel,
        {
            "name": "test_model",
            "description": "A test semantic model",
            "tables": [
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
        },
    )


@pytest.fixture
def sdm_with_datetimes() -> SemanticDataModel:
    """Semantic data model with datetime objects (simulating YAML parsing)."""
    return cast(
        SemanticDataModel,
        {
            "name": "model_with_datetimes",
            "description": "Model with datetime objects",
            "tables": [
                {
                    "name": "events",
                    "base_table": {
                        "database": "test_db",
                        "schema": "public",
                        "table": "events",
                    },
                    "time_dimensions": [
                        {
                            "name": "event_date",
                            "expr": "event_date",
                            "data_type": "string",
                            "sample_values": [
                                datetime(2024, 10, 16, 0, 0, 0, tzinfo=UTC),
                                date(2024, 1, 15),
                            ],
                        },
                    ],
                }
            ],
        },
    )


@pytest.fixture
def sdm_with_environment_fields() -> SemanticDataModel:
    """Semantic data model with environment-specific fields."""
    return cast(
        SemanticDataModel,
        {
            "name": "model_with_env_fields",
            "description": "Model with environment-specific fields",
            "tables": [
                {
                    "name": "users",
                    "base_table": {
                        "data_connection_id": "conn-123",
                        "data_connection_name": "test_connection",
                        "database": "test_db",
                        "schema": "public",
                        "table": "users",
                    },
                },
                {
                    "name": "file_data",
                    "base_table": {
                        "table": "data_frame_file",
                        "file_reference": {
                            "thread_id": "thread-456",
                            "file_ref": "file.csv",
                            "sheet_name": "",
                        },
                    },
                },
            ],
        },
    )


@pytest.fixture
def sdm_with_metadata() -> SemanticDataModel:
    """Semantic data model with metadata field."""
    return cast(
        SemanticDataModel,
        {
            "name": "model_with_metadata",
            "description": "Model with metadata",
            "tables": [],
            "metadata": {
                "input_data_connection_snapshots": [
                    {
                        "source_type": "data_connection",
                        "data_connection_id": "conn-123",
                    }
                ],
            },
        },
    )


# ============================================================================
# Tests for model_dump()
# ============================================================================


class TestModelDump:
    """Tests for model_dump() function."""

    def test_model_dump_basic(self, sample_sdm: SemanticDataModel):
        """Test basic model_dump functionality."""
        result = model_dump_sdm(sample_sdm)

        assert isinstance(result, dict)
        assert result["name"] == "test_model"
        assert result["description"] == "A test semantic model"
        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "users"

    def test_model_dump_with_datetimes(self, sdm_with_datetimes: SemanticDataModel):
        """Test model_dump converts datetime objects to ISO strings."""
        result = model_dump_sdm(sdm_with_datetimes)

        # Verify datetime objects were converted to strings
        sample_values = result["tables"][0]["time_dimensions"][0]["sample_values"]
        assert isinstance(sample_values[0], str)
        assert "2024-10-16" in sample_values[0]
        assert isinstance(sample_values[1], str)
        assert "2024-01-15" in sample_values[1]

        # Verify the result is JSON serializable
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["tables"][0]["time_dimensions"][0]["sample_values"][0] == sample_values[0]

    def test_model_dump_exclude_none(self):
        """Test model_dump with exclude_none=True."""
        sdm = cast(
            SemanticDataModel,
            {
                "name": "test",
                "description": None,
                "tables": [],
            },
        )

        # With exclude_none=False (default)
        result_with_none = model_dump_sdm(sdm, exclude_none=False)
        assert "description" in result_with_none
        assert result_with_none["description"] is None

        # With exclude_none=True
        result_without_none = model_dump_sdm(sdm, exclude_none=True)
        assert "description" not in result_without_none

    def test_model_dump_nested_datetimes(self):
        """Test model_dump handles nested datetime objects."""
        sdm = cast(
            SemanticDataModel,
            {
                "name": "test",
                "tables": [
                    {
                        "name": "events",
                        "base_table": {"table": "events"},
                        "dimensions": [
                            {
                                "name": "created_at",
                                "expr": "created_at",
                                "data_type": "string",
                                "sample_values": [
                                    datetime(2024, 1, 1, 12, 30, 45, tzinfo=UTC),
                                ],
                            }
                        ],
                    }
                ],
            },
        )

        result = model_dump_sdm(sdm)
        sample_values = result["tables"][0]["dimensions"][0]["sample_values"]
        assert isinstance(sample_values[0], str)
        assert "2024-01-01" in sample_values[0]
        assert "12:30:45" in sample_values[0]

    def test_model_dump_preserves_structure(self, sample_sdm: SemanticDataModel):
        """Test model_dump preserves the structure of the SDM."""
        result = model_dump_sdm(sample_sdm)

        # Verify structure is preserved
        assert "name" in result
        assert "description" in result
        assert "tables" in result
        assert isinstance(result["tables"], list)
        assert len(result["tables"]) == 1
        assert "name" in result["tables"][0]
        assert "base_table" in result["tables"][0]
        assert "dimensions" in result["tables"][0]

    def test_model_dump_does_not_mutate_original(self, sample_sdm: SemanticDataModel):
        """Test model_dump does not mutate the original SDM."""
        original_name = sample_sdm["name"]
        original_tables = len(sample_sdm.get("tables", []))

        result = model_dump_sdm(sample_sdm)

        # Modify result
        result["name"] = "modified"
        result["tables"].append({"name": "new_table"})

        # Verify original is unchanged
        assert sample_sdm["name"] == original_name
        assert len(sample_sdm.get("tables", [])) == original_tables


# ============================================================================
# Tests for model_validate()
# ============================================================================


class TestModelValidate:
    """Tests for model_validate() function."""

    def test_model_validate_basic(self):
        """Test basic model_validate functionality."""
        data = {
            "name": "test_model",
            "description": "A test model",
            "tables": [
                {
                    "name": "users",
                    "base_table": {"table": "users"},
                    "dimensions": [{"name": "id", "expr": "id", "data_type": "INTEGER"}],
                }
            ],
        }

        result = model_validate_sdm(data)

        assert isinstance(result, dict)
        assert result["name"] == "test_model"
        assert result.get("description") == "A test model"
        assert len(result.get("tables", [])) == 1

    def test_model_validate_with_optional_fields(self):
        """Test model_validate with optional fields."""
        data = {
            "name": "test",
            "tables": [],
            "verified_queries": [
                {"name": "query1", "sql": "SELECT * FROM users"},
            ],
        }

        result = model_validate_sdm(data)

        assert result["name"] == "test"
        assert "verified_queries" in result
        verified_queries = result.get("verified_queries")
        assert verified_queries is not None
        assert len(verified_queries) == 1

    def test_model_validate_returns_typed_dict(self):
        """Test that model_validate returns a dict that can be used as SemanticDataModel."""
        data = {
            "name": "test",
            "tables": [],
        }

        result = model_validate_sdm(data)

        # Should be able to access as dict (TypedDict behavior)
        assert result["name"] == "test"
        assert isinstance(result, dict)


# ============================================================================
# Tests for _strip_environment_specific_fields()
# ============================================================================


class TestStripEnvironmentSpecificFields:
    """Tests for _strip_environment_specific_fields() function."""

    def test_strip_data_connection_id(self, sdm_with_environment_fields: SemanticDataModel):
        """Test that data_connection_id is stripped."""
        result = _strip_environment_specific_fields(sdm_with_environment_fields)

        tables = result.get("tables", [])
        assert len(tables) > 0
        # data_connection_id should be removed
        assert "data_connection_id" not in tables[0]["base_table"]
        # data_connection_name should be removed
        assert "data_connection_name" not in tables[0]["base_table"]
        # database and schema should be preserved
        assert "database" in tables[0]["base_table"]
        assert "schema" in tables[0]["base_table"]

    def test_strip_file_reference(self, sdm_with_environment_fields: SemanticDataModel):
        """Test that file references are stripped."""
        result = _strip_environment_specific_fields(sdm_with_environment_fields)

        # File reference table should have file_reference removed from base_table
        tables = result.get("tables", [])
        file_table = next(t for t in tables if t["name"] == "file_data")
        assert "file_reference" not in file_table["base_table"]

    def test_preserves_database_schema(self, sdm_with_environment_fields: SemanticDataModel):
        """Test that database and schema are preserved (they're part of SDM definition)."""
        result = _strip_environment_specific_fields(sdm_with_environment_fields)

        # database and schema should be preserved
        tables = result.get("tables", [])
        assert len(tables) > 0
        base_table = tables[0]["base_table"]
        assert base_table.get("database") == "test_db"
        assert base_table.get("schema") == "public"

    def test_does_not_mutate_original(self, sdm_with_environment_fields: SemanticDataModel):
        """Test that original SDM is not mutated."""
        original_tables = sdm_with_environment_fields.get("tables", [])
        assert len(original_tables) > 0
        original_conn_id = original_tables[0]["base_table"].get("data_connection_id")

        result = _strip_environment_specific_fields(sdm_with_environment_fields)

        # Original should still have the field
        original_tables = sdm_with_environment_fields.get("tables", [])
        assert len(original_tables) > 0
        assert original_tables[0]["base_table"].get("data_connection_id") == original_conn_id
        # Result should not have it
        result_tables = result.get("tables", [])
        assert len(result_tables) > 0
        assert "data_connection_id" not in result_tables[0]["base_table"]

    def test_handles_missing_fields(self, sample_sdm: SemanticDataModel):
        """Test that function handles SDMs without environment-specific fields."""
        result = _strip_environment_specific_fields(sample_sdm)

        # Should work without errors
        assert result["name"] == sample_sdm["name"]
        assert len(result.get("tables", [])) == len(sample_sdm.get("tables", []))


# ============================================================================
# Tests for _normalize_for_comparison()
# ============================================================================


class TestNormalizeForComparison:
    """Tests for _normalize_for_comparison() function."""

    def test_normalize_strips_environment_fields(self, sdm_with_environment_fields: SemanticDataModel):
        """Test that normalize strips environment-specific fields."""
        result = _normalize_for_comparison(sdm_with_environment_fields)

        # Environment-specific fields should be removed
        tables = result.get("tables", [])
        assert len(tables) > 0
        assert "data_connection_id" not in tables[0]["base_table"]
        assert "data_connection_name" not in tables[0]["base_table"]

    def test_normalize_preserves_metadata_when_requested(self, sdm_with_metadata: SemanticDataModel):
        """Test that normalize preserves metadata by default."""
        result = _normalize_for_comparison(sdm_with_metadata, exclude_metadata=False)

        # Metadata should be preserved
        assert "metadata" in result
        assert result["metadata"] is not None

    def test_normalize_excludes_metadata_by_default(self, sdm_with_metadata: SemanticDataModel):
        """Test that normalize excludes metadata by default."""
        result = _normalize_for_comparison(sdm_with_metadata)

        # Metadata should be removed
        assert "metadata" not in result

    def test_normalize_excludes_metadata_when_requested(self, sdm_with_metadata: SemanticDataModel):
        """Test that normalize can exclude metadata."""
        result = _normalize_for_comparison(sdm_with_metadata, exclude_metadata=True)

        # Metadata should be removed
        assert "metadata" not in result

    def test_normalize_handles_empty_tables(self):
        """Test normalize with SDM that has empty tables list."""
        sdm = cast(SemanticDataModel, {"name": "test", "tables": []})

        result = _normalize_for_comparison(sdm)

        assert result["name"] == "test"
        assert result.get("tables", []) == []


# ============================================================================
# Tests for _to_json_string_for_comparison()
# ============================================================================


class TestToJsonStringForComparison:
    """Tests for _to_json_string_for_comparison() function."""

    def test_to_json_string_basic(self, sample_sdm: SemanticDataModel):
        """Test basic JSON string conversion."""
        result = to_json_string_for_comparison(sample_sdm)

        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["name"] == "test_model"

    def test_to_json_string_is_sorted(self):
        """Test that JSON string is sorted for consistent comparison."""
        sdm1 = cast(SemanticDataModel, {"name": "test", "description": "desc", "tables": []})
        sdm2 = cast(SemanticDataModel, {"description": "desc", "name": "test", "tables": []})

        # Even though fields are in different order, JSON strings should match
        result1 = to_json_string_for_comparison(sdm1)
        result2 = to_json_string_for_comparison(sdm2)

        assert result1 == result2

    def test_to_json_string_strips_environment_fields(self, sdm_with_environment_fields: SemanticDataModel):
        """Test that JSON string excludes environment-specific fields."""
        result = to_json_string_for_comparison(sdm_with_environment_fields)

        json.loads(result)
        # Should not contain environment-specific fields
        assert "data_connection_id" not in str(result)

    def test_to_json_string_excludes_metadata_when_requested(self, sdm_with_metadata: SemanticDataModel):
        """Test that JSON string can exclude metadata."""
        result_with_metadata = to_json_string_for_comparison(sdm_with_metadata, exclude_metadata=False)
        result_without_metadata = to_json_string_for_comparison(sdm_with_metadata, exclude_metadata=True)

        parsed_with = json.loads(result_with_metadata)
        parsed_without = json.loads(result_without_metadata)

        assert "metadata" in parsed_with
        assert "metadata" not in parsed_without
        assert parsed_with["name"] == parsed_without["name"]  # Other fields should match

    def test_to_json_string_handles_datetimes(self, sdm_with_datetimes: SemanticDataModel):
        """Test that JSON string handles datetime objects correctly."""
        result = to_json_string_for_comparison(sdm_with_datetimes)

        # Should be valid JSON (datetimes converted to strings)
        parsed = json.loads(result)
        sample_values = parsed["tables"][0]["time_dimensions"][0]["sample_values"]
        assert isinstance(sample_values[0], str)
        assert "2024-10-16" in sample_values[0]

    def test_to_json_string_consistent_for_same_sdm(self, sample_sdm: SemanticDataModel):
        """Test that same SDM produces same JSON string."""
        result1 = to_json_string_for_comparison(sample_sdm)
        result2 = to_json_string_for_comparison(sample_sdm)

        assert result1 == result2

    def test_to_json_string_different_for_different_sdms(self):
        """Test that different SDMs produce different JSON strings."""
        sdm1 = cast(SemanticDataModel, {"name": "model1", "tables": []})
        sdm2 = cast(SemanticDataModel, {"name": "model2", "tables": []})

        result1 = to_json_string_for_comparison(sdm1)
        result2 = to_json_string_for_comparison(sdm2)

        assert result1 != result2


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for multiple functions working together."""

    def test_model_dump_and_validate_roundtrip(self, sample_sdm: SemanticDataModel):
        """Test that model_dump and model_validate work together."""
        dumped = model_dump_sdm(sample_sdm)
        validated = model_validate_sdm(dumped)

        assert validated["name"] == sample_sdm["name"]
        assert validated.get("description") == sample_sdm.get("description")
        assert len(validated.get("tables", [])) == len(sample_sdm.get("tables", []))

    def test_normalize_and_compare_workflow(self):
        """Test the workflow of normalizing and comparing SDMs."""
        sdm1 = cast(
            SemanticDataModel,
            {
                "name": "test",
                "tables": [
                    {
                        "name": "users",
                        "base_table": {
                            "data_connection_id": "conn-1",  # Different IDs
                            "database": "test_db",
                            "schema": "public",
                            "table": "users",
                        },
                    }
                ],
            },
        )

        sdm2 = cast(
            SemanticDataModel,
            {
                "name": "test",
                "tables": [
                    {
                        "name": "users",
                        "base_table": {
                            "data_connection_id": "conn-2",  # Different IDs
                            "database": "test_db",
                            "schema": "public",
                            "table": "users",
                        },
                    }
                ],
            },
        )

        # After normalization, they should be equal (same semantic structure)
        json1 = to_json_string_for_comparison(sdm1)
        json2 = to_json_string_for_comparison(sdm2)

        assert json1 == json2, "SDMs with same semantic structure should match after normalization"
