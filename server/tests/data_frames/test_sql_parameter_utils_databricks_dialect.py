"""Unit tests for SQL parameter extraction and substitution with Databricks dialect."""

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter
from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
    substitute_sql_parameters_safe,
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
        assert "'premium'" in result
        assert "'2021-06-15'" in result
        assert "array_contains" in result.lower()

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
        assert "'2021-06-15'" in result
        assert "'purchase'" in result
        assert "WITH" in result

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
        assert "'python'" in result
        assert "'Germany'" in result
        assert "EXPLODE" in result.upper()

    def test_databricks_struct_access_with_substitution(self):
        """Test parameter substitution with Databricks struct access."""
        sql = "SELECT * FROM users WHERE address.country = :country AND address.region = :region"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "region": "South"}, param_defs, "databricks")
        assert "'UK'" in result
        assert "'South'" in result

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
        assert "'2021-01-01'" in result
        assert "'2021-12-31'" in result
        assert "10" in result
        assert "collect_list" in result.lower()

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
        assert "'purchase'" in result
        assert "'checkout'" in result
        assert "'2021-06-15'" in result
        assert "UNION" in result
