"""Unit tests for SQL parameter utilities."""

import pytest

from agent_platform.core.semantic_data_model.types import QueryParameter
from agent_platform.core.semantic_data_model.utils import (
    extract_parameters_from_sql,
)
from agent_platform.server.data_frames.sql_parameter_utils import (
    substitute_sql_parameters_safe,
)


class TestExtractParametersFromSQLValidation:
    """Generic validation and error handling tests for extract_parameters_from_sql.

    These tests verify error conditions and edge cases that are dialect-agnostic.
    Dialect-specific SQL pattern tests should be in test_sql_parameter_utils_<dialect>.py files.
    """

    def test_invalid_sql_raises_error(self):
        """Test that invalid SQL raises ValueError."""
        sql = "SELECT * FROM WHERE invalid syntax"
        with pytest.raises(ValueError, match="Failed to parse SQL query"):
            extract_parameters_from_sql(sql, dialect="postgres")

    def test_empty_sql_raises_error(self):
        """Test that empty SQL raises ValueError."""
        sql = ""
        with pytest.raises(ValueError, match="Failed to parse SQL query"):
            extract_parameters_from_sql(sql, dialect="postgres")

    def test_parameters_in_deep_nested_subqueries(self):
        """Test parameter extraction in deeply nested subqueries (10 levels).

        This test verifies that find_all() can handle deep AST structures
        without recursion issues. The query has 11 parameters total:
        1 user_id + 10 params (param0 through param9).
        """
        # Create a query with 10 nested subqueries
        nested_levels = 10
        sql = "SELECT * FROM users WHERE id = :user_id"
        for i in range(nested_levels):
            sql = f"SELECT * FROM ({sql}) AS subq{i} WHERE col{i} = :param{i}"

        result = extract_parameters_from_sql(sql, dialect="postgres")

        # Should find all 11 parameters (user_id + param0 through param9)
        expected_params = ["user_id"] + [f"param{i}" for i in range(nested_levels)]
        assert len(result) == len(expected_params)
        assert set(result) == set(expected_params)


class TestSubstituteSQLParametersSafeErrorHandling:
    """Generic error handling tests for substitute_sql_parameters_safe.

    These tests are dialect-agnostic and test error conditions that should
    work the same way regardless of SQL dialect.
    """

    def test_missing_required_parameter_raises_error(self):
        """Test that missing required parameter raises ValueError."""
        sql = "SELECT * FROM users WHERE id = :user_id AND country = :country"
        param_defs = [
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1),
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
        ]
        with pytest.raises(ValueError, match=r"Required parameter\(s\) not provided: country"):
            substitute_sql_parameters_safe(sql, {"user_id": 123}, param_defs, "postgres")

    def test_extra_parameters_ignored(self):
        """Test that extra parameters not in param_definitions are silently ignored."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        # Pass extra parameter 'country' that's not in SQL or param_defs
        result = substitute_sql_parameters_safe(sql, {"user_id": 123, "country": "Germany"}, param_defs, "postgres")
        assert result == "SELECT * FROM users WHERE id = 123"

    def test_parameter_in_sql_not_in_definitions_raises_error(self):
        """Test that parameter found in SQL but not in definitions raises ValueError."""
        sql = "SELECT * FROM users WHERE id = :user_id AND country = :country"
        param_defs = [
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)
            # Missing 'country' parameter definition
        ]
        with pytest.raises(ValueError, match="Parameter 'country' found in SQL but not in parameter definitions"):
            substitute_sql_parameters_safe(sql, {"user_id": 123, "country": "US"}, param_defs, "postgres")

    def test_type_conversion_error_raises_error(self):
        """Test that type conversion error raises ValueError."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        with pytest.raises(ValueError, match="Failed to convert parameter 'user_id'"):
            substitute_sql_parameters_safe(sql, {"user_id": "not_a_number"}, param_defs, "postgres")
