"""Unit tests for SQL parameter extraction and substitution with Snowflake dialect."""

from agent_platform.core.semantic_data_model.types import QueryParameter
from agent_platform.core.semantic_data_model.utils import (
    extract_parameters_from_sql,
)
from agent_platform.server.data_frames.sql_parameter_utils import (
    parameterize_sql_query,
    substitute_sql_parameters_safe,
)


def normalize_sql(sql: str) -> str:
    """Normalize SQL by collapsing whitespace for comparison."""
    return " ".join(sql.split())


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
        # sqlglot may normalize :: syntax and reorder cast
        assert result == (
            "SELECT * FROM customers WHERE country = 'Germany' AND created_at >= CAST('2021-06-15' AS TIMESTAMP)"
        )

    def test_snowflake_lateral_flatten_with_substitution(self):
        """Test parameter substitution with Snowflake LATERAL FLATTEN."""
        sql = "SELECT * FROM customers, LATERAL FLATTEN(input => tags) WHERE country = :country AND value = :tag_value"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="tag_value", data_type="string", description="Tag value", example_value="tech"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "tag_value": "premium"}, param_defs, "snowflake")
        assert result == (
            "SELECT * FROM customers, LATERAL FLATTEN(input => tags) AS _flattened(SEQ, KEY, PATH, INDEX, VALUE, THIS) "
            "WHERE country = 'UK' AND value = 'premium'"
        )

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
        assert result == (
            "SELECT * FROM users WHERE CAST(GET_PATH(metadata, 'country') AS TEXT) = 'Germany' "
            "AND CAST(GET_PATH(metadata, 'region') AS TEXT) = 'East'"
        )

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
        assert result == (
            "WITH filtered_customers AS (SELECT * FROM customers WHERE country = 'UK') "
            "SELECT * FROM filtered_customers WHERE created_at >= '2021-06-15'"
        )

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
        assert result == (
            "SELECT * FROM sales WHERE date >= '2021-01-01' "
            "QUALIFY ROW_NUMBER() OVER (PARTITION BY region ORDER BY date DESC) <= 10"
        )


