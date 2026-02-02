import pytest


class TestExtractMissingParameters:
    """Tests for extract_missing_parameters function.

    This function extracts parameters from SQL that are not already defined,
    returning auto-generated QueryParameter objects for the missing ones.
    """

    def test_all_parameters_missing(self):
        """Test that all parameters are returned when none are defined."""
        from agent_platform.core.data_frames.semantic_data_model_utils import (
            extract_missing_parameters,
        )

        sql = "SELECT * FROM users WHERE id = :user_id AND country = :country"
        result = extract_missing_parameters(sql, "postgres", None)

        assert len(result) == 2
        param_names = {p.name for p in result}
        assert param_names == {"user_id", "country"}
        # Verify auto-generated defaults
        for param in result:
            assert param.data_type == "string"
            assert param.example_value is None
            assert param.description == "Please provide description for this parameter"

    def test_some_parameters_already_defined(self):
        """Test that only missing parameters are returned when some are defined."""
        from agent_platform.core.data_frames.semantic_data_model_types import (
            QueryParameter,
        )
        from agent_platform.core.data_frames.semantic_data_model_utils import (
            extract_missing_parameters,
        )

        sql = "SELECT * FROM users WHERE id = :user_id AND country = :country AND status = :status"
        existing = [
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1),
        ]
        result = extract_missing_parameters(sql, "postgres", existing)

        assert len(result) == 2
        param_names = {p.name for p in result}
        assert param_names == {"country", "status"}

    def test_all_parameters_already_defined(self):
        """Test that empty list is returned when all parameters are defined."""
        from agent_platform.core.data_frames.semantic_data_model_types import (
            QueryParameter,
        )
        from agent_platform.core.data_frames.semantic_data_model_utils import (
            extract_missing_parameters,
        )

        sql = "SELECT * FROM users WHERE id = :user_id AND country = :country"
        existing = [
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1),
            QueryParameter(name="country", data_type="string", description="Country code", example_value="US"),
        ]
        result = extract_missing_parameters(sql, "postgres", existing)

        assert result == []

    def test_no_parameters_in_sql(self):
        """Test that empty list is returned when SQL has no parameters."""
        from agent_platform.core.data_frames.semantic_data_model_utils import (
            extract_missing_parameters,
        )

        sql = "SELECT * FROM users WHERE id = 123"
        result = extract_missing_parameters(sql, "postgres", None)

        assert result == []

    def test_invalid_sql_returns_empty_list(self):
        """Test that invalid SQL returns empty list instead of raising."""
        from agent_platform.core.data_frames.semantic_data_model_utils import (
            extract_missing_parameters,
        )

        sql = "SELECT * FROM WHERE invalid syntax"
        with pytest.raises(ValueError):  # noqa: PT011
            extract_missing_parameters(sql, "postgres", None)

    def test_empty_existing_parameters_list(self):
        """Test that empty list behaves same as None for existing parameters."""
        from agent_platform.core.data_frames.semantic_data_model_utils import (
            extract_missing_parameters,
        )

        sql = "SELECT * FROM users WHERE id = :user_id"
        result = extract_missing_parameters(sql, "postgres", [])

        assert len(result) == 1
        assert result[0].name == "user_id"
