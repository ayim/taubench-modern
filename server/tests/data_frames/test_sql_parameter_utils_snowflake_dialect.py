"""Unit tests for SQL parameter extraction with Snowflake dialect."""

from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
)


class TestExtractParametersFromSQLSnowflakeDialect:
    """Test cases for extract_parameters_from_sql with Snowflake dialect."""

    def test_basic_parameter_extraction(self):
        """Test basic parameter extraction with Snowflake."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["user_id"]

    def test_snowflake_qualified_table_names(self):
        """Test parameter extraction with Snowflake fully qualified table names."""
        sql = "SELECT * FROM database.schema.customers WHERE country = :country AND region = :region"
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["country", "region"]

    def test_snowflake_cast_syntax(self):
        """Test parameter extraction with Snowflake cast syntax."""
        sql = "SELECT * FROM customers WHERE country = :country AND created_at >= :start_date::timestamp"
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["country", "start_date"]

    def test_snowflake_lateral_flatten(self):
        """Test parameter extraction with Snowflake LATERAL FLATTEN."""
        sql = "SELECT * FROM customers, LATERAL FLATTEN(input => tags) WHERE country = :country AND value = :tag_value"
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["country", "tag_value"]

    def test_snowflake_array_functions(self):
        """Test parameter extraction with Snowflake array functions."""
        sql = "SELECT * FROM products WHERE ARRAY_CONTAINS(tags, :tag) AND category = :category"
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["category", "tag"]

    def test_snowflake_object_functions(self):
        """Test parameter extraction with Snowflake object functions."""
        sql = "SELECT * FROM users WHERE metadata:country::string = :country AND metadata:region::string = :region"
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["country", "region"]

    def test_snowflake_window_functions(self):
        """Test parameter extraction with Snowflake window functions."""
        sql = (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY :partition_col "
            "ORDER BY :order_col) FROM sales WHERE date >= :start_date"
        )
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["order_col", "partition_col", "start_date"]

    def test_snowflake_cte_with_parameters(self):
        """Test parameter extraction in Snowflake CTEs."""
        sql = (
            "WITH filtered_customers AS ("
            "  SELECT * FROM customers WHERE country = :country"
            ") "
            "SELECT * FROM filtered_customers WHERE created_at >= :start_date"
        )
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["country", "start_date"]

    def test_snowflake_variant_functions(self):
        """Test parameter extraction with Snowflake VARIANT functions."""
        sql = (
            "SELECT * FROM events WHERE GET_PATH(variant_data, 'country') = :country "
            "AND GET_PATH(variant_data, 'region') = :region"
        )
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["country", "region"]

    def test_snowflake_table_functions(self):
        """Test parameter extraction with Snowflake table functions."""
        sql = "SELECT * FROM TABLE(FLATTEN(input => parse_json(:json_data))) WHERE value = :tag_value"
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["json_data", "tag_value"]

    def test_snowflake_qualify_clause(self):
        """Test parameter extraction with Snowflake QUALIFY clause."""
        sql = (
            "SELECT * FROM sales "
            "WHERE date >= :start_date "
            "QUALIFY ROW_NUMBER() OVER (PARTITION BY region ORDER BY date DESC) <= :top_n"
        )
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["start_date", "top_n"]

    def test_snowflake_complex_query(self):
        """Test parameter extraction in a complex Snowflake query."""
        sql = (
            "WITH ranked_orders AS ("
            "  SELECT *, ROW_NUMBER() OVER ("
            "    PARTITION BY customer_id ORDER BY order_date DESC"
            "  ) as rn FROM orders WHERE order_date >= :start_date"
            ") "
            "SELECT c.name, COUNT(ro.id) as order_count, SUM(ro.amount) as total "
            "FROM customers c "
            "INNER JOIN ranked_orders ro ON c.id = ro.customer_id "
            "WHERE c.country = :country AND ro.rn <= :top_n "
            "AND ro.amount > :min_amount "
            "GROUP BY c.id, c.name"
        )
        result = extract_parameters_from_sql(sql, dialect="snowflake")
        assert result == ["country", "min_amount", "start_date", "top_n"]
