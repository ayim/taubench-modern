"""Unit tests for SemanticDataModel Pydantic model.

This module tests the SemanticDataModel Pydantic BaseModel functionality
including model_dump, model_validate, and to_comparable_json methods.
"""

import json
from datetime import UTC, date, datetime

import pytest

from agent_platform.core.semantic_data_model.types import (
    SemanticDataModel,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_sdm() -> SemanticDataModel:
    """Sample semantic data model for testing."""
    return SemanticDataModel.model_validate(
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
    return SemanticDataModel.model_validate(
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
    return SemanticDataModel.model_validate(
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
    return SemanticDataModel.model_validate(
        {
            "name": "model_with_metadata",
            "description": "Model with metadata",
            "tables": [],
            "metadata": {
                "input_data_connection_snapshots": [
                    {
                        "kind": "data_connection",
                        "inspection_result": {
                            "tables": [],
                            "inspected_at": "2024-01-01T00:00:00Z",
                        },
                        "inspection_request_info": {
                            "data_connection_id": "conn-123",
                            "data_connection_name": "test-connection",
                            "data_connection_inspect_request": None,
                        },
                        "inspected_at": "2024-01-01T00:00:00Z",
                    }
                ],
            },
        },
    )


# ============================================================================
# Tests for model_dump()
# ============================================================================


class TestModelDump:
    """Tests for SemanticDataModel.model_dump() method."""

    def test_model_dump_basic(self, sample_sdm: SemanticDataModel):
        """Test basic model_dump functionality."""
        result = sample_sdm.model_dump()

        assert isinstance(result, dict)
        assert result["name"] == "test_model"
        assert result["description"] == "A test semantic model"
        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "users"

    def test_model_dump_with_datetimes(self, sdm_with_datetimes: SemanticDataModel):
        """Test model_dump(mode='json') converts datetime objects to ISO strings."""
        # Use mode="json" to serialize datetime objects to ISO strings
        result = sdm_with_datetimes.model_dump(mode="json")

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
        """Test model_dump with exclude_none (default is True for SemanticDataModel)."""
        sdm = SemanticDataModel.model_validate(
            {
                "name": "test",
                "description": None,
                "tables": [],
            },
        )

        # With exclude_none=True (default for SemanticDataModel)
        result_without_none = sdm.model_dump()
        assert "description" not in result_without_none

        # With exclude_none=False (explicit)
        result_with_none = sdm.model_dump(exclude_none=False)
        assert "description" in result_with_none
        assert result_with_none["description"] is None

    def test_model_dump_nested_datetimes(self):
        """Test model_dump handles nested datetime objects."""
        sdm = SemanticDataModel.model_validate(
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

        # Use mode="json" to serialize datetime objects to ISO strings
        result = sdm.model_dump(mode="json")
        sample_values = result["tables"][0]["dimensions"][0]["sample_values"]
        assert isinstance(sample_values[0], str)
        assert "2024-01-01" in sample_values[0]
        assert "12:30:45" in sample_values[0]

    def test_model_dump_preserves_structure(self, sample_sdm: SemanticDataModel):
        """Test model_dump preserves the structure of the SDM."""
        result = sample_sdm.model_dump()

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
        original_name = sample_sdm.name
        original_tables = len(sample_sdm.tables or [])

        result = sample_sdm.model_dump()

        # Modify result
        result["name"] = "modified"
        result["tables"].append({"name": "new_table"})

        # Verify original is unchanged
        assert sample_sdm.name == original_name
        assert len(sample_sdm.tables or []) == original_tables


# ============================================================================
# Tests for model_validate()
# ============================================================================


class TestModelValidate:
    """Tests for SemanticDataModel.model_validate() class method."""

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

        result = SemanticDataModel.model_validate(data)

        assert isinstance(result, SemanticDataModel)
        assert result.name == "test_model"
        assert result.description == "A test model"
        assert result.tables is not None
        assert len(result.tables) == 1

    def test_model_validate_with_optional_fields(self):
        """Test model_validate with optional fields."""
        data = {
            "name": "test",
            "tables": [],
            "verified_queries": [
                {
                    "name": "query1",
                    "nlq": "Get all users",
                    "sql": "SELECT * FROM users",
                    "verified_at": "2024-01-01T00:00:00Z",
                    "verified_by": "user1",
                },
            ],
        }

        result = SemanticDataModel.model_validate(data)

        assert result.name == "test"
        assert result.verified_queries is not None
        assert len(result.verified_queries) == 1

    def test_model_validate_returns_pydantic_model(self):
        """Test that model_validate returns a SemanticDataModel instance."""
        data = {
            "name": "test",
            "tables": [],
        }

        result = SemanticDataModel.model_validate(data)

        # Should be a Pydantic model with attribute access
        assert result.name == "test"
        assert isinstance(result, SemanticDataModel)


# ============================================================================
# Tests for to_comparable_json()
# ============================================================================


class TestToComparableJson:
    """Tests for SemanticDataModel.to_comparable_json() method."""

    def test_to_comparable_json_basic(self, sample_sdm: SemanticDataModel):
        """Test basic JSON string conversion."""
        result = sample_sdm.to_comparable_json()

        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["name"] == "test_model"

    def test_to_comparable_json_is_sorted(self):
        """Test that JSON string is sorted for consistent comparison."""
        sdm1 = SemanticDataModel.model_validate({"name": "test", "description": "desc", "tables": []})
        sdm2 = SemanticDataModel.model_validate({"description": "desc", "name": "test", "tables": []})

        # Even though fields were defined in different order, JSON strings should match
        result1 = sdm1.to_comparable_json()
        result2 = sdm2.to_comparable_json()

        assert result1 == result2

    def test_to_comparable_json_strips_environment_fields(self, sdm_with_environment_fields: SemanticDataModel):
        """Test that JSON string excludes environment-specific fields."""
        result = sdm_with_environment_fields.to_comparable_json()

        json.loads(result)
        # Should not contain environment-specific fields
        assert "data_connection_id" not in str(result)
        assert "data_connection_name" not in str(result)
        assert "file_reference" not in str(result)

    def test_to_comparable_json_excludes_metadata_by_default(self, sdm_with_metadata: SemanticDataModel):
        """Test that JSON string excludes metadata by default."""
        result = sdm_with_metadata.to_comparable_json()

        parsed = json.loads(result)
        assert "metadata" not in parsed

    def test_to_comparable_json_includes_metadata_when_requested(self, sdm_with_metadata: SemanticDataModel):
        """Test that JSON string can include metadata."""
        result = sdm_with_metadata.to_comparable_json(exclude_metadata=False)

        parsed = json.loads(result)
        assert "metadata" in parsed

    def test_to_comparable_json_handles_datetimes(self, sdm_with_datetimes: SemanticDataModel):
        """Test that JSON string handles datetime objects correctly."""
        result = sdm_with_datetimes.to_comparable_json()

        # Should be valid JSON (datetimes converted to strings)
        parsed = json.loads(result)
        sample_values = parsed["tables"][0]["time_dimensions"][0]["sample_values"]
        assert isinstance(sample_values[0], str)
        assert "2024-10-16" in sample_values[0]

    def test_to_comparable_json_consistent_for_same_sdm(self, sample_sdm: SemanticDataModel):
        """Test that same SDM produces same JSON string."""
        result1 = sample_sdm.to_comparable_json()
        result2 = sample_sdm.to_comparable_json()

        assert result1 == result2

    def test_to_comparable_json_different_for_different_sdms(self):
        """Test that different SDMs produce different JSON strings."""
        sdm1 = SemanticDataModel.model_validate({"name": "model1", "tables": []})
        sdm2 = SemanticDataModel.model_validate({"name": "model2", "tables": []})

        result1 = sdm1.to_comparable_json()
        result2 = sdm2.to_comparable_json()

        assert result1 != result2


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for SemanticDataModel Pydantic model."""

    def test_model_dump_and_validate_roundtrip(self, sample_sdm: SemanticDataModel):
        """Test that model_dump and model_validate work together."""
        dumped = sample_sdm.model_dump()
        validated = SemanticDataModel.model_validate(dumped)

        assert validated.name == sample_sdm.name
        assert validated.description == sample_sdm.description
        assert len(validated.tables or []) == len(sample_sdm.tables or [])

    def test_compare_workflow_with_to_comparable_json(self):
        """Test the workflow of normalizing and comparing SDMs."""
        sdm1 = SemanticDataModel.model_validate(
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

        sdm2 = SemanticDataModel.model_validate(
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
        json1 = sdm1.to_comparable_json()
        json2 = sdm2.to_comparable_json()

        assert json1 == json2, "SDMs with same semantic structure should match after normalization"
