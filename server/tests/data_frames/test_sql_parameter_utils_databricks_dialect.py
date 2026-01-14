"""Unit tests for SQL parameter extraction with Databricks dialect."""

from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
)


class TestExtractParametersFromSQLDatabricksDialect:
    """Test cases for extract_parameters_from_sql with Databricks dialect."""

    def test_basic_parameter_extraction(self):
        """Test basic parameter extraction with Databricks."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["user_id"]

    def test_databricks_array_functions(self):
        """Test parameter extraction with Databricks array functions."""
        sql = "SELECT * FROM events WHERE array_contains(tags, :tag) AND event_date >= :start_date"
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["start_date", "tag"]

    def test_databricks_map_functions(self):
        """Test parameter extraction with Databricks map functions."""
        sql = (
            "SELECT * FROM users WHERE map_keys(metadata)['country'] = :country "
            "AND map_keys(metadata)['region'] = :region"
        )
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["country", "region"]

    def test_databricks_json_functions(self):
        """Test parameter extraction with Databricks JSON functions."""
        sql = (
            "SELECT * FROM users WHERE get_json_object(metadata, '$.country') = :country "
            "AND get_json_object(metadata, '$.region') = :region"
        )
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["country", "region"]

    def test_databricks_window_functions(self):
        """Test parameter extraction with Databricks window functions."""
        sql = (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY :partition_col "
            "ORDER BY :order_col) FROM sales WHERE date >= :start_date"
        )
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["order_col", "partition_col", "start_date"]

    def test_databricks_cte_with_parameters(self):
        """Test parameter extraction in Databricks CTEs."""
        sql = (
            "WITH filtered_events AS ("
            "  SELECT * FROM events WHERE event_date >= :start_date"
            ") "
            "SELECT * FROM filtered_events WHERE event_type = :event_type"
        )
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["event_type", "start_date"]

    def test_databricks_explode_arrays(self):
        """Test parameter extraction with Databricks EXPLODE."""
        sql = "SELECT * FROM users LATERAL VIEW EXPLODE(tags) t AS tag WHERE tag = :tag_value AND country = :country"
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["country", "tag_value"]

    def test_databricks_struct_access(self):
        """Test parameter extraction with Databricks struct access."""
        sql = "SELECT * FROM users WHERE address.country = :country AND address.region = :region"
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["country", "region"]

    def test_databricks_aggregate_functions(self):
        """Test parameter extraction with Databricks aggregate functions."""
        sql = (
            "SELECT user_id, collect_list(order_id) as order_ids "
            "FROM orders WHERE date >= :start_date AND date <= :end_date "
            "GROUP BY user_id HAVING COUNT(*) > :min_orders"
        )
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["end_date", "min_orders", "start_date"]

    def test_databricks_complex_query(self):
        """Test parameter extraction in a complex Databricks query."""
        sql = (
            "WITH ranked_events AS ("
            "  SELECT *, ROW_NUMBER() OVER ("
            "    PARTITION BY event_type ORDER BY event_date DESC"
            "  ) as rn FROM events WHERE event_date >= :start_date"
            ") "
            "SELECT e.event_type, COUNT(*) as count, SUM(e.value) as total "
            "FROM ranked_events e "
            "WHERE e.event_type = :event_type AND e.rn <= :top_n "
            "AND e.value > :min_value "
            "GROUP BY e.event_type"
        )
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["event_type", "min_value", "start_date", "top_n"]

    def test_databricks_union_all(self):
        """Test parameter extraction with Databricks UNION ALL."""
        sql = (
            "SELECT * FROM events WHERE event_type = :type1 AND date >= :start_date "
            "UNION ALL "
            "SELECT * FROM events WHERE event_type = :type2 AND date >= :start_date"
        )
        result = extract_parameters_from_sql(sql, dialect="databricks")
        assert result == ["start_date", "type1", "type2"]
