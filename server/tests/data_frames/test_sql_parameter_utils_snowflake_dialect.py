"""Unit tests for SQL parameter extraction and substitution with Snowflake dialect."""

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter
from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
    substitute_sql_parameters_safe,
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


class TestSubstituteSQLParametersSafeSnowflakeDialect:
    """Test cases for substitute_sql_parameters_safe with Snowflake dialect."""

    def test_basic_substitution(self):
        """Test basic parameter substitution with Snowflake."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        result = substitute_sql_parameters_safe(sql, {"user_id": 123}, param_defs, "snowflake")
        assert result == "SELECT * FROM users WHERE id = 123"

    def test_snowflake_qualified_table_names_with_substitution(self):
        """Test parameter substitution with Snowflake fully qualified table names."""
        sql = "SELECT * FROM database.schema.customers WHERE country = :country AND region = :region"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "region": "South"}, param_defs, "snowflake")
        assert result == "SELECT * FROM database.schema.customers WHERE country = 'UK' AND region = 'South'"

    def test_snowflake_cast_syntax_with_substitution(self):
        """Test parameter substitution with Snowflake cast syntax."""
        sql = "SELECT * FROM customers WHERE country = :country AND created_at >= :start_date::timestamp"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"country": "Germany", "start_date": "2021-06-15"}, param_defs, "snowflake"
        )
        # sqlglot may normalize :: syntax
        assert "Germany" in result
        assert "2021-06-15" in result

    def test_snowflake_lateral_flatten_with_substitution(self):
        """Test parameter substitution with Snowflake LATERAL FLATTEN."""
        sql = "SELECT * FROM customers, LATERAL FLATTEN(input => tags) WHERE country = :country AND value = :tag_value"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="tag_value", data_type="string", description="Tag value", example_value="tech"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "tag_value": "premium"}, param_defs, "snowflake")
        assert "'UK'" in result
        assert "'premium'" in result
        assert "FLATTEN" in result.upper()

    def test_snowflake_array_functions_with_substitution(self):
        """Test parameter substitution with Snowflake array functions."""
        sql = "SELECT * FROM products WHERE ARRAY_CONTAINS(tags, :tag) AND category = :category"
        param_defs = [
            QueryParameter(name="tag", data_type="string", description="Tag", example_value="sale"),
            QueryParameter(name="category", data_type="string", description="Category", example_value="Electronics"),
        ]
        result = substitute_sql_parameters_safe(sql, {"tag": "featured", "category": "Books"}, param_defs, "snowflake")
        assert "'featured'" in result
        assert "'Books'" in result
        assert "ARRAY_CONTAINS" in result.upper()

    def test_snowflake_object_functions_with_substitution(self):
        """Test parameter substitution with Snowflake object functions."""
        sql = "SELECT * FROM users WHERE metadata:country::string = :country AND metadata:region::string = :region"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "Germany", "region": "East"}, param_defs, "snowflake")
        assert "'Germany'" in result
        assert "'East'" in result

    def test_snowflake_cte_with_substitution(self):
        """Test parameter substitution in Snowflake CTEs."""
        sql = (
            "WITH filtered_customers AS ("
            "  SELECT * FROM customers WHERE country = :country"
            ") "
            "SELECT * FROM filtered_customers WHERE created_at >= :start_date"
        )
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"country": "UK", "start_date": "2021-06-15"}, param_defs, "snowflake"
        )
        assert "'UK'" in result
        assert "'2021-06-15'" in result
        assert "WITH" in result

    def test_snowflake_qualify_clause_with_substitution(self):
        """Test parameter substitution with Snowflake QUALIFY clause."""
        sql = (
            "SELECT * FROM sales "
            "WHERE date >= :start_date "
            "QUALIFY ROW_NUMBER() OVER (PARTITION BY region ORDER BY date DESC) <= :top_n"
        )
        param_defs = [
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
            QueryParameter(name="top_n", data_type="integer", description="Top N", example_value=5),
        ]
        result = substitute_sql_parameters_safe(sql, {"start_date": "2021-01-01", "top_n": 10}, param_defs, "snowflake")
        assert "'2021-01-01'" in result
        assert "10" in result
        assert "QUALIFY" in result
