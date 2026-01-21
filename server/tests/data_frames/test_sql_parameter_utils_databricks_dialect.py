"""Unit tests for SQL parameter extraction and substitution with Databricks dialect."""

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter
from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
    parameterize_sql_query,
    substitute_sql_parameters_safe,
)


def normalize_sql(sql: str) -> str:
    """Normalize SQL by collapsing whitespace for comparison."""
    return " ".join(sql.split())


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


class TestSubstituteSQLParametersSafeDatabricksDialect:
    """Test cases for substitute_sql_parameters_safe with Databricks dialect."""

    def test_basic_substitution(self):
        """Test basic parameter substitution with Databricks."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        result = substitute_sql_parameters_safe(sql, {"user_id": 123}, param_defs, "databricks")
        assert result == "SELECT * FROM users WHERE id = 123"

    def test_databricks_array_functions_with_substitution(self):
        """Test parameter substitution with Databricks array functions."""
        sql = "SELECT * FROM events WHERE array_contains(tags, :tag) AND event_date >= :start_date"
        param_defs = [
            QueryParameter(name="tag", data_type="string", description="Tag", example_value="tech"),
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"tag": "premium", "start_date": "2021-06-15"}, param_defs, "databricks"
        )
        assert result == ("SELECT * FROM events WHERE ARRAY_CONTAINS(tags, 'premium') AND event_date >= '2021-06-15'")

    def test_databricks_json_functions_with_substitution(self):
        """Test parameter substitution with Databricks JSON functions."""
        sql = (
            "SELECT * FROM users WHERE get_json_object(metadata, '$.country') = :country "
            "AND get_json_object(metadata, '$.region') = :region"
        )
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "region": "South"}, param_defs, "databricks")
        # sqlglot normalizes get_json_object to : notation in Databricks
        assert result == "SELECT * FROM users WHERE metadata:country = 'UK' AND metadata:region = 'South'"

    def test_databricks_cte_with_substitution(self):
        """Test parameter substitution in Databricks CTEs."""
        sql = (
            "WITH filtered_events AS ("
            "  SELECT * FROM events WHERE event_date >= :start_date"
            ") "
            "SELECT * FROM filtered_events WHERE event_type = :event_type"
        )
        param_defs = [
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
            QueryParameter(name="event_type", data_type="string", description="Event type", example_value="click"),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"start_date": "2021-06-15", "event_type": "purchase"}, param_defs, "databricks"
        )
        assert result == (
            "WITH filtered_events AS (SELECT * FROM events WHERE event_date >= '2021-06-15') "
            "SELECT * FROM filtered_events WHERE event_type = 'purchase'"
        )

    def test_databricks_explode_arrays_with_substitution(self):
        """Test parameter substitution with Databricks EXPLODE."""
        sql = "SELECT * FROM users LATERAL VIEW EXPLODE(tags) t AS tag WHERE tag = :tag_value AND country = :country"
        param_defs = [
            QueryParameter(name="tag_value", data_type="string", description="Tag value", example_value="tech"),
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"tag_value": "python", "country": "Germany"}, param_defs, "databricks"
        )
        assert result == (
            "SELECT * FROM users LATERAL VIEW EXPLODE(tags) t AS tag WHERE tag = 'python' AND country = 'Germany'"
        )

    def test_databricks_struct_access_with_substitution(self):
        """Test parameter substitution with Databricks struct access."""
        sql = "SELECT * FROM users WHERE address.country = :country AND address.region = :region"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "region": "South"}, param_defs, "databricks")
        assert result == "SELECT * FROM users WHERE address.country = 'UK' AND address.region = 'South'"

    def test_databricks_aggregate_functions_with_substitution(self):
        """Test parameter substitution with Databricks aggregate functions."""
        sql = (
            "SELECT user_id, collect_list(order_id) as order_ids "
            "FROM orders WHERE date >= :start_date AND date <= :end_date "
            "GROUP BY user_id HAVING COUNT(*) > :min_orders"
        )
        param_defs = [
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
            QueryParameter(name="end_date", data_type="datetime", description="End date", example_value="2020-12-31"),
            QueryParameter(name="min_orders", data_type="integer", description="Min orders", example_value=5),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"start_date": "2021-01-01", "end_date": "2021-12-31", "min_orders": 10}, param_defs, "databricks"
        )
        assert result == (
            "SELECT user_id, COLLECT_LIST(order_id) AS order_ids FROM orders "
            "WHERE date >= '2021-01-01' AND date <= '2021-12-31' "
            "GROUP BY user_id HAVING COUNT(*) > 10"
        )

    def test_databricks_union_all_with_substitution(self):
        """Test parameter substitution with Databricks UNION ALL."""
        sql = (
            "SELECT * FROM events WHERE event_type = :type1 AND date >= :start_date "
            "UNION ALL "
            "SELECT * FROM events WHERE event_type = :type2 AND date >= :start_date"
        )
        param_defs = [
            QueryParameter(name="type1", data_type="string", description="Type 1", example_value="click"),
            QueryParameter(name="type2", data_type="string", description="Type 2", example_value="view"),
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"type1": "purchase", "type2": "checkout", "start_date": "2021-06-15"}, param_defs, "databricks"
        )
        assert result == (
            "SELECT * FROM events WHERE event_type = 'purchase' AND date >= '2021-06-15' "
            "UNION ALL SELECT * FROM events WHERE event_type = 'checkout' AND date >= '2021-06-15'"
        )


class TestParameterizeSQLQueryDatabricksDialect:
    """Test cases for parameterize_sql_query with Databricks dialect."""

    def test_basic_parameterization(self):
        """Test basic parameter extraction and conversion to :param format."""
        sql = "SELECT * FROM users WHERE id = 123 AND country = 'USA'"
        result = parameterize_sql_query(sql, dialect="databricks")

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
        result = parameterize_sql_query(sql, dialect="databricks")

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
        result = parameterize_sql_query(sql, dialect="databricks")

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
        result = parameterize_sql_query(sql, dialect="databricks")

        # Only the comparison should be parameterized
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "id"

        # Function argument should remain
        assert "2" in result.parameterized_sql

    def test_databricks_explode_arrays_parameterization(self):
        """Test parameterizing with Databricks EXPLODE."""
        sql = "SELECT * FROM users LATERAL VIEW EXPLODE(tags) t AS tag WHERE tag = 'python' AND country = 'USA'"
        result = parameterize_sql_query(sql, dialect="databricks")

        # Should extract both comparison values
        assert len(result.parameters) >= 2
        # Verify full SQL with EXPLODE preserved
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM users LATERAL VIEW EXPLODE(tags) t AS tag WHERE tag = :tag AND country = :country"
        )

    def test_databricks_struct_access_parameterization(self):
        """Test parameterizing with Databricks struct access."""
        sql = "SELECT * FROM users WHERE address.country = 'USA' AND address.region = 'West'"
        result = parameterize_sql_query(sql, dialect="databricks")

        # Should extract comparison values
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "country" in param_names
        assert "region" in param_names

        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM users WHERE address.country = :country AND address.region = :region"
        )

    def test_databricks_collect_list_parameterization(self):
        """Test parameterizing with Databricks collect_list."""
        sql = (
            "SELECT user_id, collect_list(order_id) as order_ids "
            "FROM orders WHERE date >= '2021-01-01' AND date <= '2021-12-31' "
            "GROUP BY user_id HAVING COUNT(*) > 10"
        )
        result = parameterize_sql_query(sql, dialect="databricks")

        # Should extract dates AND HAVING literal (now parameterized with function context)
        assert any(p.data_type == "datetime" for p in result.parameters)
        # HAVING COUNT(*) > 10 is now parameterized as :count
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT user_id, COLLECT_LIST(order_id) AS order_ids FROM orders "
            "WHERE date >= :date AND date <= :date_1 GROUP BY user_id HAVING COUNT(*) > :count"
        )

    def test_databricks_union_all_parameterization(self):
        """Test parameterizing with Databricks UNION ALL."""
        sql = (
            "SELECT * FROM events WHERE event_type = 'click' AND date >= '2021-01-01' "
            "UNION ALL "
            "SELECT * FROM events WHERE event_type = 'view' AND date >= '2021-01-01'"
        )
        result = parameterize_sql_query(sql, dialect="databricks")

        # Should extract parameters from both queries
        assert len(result.parameters) >= 2
        # Check that we have date parameters (may be 2 if in different contexts)
        date_params = [p for p in result.parameters if p.data_type == "datetime"]
        # We get 2 date params because they're in different SELECT statements
        # (different contexts even though same column name)
        assert len(date_params) >= 1
        # Verify full SQL with UNION ALL preserved
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM events WHERE event_type = :event_type AND date >= :date "
            "UNION ALL SELECT * FROM events WHERE event_type = :event_type_1 AND date >= :date"
        )

    def test_overlapping_parameter_names_comprehensive(self):
        """Test parameters from columns with overlapping names are handled correctly."""
        sql = """
            SELECT * FROM orders
            WHERE user_id = 123
              AND user_id_secondary = 456
              AND date = '2021-01-01'
              AND datetime = '2021-01-01 10:00:00'
              AND created_at = '2021-01-01'
              AND created_at_utc = '2021-01-01T00:00:00Z'
        """
        result = parameterize_sql_query(sql, "databricks")

        # Check that all parameters are extracted with distinct names
        param_names = {p.name for p in result.parameters}
        assert param_names == {"user_id", "user_id_secondary", "date", "datetime", "created_at", "created_at_utc"}
        assert len(result.parameters) == 6

        # Check full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM orders WHERE user_id = :user_id AND user_id_secondary = :user_id_secondary "
            "AND date = :date AND datetime = :datetime AND created_at = :created_at "
            "AND created_at_utc = :created_at_utc"
        )

    def test_databricks_size_array_parameterization(self):
        """Test Databricks SIZE function with parameterization improvements."""
        sql = "SELECT * FROM products WHERE SIZE(tags) > 3 AND price > 100"
        result = parameterize_sql_query(sql, dialect="databricks")

        # Should parameterize both the array size comparison and price
        # sqlglot translates SIZE to ARRAYSIZE
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "arraysize_tags" in param_names  # SIZE → ARRAYSIZE by sqlglot
        assert "price" in param_names
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM products WHERE SIZE(tags) > :arraysize_tags AND price > :price"
        )

    def test_databricks_array_contains_parameterization(self):
        """Test Databricks ARRAY_CONTAINS with parameterization improvements."""
        sql = "SELECT * FROM products WHERE ARRAY_CONTAINS(categories, 'electronics') = true AND stock > 0"
        result = parameterize_sql_query(sql, dialect="databricks")

        # Should parameterize the boolean and stock comparison (function arguments not parameterized)
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "stock" in param_names
        assert "arraycontains_categories" in param_names  # slugify removes underscores

        # Verify full parameterized SQL (function argument 'electronics' preserved, boolean parameterized)
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM products WHERE ARRAY_CONTAINS(categories, 'electronics') = "
            ":arraycontains_categories AND stock > :stock"
        )

    def test_databricks_datediff_parameterization(self):
        """Test Databricks DATEDIFF function with parameterization improvements."""
        sql = "SELECT * FROM orders WHERE DATEDIFF(delivery_date, order_date) > 5"
        result = parameterize_sql_query(sql, dialect="databricks")

        # Should parameterize the comparison value with function name and column
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "datediff_delivery_date"
        assert result.parameters[0].example_value == 5
        # sqlglot normalizes DATEDIFF to include DAY unit and reorders arguments
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM orders WHERE DATEDIFF(DAY, order_date, delivery_date) > :datediff_delivery_date"
        )
