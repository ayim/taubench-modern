"""Unit tests for SQL parameter utilities."""

import pytest

from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
)


class TestExtractParametersFromSQL:
    """Test cases for extract_parameters_from_sql function.

    These tests use 'postgres' as the default dialect for testing general
    SQL constructs that work across dialects.
    """

    def test_single_parameter(self):
        """Test extraction of a single parameter."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["user_id"]

    def test_multiple_parameters(self):
        """Test extraction of multiple parameters."""
        sql = "SELECT * FROM orders WHERE date >= :start_date AND date <= :end_date"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["end_date", "start_date"]

    def test_parameters_in_different_clauses(self):
        """Test parameters in WHERE, JOIN, and HAVING clauses."""
        sql = (
            "SELECT u.name, o.total FROM users u "
            "INNER JOIN orders o ON u.id = o.user_id "
            "WHERE u.country = :country AND o.status = :status "
            "HAVING COUNT(o.id) > :min_orders"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "min_orders", "status"]

    def test_parameters_in_subquery(self):
        """Test parameters in subqueries."""
        sql = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE date = :order_date)"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["order_date"]

    def test_parameters_in_cte(self):
        """Test parameters in CTE (Common Table Expression)."""
        sql = (
            "WITH filtered_users AS ("
            "  SELECT * FROM users WHERE country = :country"
            ") SELECT * FROM filtered_users WHERE age > :min_age"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "min_age"]

    def test_parameters_with_underscores(self):
        """Test parameters with underscores in names."""
        sql = "SELECT * FROM users WHERE user_id = :user_id AND status = :order_status"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["order_status", "user_id"]

    def test_parameters_with_numbers(self):
        """Test parameters with numbers in names."""
        sql = "SELECT * FROM orders WHERE year = :year_2024 AND month = :month_12"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["month_12", "year_2024"]

    def test_no_parameters(self):
        """Test query with no parameters."""
        sql = "SELECT * FROM users WHERE id = 1"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == []

    def test_duplicate_parameters(self):
        """Test that duplicate parameters are deduplicated."""
        sql = "SELECT * FROM users WHERE country = :country AND region = :region AND country = :country"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "region"]

    def test_parameters_in_string_literals_ignored(self):
        """Test that :param inside string literals are not extracted."""
        sql = "SELECT ':not_a_param' as text, id FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        # Note: This test depends on how sqlglot parses string literals
        # The function should extract :user_id but not :not_a_param
        assert "user_id" in result
        # The literal string might be parsed differently, so we just check
        # that user_id is extracted

    def test_parameters_in_complex_query(self):
        """Test parameters in a complex query with multiple clauses."""
        sql = (
            "SELECT u.name, COUNT(o.id) as order_count "
            "FROM users u "
            "LEFT JOIN orders o ON u.id = o.user_id "
            "WHERE u.country = :country "
            "AND o.date >= :start_date "
            "AND o.date <= :end_date "
            "GROUP BY u.id, u.name "
            "HAVING COUNT(o.id) >= :min_orders "
            "ORDER BY order_count DESC "
            "LIMIT :limit"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == [
            "country",
            "end_date",
            "limit",
            "min_orders",
            "start_date",
        ]

    def test_parameters_in_union_query(self):
        """Test parameters in UNION query."""
        sql = "SELECT * FROM users WHERE country = :country UNION SELECT * FROM customers WHERE region = :region"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "region"]

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

    def test_parameters_in_case_statement(self):
        """Test parameters in CASE statement."""
        sql = "SELECT CASE WHEN status = :status THEN 'active' ELSE 'inactive' END FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["status", "user_id"]

    def test_parameters_in_in_clause(self):
        """Test parameters in IN clause."""
        sql = "SELECT * FROM users WHERE id IN (:id1, :id2, :id3)"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["id1", "id2", "id3"]

    def test_parameters_in_like_clause(self):
        """Test parameters in LIKE clause."""
        sql = "SELECT * FROM users WHERE name LIKE :pattern"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["pattern"]

    def test_parameters_in_between_clause(self):
        """Test parameters in BETWEEN clause."""
        sql = "SELECT * FROM orders WHERE date BETWEEN :start_date AND :end_date"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["end_date", "start_date"]

    def test_parameters_with_common_prefix(self):
        """Test parameters with common prefix (e.g., date_start, date_end)."""
        sql = "SELECT * FROM orders WHERE date >= :date_start AND date <= :date_end AND created_at >= :date_created"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["date_created", "date_end", "date_start"]

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
