"""Unit tests for SQL parameter extraction with Redshift dialect."""

from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
)


class TestExtractParametersFromSQLRedshiftDialect:
    """Test cases for extract_parameters_from_sql with Redshift dialect."""

    def test_basic_parameter_extraction(self):
        """Test basic parameter extraction with Redshift."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["user_id"]

    def test_redshift_date_trunc(self):
        """Test parameter extraction with Redshift date_trunc function."""
        sql = "SELECT * FROM sales WHERE region = :region AND date_trunc('month', order_date) = :month"
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["month", "region"]

    def test_redshift_window_functions(self):
        """Test parameter extraction with Redshift window functions."""
        sql = (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY :partition_col "
            "ORDER BY :order_col) FROM sales WHERE date >= :start_date"
        )
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["order_col", "partition_col", "start_date"]

    def test_redshift_aggregate_functions(self):
        """Test parameter extraction with Redshift aggregate functions."""
        sql = (
            "SELECT user_id, LISTAGG(order_id, ',') WITHIN GROUP (ORDER BY date) "
            "FROM orders WHERE date >= :start_date AND date <= :end_date "
            "GROUP BY user_id HAVING COUNT(*) > :min_orders"
        )
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["end_date", "min_orders", "start_date"]

    def test_redshift_json_functions(self):
        """Test parameter extraction with Redshift JSON functions."""
        sql = (
            "SELECT * FROM users WHERE JSON_EXTRACT_PATH_TEXT(metadata, 'country') = :country "
            "AND JSON_EXTRACT_PATH_TEXT(metadata, 'region') = :region"
        )
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["country", "region"]

    def test_redshift_cte_with_parameters(self):
        """Test parameter extraction in Redshift CTEs."""
        sql = (
            "WITH filtered_sales AS ("
            "  SELECT * FROM sales WHERE region = :region AND date >= :start_date"
            ") "
            "SELECT * FROM filtered_sales WHERE amount > :min_amount"
        )
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["min_amount", "region", "start_date"]

    def test_redshift_unnest_arrays(self):
        """Test parameter extraction with Redshift UNNEST."""
        sql = "SELECT * FROM users, UNNEST(tags) as tag WHERE tag = :tag_value AND country = :country"
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["country", "tag_value"]

    def test_redshift_lateral_join(self):
        """Test parameter extraction with Redshift LATERAL joins."""
        sql = (
            "SELECT u.name, o.total FROM users u "
            "CROSS JOIN LATERAL ("
            "  SELECT SUM(amount) as total FROM orders "
            "  WHERE user_id = u.id AND date >= :start_date"
            ") o WHERE u.country = :country"
        )
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["country", "start_date"]

    def test_redshift_merge_statement(self):
        """Test parameter extraction in Redshift MERGE statement (read-only validation)."""
        sql = (
            "SELECT * FROM target t "
            "INNER JOIN source s ON t.id = s.id "
            "WHERE s.date >= :start_date AND t.status = :status"
        )
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["start_date", "status"]

    def test_redshift_complex_query(self):
        """Test parameter extraction in a complex Redshift query."""
        sql = (
            "WITH ranked_sales AS ("
            "  SELECT *, ROW_NUMBER() OVER ("
            "    PARTITION BY region ORDER BY date DESC"
            "  ) as rn FROM sales WHERE date >= :start_date"
            ") "
            "SELECT r.region, COUNT(*) as count, SUM(r.amount) as total "
            "FROM ranked_sales r "
            "WHERE r.region = :region AND r.rn <= :top_n "
            "AND r.amount > :min_amount "
            "GROUP BY r.region"
        )
        result = extract_parameters_from_sql(sql, dialect="redshift")
        assert result == ["min_amount", "region", "start_date", "top_n"]
