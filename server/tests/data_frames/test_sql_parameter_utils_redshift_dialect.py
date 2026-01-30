"""Unit tests for SQL parameter extraction and substitution with Redshift dialect."""

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter
from agent_platform.core.data_frames.semantic_data_model_utils import (
    extract_parameters_from_sql,
)
from agent_platform.server.data_frames.sql_parameter_utils import (
    parameterize_sql_query,
    substitute_sql_parameters_safe,
)


def normalize_sql(sql: str) -> str:
    """Normalize SQL by collapsing whitespace for comparison."""
    return " ".join(sql.split())


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


class TestSubstituteSQLParametersSafeRedshiftDialect:
    """Test cases for substitute_sql_parameters_safe with Redshift dialect."""

    def test_basic_substitution(self):
        """Test basic parameter substitution with Redshift."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        result = substitute_sql_parameters_safe(sql, {"user_id": 123}, param_defs, "redshift")
        assert result == "SELECT * FROM users WHERE id = 123"

    def test_redshift_date_trunc_with_substitution(self):
        """Test parameter substitution with Redshift date_trunc function."""
        sql = "SELECT * FROM sales WHERE region = :region AND date_trunc('month', order_date) = :month"
        param_defs = [
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
            QueryParameter(name="month", data_type="datetime", description="Month", example_value="2020-01-01"),
        ]
        result = substitute_sql_parameters_safe(sql, {"region": "East", "month": "2021-06-01"}, param_defs, "redshift")
        assert result == (
            "SELECT * FROM sales WHERE region = 'East' AND DATE_TRUNC('MONTH', order_date) = '2021-06-01'"
        )

    def test_redshift_aggregate_functions_with_substitution(self):
        """Test parameter substitution with Redshift aggregate functions."""
        sql = (
            "SELECT user_id, LISTAGG(order_id, ',') WITHIN GROUP (ORDER BY date) "
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
            sql, {"start_date": "2021-01-01", "end_date": "2021-12-31", "min_orders": 10}, param_defs, "redshift"
        )
        assert result == (
            "SELECT user_id, LISTAGG(order_id, ',') WITHIN GROUP (ORDER BY date) FROM orders "
            "WHERE date >= '2021-01-01' AND date <= '2021-12-31' "
            "GROUP BY user_id HAVING COUNT(*) > 10"
        )

    def test_redshift_json_functions_with_substitution(self):
        """Test parameter substitution with Redshift JSON functions."""
        sql = (
            "SELECT * FROM users WHERE JSON_EXTRACT_PATH_TEXT(metadata, 'country') = :country "
            "AND JSON_EXTRACT_PATH_TEXT(metadata, 'region') = :region"
        )
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "region": "South"}, param_defs, "redshift")
        assert result == (
            "SELECT * FROM users WHERE JSON_EXTRACT_PATH_TEXT(metadata, 'country') = 'UK' "
            "AND JSON_EXTRACT_PATH_TEXT(metadata, 'region') = 'South'"
        )

    def test_redshift_cte_with_substitution(self):
        """Test parameter substitution in Redshift CTEs."""
        sql = (
            "WITH filtered_sales AS ("
            "  SELECT * FROM sales WHERE region = :region AND date >= :start_date"
            ") "
            "SELECT * FROM filtered_sales WHERE amount > :min_amount"
        )
        param_defs = [
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
            QueryParameter(name="min_amount", data_type="float", description="Min amount", example_value=100.0),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"region": "East", "start_date": "2021-06-15", "min_amount": 250.0}, param_defs, "redshift"
        )
        assert result == (
            "WITH filtered_sales AS (SELECT * FROM sales WHERE region = 'East' AND date >= '2021-06-15') "
            "SELECT * FROM filtered_sales WHERE amount > 250.0"
        )

    def test_redshift_lateral_join_with_substitution(self):
        """Test parameter substitution with Redshift LATERAL joins."""
        sql = (
            "SELECT u.name, o.total FROM users u "
            "CROSS JOIN LATERAL ("
            "  SELECT SUM(amount) as total FROM orders "
            "  WHERE user_id = u.id AND date >= :start_date"
            ") o WHERE u.country = :country"
        )
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"country": "UK", "start_date": "2021-01-01"}, param_defs, "redshift"
        )
        assert result == (
            "SELECT u.name, o.total FROM users AS u CROSS JOIN LATERAL "
            "(SELECT SUM(amount) AS total FROM orders WHERE user_id = u.id AND date >= '2021-01-01') AS o "
            "WHERE u.country = 'UK'"
        )


class TestParameterizeSQLQueryRedshiftDialect:
    """Test cases for parameterize_sql_query with Redshift dialect."""

    def test_basic_parameterization(self):
        """Test basic parameter extraction and conversion to :param format."""
        sql = "SELECT * FROM users WHERE id = 123 AND country = 'USA'"
        result = parameterize_sql_query(sql, dialect="redshift")

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
        result = parameterize_sql_query(sql, dialect="redshift")

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
        result = parameterize_sql_query(sql, dialect="redshift")

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
        result = parameterize_sql_query(sql, dialect="redshift")

        # Only the comparison should be parameterized
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "id"

        # Function argument should remain
        assert "2" in result.parameterized_sql

    def test_redshift_json_functions_parameterization(self):
        """Test parameterizing with Redshift JSON functions."""
        # Use a simpler query where column context is clear
        sql = "SELECT * FROM users WHERE country = 'USA' AND region = 'West'"
        result = parameterize_sql_query(sql, dialect="redshift")

        # Should extract both comparison values
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "country" in param_names
        assert "region" in param_names

    def test_redshift_lateral_join_parameterization(self):
        """Test parameterizing with Redshift LATERAL joins."""
        sql = (
            "SELECT u.name, o.total FROM users u "
            "CROSS JOIN LATERAL ("
            "  SELECT SUM(amount) as total FROM orders "
            "  WHERE user_id = u.id AND date >= '2021-01-01'"
            ") o WHERE u.country = 'USA'"
        )
        result = parameterize_sql_query(sql, dialect="redshift")

        # Should extract both literals
        assert len(result.parameters) >= 2
        assert any(p.data_type == "datetime" for p in result.parameters)
        # Verify full SQL with LATERAL preserved
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT u.name, o.total FROM users AS u CROSS JOIN LATERAL "
            "( SELECT SUM(amount) AS total FROM orders WHERE user_id = u.id AND date >= :date ) AS o "
            "WHERE u.country = :country"
        )

    def test_redshift_listagg_parameterization(self):
        """Test parameterizing with Redshift LISTAGG."""
        sql = (
            "SELECT user_id, LISTAGG(order_id, ',') as order_ids "
            "FROM orders WHERE date >= '2021-01-01' AND date <= '2021-12-31' "
            "GROUP BY user_id HAVING COUNT(*) > 10"
        )
        result = parameterize_sql_query(sql, dialect="redshift")

        # Should extract dates AND HAVING literal (now parameterized with function context)
        assert any(p.data_type == "datetime" for p in result.parameters)
        # HAVING COUNT(*) > 10 is now parameterized as :count
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT user_id, LISTAGG(order_id, ',') AS order_ids FROM orders "
            "WHERE date >= :date AND date <= :date_1 GROUP BY user_id HAVING COUNT(*) > :count"
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
        result = parameterize_sql_query(sql, "redshift")

        # Check that all parameters are extracted with distinct names
        param_names = {p.name for p in result.parameters}
        assert param_names == {"user_id", "user_id_secondary", "date", "datetime", "created_at", "created_at_utc"}
        assert len(result.parameters) == 6

        # Check full parameterized SQL (Redshift %(param)s format should be converted to :param)
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM orders WHERE user_id = :user_id AND user_id_secondary = :user_id_secondary "
            "AND date = :date AND datetime = :datetime AND created_at = :created_at "
            "AND created_at_utc = :created_at_utc"
        )

    def test_redshift_datediff_parameterization(self):
        """Test Redshift DATEDIFF function with parameterization improvements."""
        sql = "SELECT * FROM orders WHERE DATEDIFF(day, order_date, ship_date) > 3"
        result = parameterize_sql_query(sql, dialect="redshift")

        # Should parameterize the comparison value with function name and column
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "tsordsdiff_ship_date"
        assert result.parameters[0].example_value == 3

        # Verify full parameterized SQL (sqlglot may normalize DATEDIFF)
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM orders WHERE DATEDIFF(DAY, order_date, ship_date) > :tsordsdiff_ship_date"
        )

    def test_redshift_nvl_parameterization(self):
        """Test Redshift NVL function with parameterization improvements."""
        sql = "SELECT * FROM products WHERE NVL(discount, 0) > 10 AND status = 'active'"
        result = parameterize_sql_query(sql, dialect="redshift")

        # Should parameterize both the NVL comparison and status
        # sqlglot translates NVL to COALESCE
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "coalesce_discount" in param_names  # NVL → COALESCE by sqlglot
        assert "status" in param_names
        # sqlglot translates NVL to COALESCE
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM products WHERE COALESCE(discount, 0) > :coalesce_discount AND status = :status"
        )
