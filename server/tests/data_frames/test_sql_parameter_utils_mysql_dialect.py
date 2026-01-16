"""Unit tests for SQL parameter extraction and substitution with MySQL dialect."""

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter
from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
    substitute_sql_parameters_safe,
)


class TestExtractParametersFromSQLMySQLDialect:
    """Test cases for extract_parameters_from_sql with MySQL dialect."""

    def test_basic_parameter_extraction(self):
        """Test basic parameter extraction with MySQL."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["user_id"]

    def test_mysql_between_clause(self):
        """Test parameter extraction with MySQL BETWEEN clause."""
        sql = "SELECT * FROM products WHERE category = :category AND price BETWEEN :min_price AND :max_price"
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["category", "max_price", "min_price"]

    def test_mysql_string_functions(self):
        """Test parameter extraction with MySQL string functions."""
        sql = "SELECT * FROM products WHERE CONCAT(name, :suffix) LIKE :pattern AND category = :category"
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["category", "pattern", "suffix"]

    def test_mysql_date_functions(self):
        """Test parameter extraction with MySQL date functions."""
        sql = (
            "SELECT * FROM users WHERE status = :status "
            "AND created_at >= :start_date "
            "AND YEAR(created_at) = :year "
            "AND MONTH(created_at) = :month"
        )
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["month", "start_date", "status", "year"]

    def test_mysql_json_functions(self):
        """Test parameter extraction with MySQL JSON functions."""
        sql = (
            "SELECT * FROM users WHERE JSON_EXTRACT(metadata, '$.country') = :country "
            "AND JSON_EXTRACT(metadata, '$.region') = :region"
        )
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["country", "region"]

    def test_mysql_window_functions(self):
        """Test parameter extraction with MySQL window functions."""
        sql = (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY :partition_col "
            "ORDER BY :order_col) FROM sales WHERE date >= :start_date"
        )
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["order_col", "partition_col", "start_date"]

    def test_mysql_cte_with_parameters(self):
        """Test parameter extraction in MySQL CTEs."""
        sql = (
            "WITH filtered_users AS ("
            "  SELECT * FROM users WHERE country = :country"
            ") "
            "SELECT * FROM filtered_users WHERE age > :min_age"
        )
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["country", "min_age"]

    def test_mysql_in_clause_with_parameters(self):
        """Test parameter extraction in MySQL IN clauses."""
        sql = "SELECT * FROM orders WHERE status IN (:status1, :status2, :status3) AND user_id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["status1", "status2", "status3", "user_id"]

    def test_mysql_case_statement(self):
        """Test parameter extraction in MySQL CASE statements."""
        sql = (
            "SELECT CASE WHEN status = :status THEN 'active' "
            "ELSE 'inactive' END as status_label FROM users WHERE id = :user_id"
        )
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["status", "user_id"]

    def test_mysql_group_concat(self):
        """Test parameter extraction with MySQL GROUP_CONCAT."""
        sql = (
            "SELECT user_id, GROUP_CONCAT(order_id) as order_ids "
            "FROM orders WHERE date >= :start_date AND date <= :end_date "
            "GROUP BY user_id HAVING COUNT(*) > :min_orders"
        )
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == ["end_date", "min_orders", "start_date"]

    def test_mysql_complex_query(self):
        """Test parameter extraction in a complex MySQL query."""
        sql = (
            "SELECT u.name, COUNT(o.id) as order_count, SUM(o.total) as total "
            "FROM users u "
            "LEFT JOIN orders o ON u.id = o.user_id "
            "WHERE u.country = :country "
            "AND o.date >= :start_date AND o.date <= :end_date "
            "GROUP BY u.id, u.name "
            "HAVING COUNT(o.id) >= :min_orders "
            "ORDER BY total DESC "
            "LIMIT :limit_count"
        )
        result = extract_parameters_from_sql(sql, dialect="mysql")
        assert result == [
            "country",
            "end_date",
            "limit_count",
            "min_orders",
            "start_date",
        ]


class TestSubstituteSQLParametersSafeMySQLDialect:
    """Test cases for substitute_sql_parameters_safe with MySQL dialect."""

    def test_basic_substitution(self):
        """Test basic parameter substitution with MySQL."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        result = substitute_sql_parameters_safe(sql, {"user_id": 123}, param_defs, "mysql")
        assert result == "SELECT * FROM users WHERE id = 123"

    def test_mysql_between_clause_with_substitution(self):
        """Test parameter substitution with MySQL BETWEEN clause."""
        sql = "SELECT * FROM products WHERE category = :category AND price BETWEEN :min_price AND :max_price"
        param_defs = [
            QueryParameter(name="category", data_type="string", description="Category", example_value="Electronics"),
            QueryParameter(name="min_price", data_type="float", description="Min price", example_value=100.0),
            QueryParameter(name="max_price", data_type="float", description="Max price", example_value=500.0),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"category": "Books", "min_price": 10.0, "max_price": 50.0}, param_defs, "mysql"
        )
        assert result == "SELECT * FROM products WHERE category = 'Books' AND price BETWEEN 10.0 AND 50.0"

    def test_mysql_string_functions_with_substitution(self):
        """Test parameter substitution with MySQL string functions."""
        sql = "SELECT * FROM products WHERE CONCAT(name, :suffix) LIKE :pattern AND category = :category"
        param_defs = [
            QueryParameter(name="suffix", data_type="string", description="Suffix", example_value="_test"),
            QueryParameter(name="pattern", data_type="string", description="Pattern", example_value="%book%"),
            QueryParameter(name="category", data_type="string", description="Category", example_value="Books"),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"suffix": "_premium", "pattern": "%laptop%", "category": "Electronics"}, param_defs, "mysql"
        )
        assert "'_premium'" in result
        assert "'%laptop%'" in result
        assert "'Electronics'" in result
        assert "CONCAT" in result

    def test_mysql_json_functions_with_substitution(self):
        """Test parameter substitution with MySQL JSON functions."""
        sql = (
            "SELECT * FROM users WHERE JSON_EXTRACT(metadata, '$.country') = :country "
            "AND JSON_EXTRACT(metadata, '$.region') = :region"
        )
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "region": "South"}, param_defs, "mysql")
        assert "'UK'" in result
        assert "'South'" in result
        assert "JSON_EXTRACT" in result

    def test_mysql_cte_with_substitution(self):
        """Test parameter substitution in MySQL CTEs."""
        sql = (
            "WITH filtered_users AS ("
            "  SELECT * FROM users WHERE country = :country"
            ") "
            "SELECT * FROM filtered_users WHERE age > :min_age"
        )
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="min_age", data_type="integer", description="Min age", example_value=18),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "Germany", "min_age": 25}, param_defs, "mysql")
        assert "'Germany'" in result
        assert "25" in result
        assert "WITH" in result

    def test_mysql_case_statement_with_substitution(self):
        """Test parameter substitution in MySQL CASE statements."""
        sql = (
            "SELECT CASE WHEN status = :status THEN 'active' "
            "ELSE 'inactive' END as status_label FROM users WHERE id = :user_id"
        )
        param_defs = [
            QueryParameter(name="status", data_type="string", description="Status", example_value="active"),
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1),
        ]
        result = substitute_sql_parameters_safe(sql, {"status": "pending", "user_id": 456}, param_defs, "mysql")
        assert "'pending'" in result
        assert "456" in result
        assert "CASE" in result

    def test_mysql_group_concat_with_substitution(self):
        """Test parameter substitution with MySQL GROUP_CONCAT."""
        sql = (
            "SELECT user_id, GROUP_CONCAT(order_id) as order_ids "
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
            sql, {"start_date": "2021-01-01", "end_date": "2021-12-31", "min_orders": 10}, param_defs, "mysql"
        )
        assert "'2021-01-01'" in result
        assert "'2021-12-31'" in result
        assert "10" in result
        assert "GROUP_CONCAT" in result.upper()
