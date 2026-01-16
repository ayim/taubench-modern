"""Unit tests for SQL parameter extraction and substitution with PostgreSQL dialect."""

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter
from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
    substitute_sql_parameters_safe,
)


class TestExtractParametersFromSQLPostgresDialect:
    """Test cases for extract_parameters_from_sql with PostgreSQL dialect."""

    def test_basic_parameter_extraction(self):
        """Test basic parameter extraction with PostgreSQL."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["user_id"]

    def test_postgres_cast_syntax(self):
        """Test parameter extraction with PostgreSQL cast syntax (::)."""
        sql = (
            "SELECT id::text, created_at::date FROM users WHERE country = :country AND created_at::date = :date_filter"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "date_filter"]

    def test_postgres_json_operators(self):
        """Test parameter extraction with PostgreSQL JSON operators."""
        sql = (
            "SELECT * FROM users WHERE metadata->>'country' = :country "
            "AND metadata->>'region' = :region "
            "AND metadata->'tags'->0 = :first_tag"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "first_tag", "region"]

    def test_postgres_array_operators(self):
        """Test parameter extraction with PostgreSQL array operators."""
        sql = "SELECT * FROM products WHERE tags @> ARRAY[:tag]::text[] AND category = ANY(:categories::text[])"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["categories", "tag"]

    def test_postgres_window_functions(self):
        """Test parameter extraction with PostgreSQL window functions."""
        sql = (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY :partition_col "
            "ORDER BY :order_col) FROM sales WHERE date >= :start_date"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["order_col", "partition_col", "start_date"]

    def test_postgres_cte_with_parameters(self):
        """Test parameter extraction in PostgreSQL CTEs."""
        sql = (
            "WITH filtered_users AS ("
            "  SELECT * FROM users WHERE country = :country"
            ") "
            "SELECT * FROM filtered_users WHERE age > :min_age"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "min_age"]

    def test_postgres_full_text_search(self):
        """Test parameter extraction with PostgreSQL full-text search."""
        sql = (
            "SELECT * FROM documents WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :search_term)"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["search_term"]

    def test_postgres_lateral_join(self):
        """Test parameter extraction with PostgreSQL LATERAL joins."""
        sql = (
            "SELECT u.name, o.total FROM users u "
            "CROSS JOIN LATERAL ("
            "  SELECT SUM(amount) as total FROM orders "
            "  WHERE user_id = u.id AND date >= :start_date"
            ") o WHERE u.country = :country"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "start_date"]

    def test_postgres_array_aggregation(self):
        """Test parameter extraction with PostgreSQL array aggregation."""
        sql = (
            "SELECT user_id, array_agg(order_id ORDER BY date) "
            "FROM orders WHERE date >= :start_date AND date <= :end_date "
            "GROUP BY user_id HAVING COUNT(*) > :min_orders"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["end_date", "min_orders", "start_date"]

    def test_postgres_unnest_arrays(self):
        """Test parameter extraction with PostgreSQL UNNEST."""
        sql = "SELECT * FROM users, UNNEST(tags) as tag WHERE tag = :tag_value AND country = :country"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "tag_value"]

    def test_postgres_double_colon_not_parameter(self):
        """Test that PostgreSQL double colon (::) is not treated as parameter."""
        sql = "SELECT id::text FROM users WHERE id = :user_id"
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["user_id"]

    def test_postgres_complex_query(self):
        """Test parameter extraction in a complex PostgreSQL query."""
        sql = (
            "WITH ranked_orders AS ("
            "  SELECT *, ROW_NUMBER() OVER ("
            "    PARTITION BY user_id ORDER BY date DESC"
            "  ) as rn FROM orders WHERE date >= :start_date"
            ") "
            "SELECT u.name, ro.total FROM users u "
            "INNER JOIN ranked_orders ro ON u.id = ro.user_id "
            "WHERE u.country = :country AND ro.rn <= :top_n "
            "AND ro.total > :min_total"
        )
        result = extract_parameters_from_sql(sql, dialect="postgres")
        assert result == ["country", "min_total", "start_date", "top_n"]


class TestSubstituteSQLParametersSafePostgresDialect:
    """Test cases for substitute_sql_parameters_safe with PostgreSQL dialect."""

    def test_basic_integer_substitution(self):
        """Test basic integer parameter substitution with PostgreSQL."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=123)]
        result = substitute_sql_parameters_safe(sql, {"user_id": 456}, param_defs, "postgres")
        assert result == "SELECT * FROM users WHERE id = 456"

    def test_basic_string_substitution(self):
        """Test basic string parameter substitution with proper quoting."""
        sql = "SELECT * FROM users WHERE country = :country"
        param_defs = [QueryParameter(name="country", data_type="string", description="Country", example_value="US")]
        result = substitute_sql_parameters_safe(sql, {"country": "Germany"}, param_defs, "postgres")
        assert result == "SELECT * FROM users WHERE country = 'Germany'"

    def test_string_with_quotes_escaping(self):
        """Test string parameter with quotes is properly escaped."""
        sql = "SELECT * FROM users WHERE name = :name"
        param_defs = [QueryParameter(name="name", data_type="string", description="Name", example_value="John")]
        result = substitute_sql_parameters_safe(sql, {"name": "O'Brien"}, param_defs, "postgres")
        assert result == "SELECT * FROM users WHERE name = 'O''Brien'"

    def test_float_substitution(self):
        """Test float parameter substitution."""
        sql = "SELECT * FROM products WHERE price >= :min_price"
        param_defs = [QueryParameter(name="min_price", data_type="float", description="Min price", example_value=10.0)]
        result = substitute_sql_parameters_safe(sql, {"min_price": 99.99}, param_defs, "postgres")
        assert result == "SELECT * FROM products WHERE price >= 99.99"

    def test_boolean_substitution(self):
        """Test boolean parameter substitution."""
        sql = "SELECT * FROM users WHERE is_active = :active"
        param_defs = [QueryParameter(name="active", data_type="boolean", description="Active", example_value=True)]
        result = substitute_sql_parameters_safe(sql, {"active": True}, param_defs, "postgres")
        assert result == "SELECT * FROM users WHERE is_active = TRUE"

    def test_datetime_substitution(self):
        """Test datetime parameter substitution."""
        sql = "SELECT * FROM orders WHERE created_at >= :start_date"
        param_defs = [
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            )
        ]
        result = substitute_sql_parameters_safe(sql, {"start_date": "2021-06-15"}, param_defs, "postgres")
        assert result == "SELECT * FROM orders WHERE created_at >= '2021-06-15'"

    def test_multiple_parameters_different_types(self):
        """Test substitution of multiple parameters with different types."""
        sql = "SELECT * FROM orders WHERE user_id = :user_id AND total > :min_total AND date >= :start_date"
        param_defs = [
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1),
            QueryParameter(name="min_total", data_type="float", description="Min total", example_value=50.0),
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"user_id": 123, "min_total": 100.50, "start_date": "2021-01-01"}, param_defs, "postgres"
        )
        assert result == "SELECT * FROM orders WHERE user_id = 123 AND total > 100.5 AND date >= '2021-01-01'"

    def test_same_parameter_multiple_occurrences(self):
        """Test that same parameter appearing multiple times is replaced consistently."""
        sql = "SELECT * FROM users WHERE id = :user_id OR parent_id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        result = substitute_sql_parameters_safe(sql, {"user_id": 456}, param_defs, "postgres")
        assert result == "SELECT * FROM users WHERE id = 456 OR parent_id = 456"

    def test_postgres_cast_syntax_with_substitution(self):
        """Test parameter substitution with PostgreSQL cast syntax (::)."""
        sql = "SELECT id::text FROM users WHERE country = :country AND created_at::date = :date_filter"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(
                name="date_filter", data_type="datetime", description="Date filter", example_value="2020-01-01"
            ),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"country": "Germany", "date_filter": "2021-06-15"}, param_defs, "postgres"
        )
        assert result == (
            "SELECT CAST(id AS TEXT) FROM users WHERE country = 'Germany' AND CAST(created_at AS DATE) = '2021-06-15'"
        )

    def test_postgres_json_operators_with_substitution(self):
        """Test parameter substitution with PostgreSQL JSON operators."""
        sql = "SELECT * FROM users WHERE metadata->>'country' = :country AND metadata->>'region' = :region"
        param_defs = [
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="region", data_type="string", description="Region", example_value="West"),
        ]
        result = substitute_sql_parameters_safe(sql, {"country": "UK", "region": "South"}, param_defs, "postgres")
        assert result == "SELECT * FROM users WHERE metadata ->> 'country' = 'UK' AND metadata ->> 'region' = 'South'"

    def test_postgres_cte_with_substitution(self):
        """Test parameter substitution in PostgreSQL CTEs."""
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
        result = substitute_sql_parameters_safe(sql, {"country": "Germany", "min_age": 25}, param_defs, "postgres")
        assert result == (
            "WITH filtered_users AS (SELECT * FROM users WHERE country = 'Germany') "
            "SELECT * FROM filtered_users WHERE age > 25"
        )

    def test_postgres_array_operators_with_substitution(self):
        """Test parameter substitution with PostgreSQL array operators."""
        sql = "SELECT * FROM products WHERE category = :category AND tags @> ARRAY[:tag]::text[]"
        param_defs = [
            QueryParameter(name="category", data_type="string", description="Category", example_value="Electronics"),
            QueryParameter(name="tag", data_type="string", description="Tag", example_value="sale"),
        ]
        result = substitute_sql_parameters_safe(sql, {"category": "Books", "tag": "featured"}, param_defs, "postgres")
        # sqlglot normalizes :: cast syntax to CAST() function
        assert result == "SELECT * FROM products WHERE category = 'Books' AND tags @> CAST(ARRAY['featured'] AS TEXT[])"

    def test_postgres_window_functions_with_substitution(self):
        """Test parameter substitution with PostgreSQL window functions."""
        sql = (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY department "
            "ORDER BY salary DESC) FROM employees WHERE hire_date >= :start_date"
        )
        param_defs = [
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
        ]
        result = substitute_sql_parameters_safe(sql, {"start_date": "2021-06-15"}, param_defs, "postgres")
        assert result == (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) "
            "FROM employees WHERE hire_date >= '2021-06-15'"
        )

    def test_postgres_full_text_search_with_substitution(self):
        """Test parameter substitution with PostgreSQL full-text search."""
        sql = (
            "SELECT * FROM documents WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :search_term)"
        )
        param_defs = [
            QueryParameter(name="search_term", data_type="string", description="Search term", example_value="test"),
        ]
        result = substitute_sql_parameters_safe(sql, {"search_term": "machine learning"}, param_defs, "postgres")
        assert result == (
            "SELECT * FROM documents WHERE TO_TSVECTOR('english', content) @@ "
            "PLAINTO_TSQUERY('english', 'machine learning')"
        )

    def test_postgres_lateral_join_with_substitution(self):
        """Test parameter substitution with PostgreSQL LATERAL joins."""
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
            sql, {"country": "UK", "start_date": "2021-01-01"}, param_defs, "postgres"
        )
        assert result == (
            "SELECT u.name, o.total FROM users AS u CROSS JOIN LATERAL "
            "(SELECT SUM(amount) AS total FROM orders WHERE user_id = u.id AND date >= '2021-01-01') AS o "
            "WHERE u.country = 'UK'"
        )

    def test_postgres_array_aggregation_with_substitution(self):
        """Test parameter substitution with PostgreSQL array aggregation."""
        sql = (
            "SELECT user_id, array_agg(order_id ORDER BY date) "
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
            sql, {"start_date": "2021-01-01", "end_date": "2021-12-31", "min_orders": 10}, param_defs, "postgres"
        )
        assert result == (
            "SELECT user_id, ARRAY_AGG(order_id ORDER BY date) FROM orders "
            "WHERE date >= '2021-01-01' AND date <= '2021-12-31' "
            "GROUP BY user_id HAVING COUNT(*) > 10"
        )

    def test_postgres_unnest_arrays_with_substitution(self):
        """Test parameter substitution with PostgreSQL UNNEST."""
        sql = "SELECT * FROM users, UNNEST(tags) as tag WHERE tag = :tag_value AND country = :country"
        param_defs = [
            QueryParameter(name="tag_value", data_type="string", description="Tag value", example_value="tech"),
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
        ]
        result = substitute_sql_parameters_safe(
            sql, {"tag_value": "python", "country": "Germany"}, param_defs, "postgres"
        )
        assert result == "SELECT * FROM users, UNNEST(tags) AS tag WHERE tag = 'python' AND country = 'Germany'"

    def test_postgres_double_colon_cast_with_substitution(self):
        """Test parameter substitution with PostgreSQL double colon cast syntax."""
        sql = "SELECT id::text FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        result = substitute_sql_parameters_safe(sql, {"user_id": 456}, param_defs, "postgres")
        # sqlglot normalizes :: to CAST()
        assert result == "SELECT CAST(id AS TEXT) FROM users WHERE id = 456"

    def test_postgres_complex_query_with_substitution(self):
        """Test parameter substitution in a complex PostgreSQL query."""
        sql = (
            "WITH ranked_orders AS ("
            "  SELECT *, ROW_NUMBER() OVER ("
            "    PARTITION BY user_id ORDER BY date DESC"
            "  ) as rn FROM orders WHERE date >= :start_date"
            ") "
            "SELECT u.name, ro.total FROM users u "
            "INNER JOIN ranked_orders ro ON u.id = ro.user_id "
            "WHERE u.country = :country AND ro.rn <= :top_n "
            "AND ro.total > :min_total"
        )
        param_defs = [
            QueryParameter(
                name="start_date", data_type="datetime", description="Start date", example_value="2020-01-01"
            ),
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
            QueryParameter(name="top_n", data_type="integer", description="Top N", example_value=5),
            QueryParameter(name="min_total", data_type="float", description="Min total", example_value=100.0),
        ]
        result = substitute_sql_parameters_safe(
            sql,
            {"start_date": "2021-01-01", "country": "UK", "top_n": 10, "min_total": 250.0},
            param_defs,
            "postgres",
        )
        assert "2021-01-01" in result
        assert "'UK'" in result
        assert "10" in result
        assert "250" in result