class TestParameterizeSQLQuerySnowflakeDialect:
    """Test cases for parameterize_sql_query with Snowflake dialect."""

    def test_basic_parameterization(self):
        """Test basic parameter extraction and conversion to :param format."""
        sql = "SELECT * FROM users WHERE id = 123 AND country = 'USA'"
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Should extract both parameters
        assert len(result.parameters) == 2

        # Verify intelligent naming
        param_names = {p.name for p in result.parameters}
        assert "id" in param_names
        assert "country" in param_names

        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == ("SELECT * FROM users WHERE id = :id AND country = :country")

    def test_parameter_deduplication_same_column(self):
        """Test that same value in SAME column context creates only ONE parameter."""
        sql = "SELECT * FROM users WHERE user_id = 123 OR user_id = 123"
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Should have only ONE parameter since same column and same value
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "user_id"
        assert result.parameters[0].example_value == 123
        assert result.parameters[0].data_type == "integer"

        # Verify user_id appears twice but as same parameter
        assert result.parameterized_sql.count(":user_id") == 2

    def test_parameter_deduplication_different_columns(self):
        """Test that same value in DIFFERENT columns creates SEPARATE parameters."""
        sql = "SELECT * FROM orders WHERE user_id = 123 OR parent_id = 123"
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Should have TWO parameters - one for each column
        assert len(result.parameters) == 2
        assert all(p.example_value == 123 for p in result.parameters)

        # Each column gets its own parameter
        param_names = {p.name for p in result.parameters}
        assert "user_id" in param_names
        assert "parent_id" in param_names

    def test_function_arguments_not_parameterized(self):
        """Test that function arguments are not parameterized."""
        sql = "SELECT ROUND(price, 2) FROM products WHERE id = 124"
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Only the comparison should be parameterized
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "id"

        # Function argument should remain
        assert "2" in result.parameterized_sql

    def test_snowflake_qualified_table_names_parameterization(self):
        """Test parameterizing with Snowflake fully qualified table names."""
        sql = "SELECT * FROM database.schema.customers WHERE country = 'USA' AND region = 'West'"
        result = parameterize_sql_query(sql, dialect="snowflake")

        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "country" in param_names
        assert "region" in param_names
        # Verify full SQL (normalized to handle pretty-print)
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM database.schema.customers WHERE country = :country AND region = :region"
        )

    def test_snowflake_lateral_flatten_parameterization(self):
        """Test parameterizing with Snowflake LATERAL FLATTEN."""
        sql = "SELECT * FROM customers, LATERAL FLATTEN(input => tags) WHERE country = 'USA' AND value = 'tech'"
        result = parameterize_sql_query(sql, dialect="snowflake")

        assert len(result.parameters) == 2
        values_by_name = {p.name: p.example_value for p in result.parameters}
        assert values_by_name.get("country") == "USA" or values_by_name.get("value") == "tech"
        # Verify full SQL with LATERAL FLATTEN preserved (sqlglot expands column list)
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM customers, LATERAL FLATTEN(input => tags) AS _flattened(SEQ, KEY, PATH, INDEX, VALUE, THIS) "
            "WHERE country = :country AND value = :value"
        )

    def test_snowflake_array_functions_parameterization(self):
        """Test parameterizing with Snowflake array functions."""
        sql = "SELECT * FROM products WHERE ARRAY_CONTAINS(tags, 'featured') AND category = 'Electronics'"
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Should only extract category (function argument is not parameterized)
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "category"
        assert result.parameters[0].example_value == "Electronics"

        # Verify full SQL with ARRAY_CONTAINS and function argument preserved
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM products WHERE ARRAY_CONTAINS(tags, 'featured') AND category = :category"
        )

    def test_snowflake_qualify_clause_parameterization(self):
        """Test parameterizing with Snowflake QUALIFY clause."""
        sql = (
            "SELECT * FROM sales "
            "WHERE date >= '2021-01-01' "
            "QUALIFY ROW_NUMBER() OVER (PARTITION BY region ORDER BY date DESC) <= 10"
        )
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Should extract date AND the QUALIFY literal (now parameterized with function context)
        assert any(p.data_type == "datetime" for p in result.parameters)
        # The QUALIFY comparison is now parameterized using the PARTITION BY column context
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM sales WHERE date >= :date "
            "QUALIFY ROW_NUMBER() OVER (PARTITION BY region ORDER BY date DESC) <= :region"
        )

    def test_overlapping_parameter_names_comprehensive(self):
        """Test parameters from columns with overlapping names are handled correctly."""
        sql = """
            SELECT * FROM database.schema.orders
            WHERE user_id = 123
              AND user_id_secondary = 456
              AND date = '2021-01-01'
              AND datetime = '2021-01-01 10:00:00'
              AND created_at = '2021-01-01'
              AND created_at_timestamp = '2021-01-01 00:00:00'
        """
        result = parameterize_sql_query(sql, "snowflake")

        # Check that all parameters are extracted with distinct names
        param_names = {p.name for p in result.parameters}
        assert param_names == {"user_id", "user_id_secondary", "date", "datetime", "created_at", "created_at_timestamp"}
        assert len(result.parameters) == 6

        # Check full parameterized SQL (Snowflake preserves fully qualified table names)
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM database.schema.orders WHERE user_id = :user_id AND user_id_secondary = :user_id_secondary "
            "AND date = :date AND datetime = :datetime AND created_at = :created_at "
            "AND created_at_timestamp = :created_at_timestamp"
        )

    def test_snowflake_array_size_parameterization(self):
        """Test Snowflake ARRAY_SIZE function with parameterization improvements."""
        sql = "SELECT * FROM products WHERE ARRAY_SIZE(tags) > 5 AND category = 'Electronics'"
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Should parameterize both the array size comparison and category
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "arraysize_tags" in param_names  # slugify removes underscores
        assert "category" in param_names
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM products WHERE ARRAY_SIZE(tags) > :arraysize_tags AND category = :category"
        )

    def test_snowflake_datediff_parameterization(self):
        """Test Snowflake DATEDIFF function with parameterization improvements."""
        sql = "SELECT * FROM orders WHERE DATEDIFF(day, order_date, delivery_date) > 7"
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Should parameterize the comparison value with function name and column
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "datediff_delivery_date"
        assert result.parameters[0].example_value == 7
        # sqlglot capitalizes 'day' to 'DAY'
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM orders WHERE DATEDIFF(DAY, order_date, delivery_date) > :datediff_delivery_date"
        )

    def test_snowflake_iff_in_comparison_parameterization(self):
        """Test Snowflake IFF function with parameterization improvements."""
        sql = "SELECT * FROM users WHERE IFF(premium, discount_rate, 0) > 10"
        result = parameterize_sql_query(sql, dialect="snowflake")

        # Should parameterize the comparison value with function name and column
        # IFF is translated to IF, and premium column is found
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "if_premium"
        assert result.parameters[0].example_value == 10
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM users WHERE IFF(premium, discount_rate, 0) > :if_premium"
        )
