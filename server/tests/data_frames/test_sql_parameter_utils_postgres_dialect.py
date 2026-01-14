"""Unit tests for SQL parameter extraction with PostgreSQL dialect."""

from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
)


class TestExtractParametersFromSQLPostgresDialect:
    """Test cases for extract_parameters_from_sql with PostgreSQL dialect."""

    def test_basic_parameter_extraction(self):
        """Test basic parameter extraction with PostgreSQL."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["user_id"]

    def test_postgres_cast_syntax(self):
        """Test parameter extraction with PostgreSQL cast syntax (::)."""
        sql = (
            "SELECT id::text, created_at::date FROM users WHERE country = :country AND created_at::date = :date_filter"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "date_filter"]

    def test_postgres_json_operators(self):
        """Test parameter extraction with PostgreSQL JSON operators."""
        sql = (
            "SELECT * FROM users WHERE metadata->>'country' = :country "
            "AND metadata->>'region' = :region "
            "AND metadata->'tags'->0 = :first_tag"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "first_tag", "region"]

    def test_postgres_array_operators(self):
        """Test parameter extraction with PostgreSQL array operators."""
        sql = "SELECT * FROM products WHERE tags @> ARRAY[:tag]::text[] AND category = ANY(:categories::text[])"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["categories", "tag"]

    def test_postgres_window_functions(self):
        """Test parameter extraction with PostgreSQL window functions."""
        sql = (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY :partition_col "
            "ORDER BY :order_col) FROM sales WHERE date >= :start_date"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["order_col", "partition_col", "start_date"]

    def test_postgres_cte_with_parameters(self):
        """Test parameter extraction in PostgreSQL CTEs."""
        sql = (
            "WITH filtered_users AS ("
            "  SELECT * FROM users WHERE country = :country"
            ") "
            "SELECT * FROM filtered_users WHERE age > :min_age"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "min_age"]

    def test_postgres_full_text_search(self):
        """Test parameter extraction with PostgreSQL full-text search."""
        sql = (
            "SELECT * FROM documents WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :search_term)"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["search_term"]

    def test_postgres_lateral_join(self):
        """Test parameter extraction with PostgreSQL LATERAL joins."""
        sql = (
            "SELECT u.name, o.total FROM users u "
            "CROSS JOIN LATERAL ("
            "  SELECT SUM(amount) as total FROM orders "
            "  WHERE user_id = u.id AND date >= :start_date"
            ") o WHERE u.country = :country"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "start_date"]

    def test_postgres_array_aggregation(self):
        """Test parameter extraction with PostgreSQL array aggregation."""
        sql = (
            "SELECT user_id, array_agg(order_id ORDER BY date) "
            "FROM orders WHERE date >= :start_date AND date <= :end_date "
            "GROUP BY user_id HAVING COUNT(*) > :min_orders"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["end_date", "min_orders", "start_date"]

    def test_postgres_unnest_arrays(self):
        """Test parameter extraction with PostgreSQL UNNEST."""
        sql = "SELECT * FROM users, UNNEST(tags) as tag WHERE tag = :tag_value AND country = :country"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "tag_value"]

    def test_postgres_double_colon_not_parameter(self):
        """Test that PostgreSQL double colon (::) is not treated as parameter."""
        sql = "SELECT id::text FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["user_id"]

    def test_postgres_complex_query(self):
        """Test parameter extraction in a complex PostgreSQL query."""
        sql = (
            "WITH ranked_orders AS ("
            "  SELECT *, ROW_NUMBER() OVER ("
            "    PARTITION BY user_id ORDER BY date DESC"
            "  ) as rn FROM orders WHERE date >= :start_date"
            ") "
            "SELECT u.name, ro.total FROM users u "
            "INNER JOIN ranked_orders ro ON u.id = ro.user_id "
            "WHERE u.country = :country AND ro.rn <= :top_n "
            "AND ro.total > :min_total"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "min_total", "start_date", "top_n"]
