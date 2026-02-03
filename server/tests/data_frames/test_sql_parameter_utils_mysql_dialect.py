"""Unit tests for SQL parameter extraction and substitution with MySQL dialect."""

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
        assert (
            result
            == "SELECT * FROM products WHERE CONCAT(name, '_premium') LIKE '%laptop%' AND category = 'Electronics'"
        )

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
        assert result == (
            "SELECT * FROM users WHERE JSON_EXTRACT(metadata, '$.country') = 'UK' "
            "AND JSON_EXTRACT(metadata, '$.region') = 'South'"
        )

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
        assert result == (
            "WITH filtered_users AS (SELECT * FROM users WHERE country = 'Germany') "
            "SELECT * FROM filtered_users WHERE age > 25"
        )

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
        assert result == (
            "SELECT CASE WHEN status = 'pending' THEN 'active' ELSE 'inactive' END AS status_label "
            "FROM users WHERE id = 456"
        )

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
        assert result == (
            "SELECT user_id, GROUP_CONCAT(order_id SEPARATOR ',') AS order_ids FROM orders "
            "WHERE date >= '2021-01-01' AND date <= '2021-12-31' "
            "GROUP BY user_id HAVING COUNT(*) > 10"
        )


class TestParameterizeSQLQueryMySQLDialect:
    """Test cases for parameterize_sql_query with MySQL dialect."""

    def test_basic_parameterization(self):
        """Test basic parameter extraction and conversion to :param format."""
        sql = "SELECT * FROM users WHERE id = 123 AND country = 'USA'"
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should extract both parameters
        assert len(result.parameters) == 2

        # Should use :param format
        assert ":id" in result.parameterized_sql
        assert ":country" in result.parameterized_sql

        # Verify intelligent naming
        param_names = {p.name for p in result.parameters}
        assert "id" in param_names
        assert "country" in param_names

    def test_parameter_deduplication_same_column(self):
        """Test that same value in SAME column context creates only ONE parameter."""
        sql = "SELECT * FROM users WHERE user_id = 123 OR user_id = 123"
        result = parameterize_sql_query(sql, dialect="mysql")

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
        result = parameterize_sql_query(sql, dialect="mysql")

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
        result = parameterize_sql_query(sql, dialect="mysql")

        # Only the comparison should be parameterized
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "id"

        # Function argument should remain
        assert "2" in result.parameterized_sql

    def test_mysql_json_functions_parameterization(self):
        """Test parameterizing with MySQL JSON functions."""
        # Use a simpler query where column context is clear
        sql = "SELECT * FROM users WHERE country = 'USA' AND JSON_LENGTH(tags) > 5"
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should extract both country and the comparison against JSON_LENGTH function
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "country" in param_names
        assert "anonymous_tags" in param_names  # JSON_LENGTH(tags) creates anonymous_tags parameter
        # Verify full SQL with both parameterized
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM users WHERE country = :country AND JSON_LENGTH(tags) > :anonymous_tags"
        )

    def test_mysql_group_concat_parameterization(self):
        """Test parameterizing with MySQL GROUP_CONCAT."""
        sql = (
            "SELECT user_id, GROUP_CONCAT(order_id) as order_ids "
            "FROM orders WHERE date >= '2021-01-01' AND date <= '2021-12-31' "
            "GROUP BY user_id HAVING COUNT(*) > 10"
        )
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should extract dates AND HAVING count literal
        assert any(p.data_type == "datetime" for p in result.parameters)
        assert any(p.name == "count" for p in result.parameters)
        # Verify full SQL with GROUP_CONCAT and HAVING parameterized (sqlglot adds default SEPARATOR)
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT user_id, GROUP_CONCAT(order_id SEPARATOR ',') AS order_ids FROM orders "
            "WHERE date >= :date AND date <= :date_1 GROUP BY user_id HAVING COUNT(*) > :count"
        )

    def test_mysql_case_statement_parameterization(self):
        """Test parameterizing MySQL CASE statements."""
        sql = (
            "SELECT CASE WHEN status = 'active' THEN 'online' "
            "ELSE 'offline' END as status_label FROM users WHERE id = 123"
        )
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should extract both the WHEN comparison and WHERE comparison
        assert len(result.parameters) >= 2
        assert any(p.name == "id" for p in result.parameters)
        # Verify full SQL with CASE statement and parameterized WHEN condition
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT CASE WHEN status = :status THEN 'online' ELSE 'offline' END AS status_label "
            "FROM users WHERE id = :id"
        )

    def test_mysql_in_clause_parameterization(self):
        """Test parameterizing MySQL IN clause."""
        sql = "SELECT * FROM users WHERE status IN ('active', 'pending', 'approved')"
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should extract all IN values with intelligent naming
        assert len(result.parameters) == 3
        assert all(p.data_type == "string" for p in result.parameters)

        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM users WHERE status IN (:status, :status_1, :status_2)"
        )

    def test_overlapping_parameter_names_comprehensive(self):
        """Test parameters from columns with overlapping names are handled correctly."""
        sql = """
            SELECT * FROM orders
            WHERE user_id = 123
              AND user_id_secondary = 456
              AND date = '2021-01-01'
              AND datetime = '2021-01-01 10:00:00'
              AND name = 'test'
              AND name_full = 'Test User'
        """
        result = parameterize_sql_query(sql, "mysql")

        # Check that all parameters are extracted with distinct names
        param_names = {p.name for p in result.parameters}
        assert param_names == {"user_id", "user_id_secondary", "date", "datetime", "name", "name_full"}
        assert len(result.parameters) == 6

        # Check full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM orders WHERE user_id = :user_id AND user_id_secondary = :user_id_secondary "
            "AND date = :date AND datetime = :datetime AND name = :name AND name_full = :name_full"
        )

    def test_mysql_string_function_parameterization(self):
        """Test MySQL-specific string functions with parameterization improvements."""
        # Test CONCAT_WS with comparison
        sql = "SELECT * FROM products WHERE CONCAT_WS('-', brand, model) = 'Apple-iPhone'"
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should parameterize the comparison value with function name
        # slugify converts CONCAT_WS to concatws, then combines with column name
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "concatws_brand"
        assert result.parameters[0].example_value == "Apple-iPhone"
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM products WHERE CONCAT_WS('-', brand, model) = :concatws_brand"
        )

    def test_mysql_find_in_set_parameterization(self):
        """Test MySQL FIND_IN_SET function with parameterization improvements."""
        sql = "SELECT * FROM users WHERE FIND_IN_SET(role, permissions) > 0 AND status = 'active'"
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should parameterize both the comparison against FIND_IN_SET and status
        # sqlglot may translate FIND_IN_SET, resulting in different function name
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        # Check that we have a parameter related to the function (could be anonymous_role or similar)
        assert "status" in param_names
        assert normalize_sql(result.parameterized_sql).count(":") == 2
        assert (
            "FIND_IN_SET(role, permissions)" in result.parameterized_sql
            or "FINDINSET(role, permissions)" in result.parameterized_sql
        )

    def test_mysql_date_add_parameterization(self):
        """Test MySQL DATE_ADD function with parameterization improvements."""
        sql = "SELECT * FROM subscriptions WHERE DATE_ADD(start_date, INTERVAL 30 DAY) > '2024-01-01'"
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should parameterize the date comparison with function name
        # sqlglot processes DATE_ADD and finds the column inside
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "dateadd_start_date"  # slugify removes underscore
        assert result.parameters[0].data_type == "datetime"
        assert result.parameters[0].example_value == "2024-01-01"
        assert result.parameters[0].base_column_name == "start_date"
        # sqlglot quotes the INTERVAL value
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM subscriptions WHERE DATE_ADD(start_date, INTERVAL '30' DAY) > :dateadd_start_date"
        )

    def test_mysql_substring_index_parameterization(self):
        """Test MySQL SUBSTRING_INDEX with parameterization improvements."""
        sql = "SELECT * FROM emails WHERE SUBSTRING_INDEX(email, '@', -1) = 'gmail.com' AND active = 1"
        result = parameterize_sql_query(sql, dialect="mysql")

        # Should parameterize both the domain comparison and active flag
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "substringindex_email" in param_names  # slugify removes underscores
        assert "active" in param_names
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM emails WHERE SUBSTRING_INDEX(email, '@', -1) = :substringindex_email AND active = :active"
        )
