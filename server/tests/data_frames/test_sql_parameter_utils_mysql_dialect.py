"""Unit tests for SQL parameter extraction with MySQL dialect."""

from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
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
