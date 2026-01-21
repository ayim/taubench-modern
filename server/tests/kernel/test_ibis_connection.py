"""Tests for ibis_utils module."""

import pytest

from agent_platform.server.kernel.ibis_utils import database_filter


class TestDatabaseFilter:
    """Tests for the database_filter function."""

    def test_both_database_and_schema_provided(self) -> None:
        """When both database and schema are provided, returns a tuple."""
        result = database_filter("mydb", "myschema")
        assert result == ("mydb", "myschema")

    def test_only_schema_provided(self) -> None:
        """When only schema is provided, returns just the schema string."""
        result = database_filter(None, "myschema")
        assert result == "myschema"

    def test_neither_provided(self) -> None:
        """When neither database nor schema is provided, returns None."""
        result = database_filter(None, None)
        assert result is None

    def test_only_database_provided(self) -> None:
        """When only database is provided (no schema), returns None."""
        result = database_filter("mydb", None)
        assert result is None

    def test_empty_database_with_schema(self) -> None:
        """Empty database string is treated as falsy, returns schema."""
        result = database_filter("", "myschema")
        assert result == "myschema"

    @pytest.mark.parametrize("inputs", [("mydb", ""), ("", ""), "mydb", None])
    def test_filter_returns_none(self, inputs) -> None:
        """Test cases that should return None."""
        # In Ibis, there are no implementations that provide only database.
        assert database_filter(inputs) is None
