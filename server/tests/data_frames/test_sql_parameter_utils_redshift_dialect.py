"""Unit tests for SQL parameter extraction and substitution with Redshift dialect."""

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter
from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
    substitute_sql_parameters_safe,
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
        assert "'East'" in result
        assert "'2021-06-01'" in result
        assert "date_trunc" in result.lower()

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
        assert "'2021-01-01'" in result
        assert "'2021-12-31'" in result
        assert "10" in result
        assert "LISTAGG" in result.upper()

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
        assert "'UK'" in result
        assert "'South'" in result
        assert "JSON_EXTRACT_PATH_TEXT" in result.upper()

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
        assert "'East'" in result
        assert "'2021-06-15'" in result
        assert "250.0" in result
        assert "WITH" in result

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
        assert "'UK'" in result
        assert "'2021-01-01'" in result
        assert "LATERAL" in result
