"""Unit tests for SQL parameter extraction and substitution with PostgreSQL dialect."""

from agent_platform.core.data_frames.semantic_data_model_types import QueryParameter
from agent_platform.server.data_frames.sql_parameter_utils import (
    extract_parameters_from_sql,
    parameterize_sql_query,
    substitute_sql_parameters_safe,
)


def normalize_sql(sql: str) -> str:
    """Normalize SQL by collapsing whitespace for comparison."""
    return " ".join(sql.split())


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
        assert result == (
            "WITH ranked_orders AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY date DESC) AS rn "
            "FROM orders WHERE date >= '2021-01-01') "
            "SELECT u.name, ro.total FROM users AS u "
            "INNER JOIN ranked_orders AS ro ON u.id = ro.user_id "
            "WHERE u.country = 'UK' AND ro.rn <= 10 AND ro.total > 250.0"
        )


class TestParameterizeSQLQueryPostgresDialect:
    """Test cases for parameterize_sql_query with PostgreSQL dialect."""

    def test_basic_integer_parameterization(self):
        """Test parameterizing a query with a single integer literal."""
        sql = "SELECT * FROM users WHERE id = 123"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "id"
        assert result.parameters[0].data_type == "integer"
        assert result.parameters[0].example_value == 123
        assert normalize_sql(result.parameterized_sql) == "SELECT * FROM users WHERE id = :id"

    def test_basic_string_parameterization(self):
        """Test parameterizing a query with a single string literal."""
        sql = "SELECT * FROM users WHERE country = 'USA'"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "country"
        assert result.parameters[0].data_type == "string"
        assert result.parameters[0].example_value == "USA"
        assert normalize_sql(result.parameterized_sql) == "SELECT * FROM users WHERE country = :country"

    def test_basic_float_parameterization(self):
        """Test parameterizing a query with a float literal."""
        sql = "SELECT * FROM products WHERE price >= 99.99"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "price"
        assert result.parameters[0].data_type == "float"
        assert result.parameters[0].example_value == 99.99
        assert normalize_sql(result.parameterized_sql) == "SELECT * FROM products WHERE price >= :price"

    def test_basic_boolean_parameterization(self):
        """Test parameterizing a query with boolean literals."""
        sql = "SELECT * FROM users WHERE is_active = TRUE AND is_deleted = FALSE"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        # Check we have both parameters with intelligent names
        param_names = {p.name for p in result.parameters}
        assert "is_active" in param_names
        assert "is_deleted" in param_names
        assert result.parameters[0].data_type == "boolean"
        assert result.parameters[1].data_type == "boolean"
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM users WHERE is_active = :is_active AND is_deleted = :is_deleted"
        )

    def test_basic_datetime_parameterization(self):
        """Test parameterizing a query with datetime literals."""
        sql = "SELECT * FROM orders WHERE created_at >= '2021-01-01' AND updated_at <= '2021-12-31 23:59:59'"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        # Check we have both parameters with intelligent names
        param_names = {p.name for p in result.parameters}
        assert "created_at" in param_names
        assert "updated_at" in param_names
        # Both should be detected as datetime type
        assert all(p.data_type == "datetime" for p in result.parameters)
        # Verify example values
        values_by_name = {p.name: p.example_value for p in result.parameters}
        assert values_by_name["created_at"] == "2021-01-01"
        assert values_by_name["updated_at"] == "2021-12-31 23:59:59"
        assert (
            normalize_sql(result.parameterized_sql)
            == "SELECT * FROM orders WHERE created_at >= :created_at AND updated_at <= :updated_at"
        )

    def test_multiple_mixed_types(self):
        """Test parameterizing a query with multiple literals of different types."""
        sql = "SELECT * FROM orders WHERE user_id = 456 AND total > 100.50 AND status = 'active'"
        result = parameterize_sql_query(sql, dialect="postgres")
        # Check that all three parameters were extracted
        assert len(result.parameters) == 3

        # Verify we have one of each type
        param_types = {p.data_type for p in result.parameters}
        assert "integer" in param_types
        assert "float" in param_types
        assert "string" in param_types

        # Verify the values (regardless of parameter name/order)
        values_by_type = {p.data_type: p.example_value for p in result.parameters}
        assert values_by_type["integer"] == 456
        assert values_by_type["float"] == 100.5
        assert values_by_type["string"] == "active"

        # Check intelligent naming - should use column names
        param_names = {p.name for p in result.parameters}
        assert "user_id" in param_names
        assert "total" in param_names
        assert "status" in param_names

        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM orders WHERE user_id = :user_id AND total > :total AND status = :status"
        )

    def test_string_with_special_characters(self):
        """Test parameterizing strings with special characters."""
        sql = "SELECT * FROM users WHERE name = 'O''Brien'"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "name"
        assert result.parameters[0].data_type == "string"
        # sqlglot normalizes the escaped quote
        assert result.parameters[0].example_value is not None
        assert "Brien" in str(result.parameters[0].example_value)
        assert normalize_sql(result.parameterized_sql) == "SELECT * FROM users WHERE name = :name"

    def test_parameter_deduplication_same_column(self):
        """Test that same value in SAME column context creates only ONE parameter."""
        sql = "SELECT * FROM users WHERE user_id = 123 OR user_id = 123"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should have only ONE parameter since same column and same value
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "user_id"
        assert result.parameters[0].example_value == 123
        assert result.parameters[0].data_type == "integer"

        # Verify user_id placeholder appears twice in SQL (reused)
        assert result.parameterized_sql.count(":user_id") == 2

    def test_parameter_deduplication_different_columns(self):
        """Test that same value in DIFFERENT columns creates SEPARATE parameters."""
        sql = "SELECT * FROM orders WHERE user_id = 123 OR parent_id = 123"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should have TWO parameters - one for each column
        # This is the CORRECT behavior that fixes the bug where
        # "position BETWEEN 1 AND 10" and "points >= 1" incorrectly shared parameters
        assert len(result.parameters) == 2
        assert all(p.example_value == 123 for p in result.parameters)
        assert all(p.data_type == "integer" for p in result.parameters)

        # Each column gets its own parameter
        param_names = {p.name for p in result.parameters}
        assert "user_id" in param_names
        assert "parent_id" in param_names

        # Each parameter used once
        assert ":user_id" in result.parameterized_sql
        assert ":parent_id" in result.parameterized_sql

    def test_parameter_no_deduplication_different_columns_same_value(self):
        """Test comprehensive example: same value across different columns."""
        # Real-world scenario that exposed the bug
        sql = "SELECT * FROM products WHERE min_price = 100 AND max_price = 100 AND discount = 100"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should have THREE parameters - one for each different column
        assert len(result.parameters) == 3
        assert all(p.example_value == 100 for p in result.parameters)
        assert all(p.data_type == "integer" for p in result.parameters)

        # All three columns get their own parameter names
        param_names = {p.name for p in result.parameters}
        assert "min_price" in param_names
        assert "max_price" in param_names
        assert "discount" in param_names

        # Each parameter is used once
        assert result.parameterized_sql.count(":min_price") == 1
        assert result.parameterized_sql.count(":max_price") == 1
        assert result.parameterized_sql.count(":discount") == 1

    def test_function_arguments_not_parameterized(self):
        """Test that function arguments are not parameterized."""
        sql = "SELECT ROUND(price, 2) FROM products WHERE id = 124"
        result = parameterize_sql_query(sql, dialect="postgres")
        # Should only parameterize the id comparison, not the ROUND precision
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "id"
        assert result.parameters[0].example_value == 124
        # The '2' should remain in the SQL unchanged
        assert "ROUND(price, 2)" in result.parameterized_sql
        # The id should be parameterized
        assert ":id" in result.parameterized_sql

    def test_empty_query_no_literals(self):
        """Test parameterizing a query with no literals."""
        sql = "SELECT * FROM users WHERE id = user_id"
        result = parameterize_sql_query(sql, dialect="postgres")
        # No literals to extract, no parameters should be added
        assert ":" not in result.parameterized_sql  # No placeholders
        assert "FROM users" in result.parameterized_sql
        assert len(result.parameters) == 0

    def test_postgres_cte_with_literals(self):
        """Test parameterizing PostgreSQL CTEs with literals."""
        sql = (
            "WITH filtered_users AS ("
            "  SELECT * FROM users WHERE country = 'USA'"
            ") "
            "SELECT * FROM filtered_users WHERE age > 18"
        )
        result = parameterize_sql_query(sql, dialect="postgres")
        # Check that both parameters were extracted
        assert len(result.parameters) == 2

        # Verify we have one of each type
        param_types = {p.data_type for p in result.parameters}
        assert "string" in param_types
        assert "integer" in param_types

        # Verify the values (regardless of parameter name/order)
        values_by_type = {p.data_type: p.example_value for p in result.parameters}
        assert values_by_type["string"] == "USA"
        assert values_by_type["integer"] == 18

        # Check intelligent naming
        param_names = {p.name for p in result.parameters}
        assert "country" in param_names
        assert "age" in param_names

        # Verify full SQL
        assert normalize_sql(result.parameterized_sql) == (
            "WITH filtered_users AS ( SELECT * FROM users WHERE country = :country ) "
            "SELECT * FROM filtered_users WHERE age > :age"
        )

    def test_postgres_window_functions_with_literals(self):
        """Test parameterizing PostgreSQL window functions with literals."""
        sql = (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) "
            "FROM employees WHERE hire_date >= '2021-01-01'"
        )
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "hire_date"
        assert result.parameters[0].data_type == "datetime"
        assert result.parameters[0].example_value == "2021-01-01"
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT *, ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) "
            "FROM employees WHERE hire_date >= :hire_date"
        )

    def test_postgres_array_operators_with_literals(self):
        """Test parameterizing PostgreSQL array operators with literals."""
        sql = "SELECT * FROM products WHERE category = 'Electronics' AND price > 100"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        # Verify intelligent naming
        param_names = {p.name for p in result.parameters}
        assert "category" in param_names
        assert "price" in param_names
        # Verify types and values
        values_by_name = {p.name: p.example_value for p in result.parameters}
        assert values_by_name["category"] == "Electronics"
        assert values_by_name["price"] == 100

    def test_postgres_in_clause_with_literals(self):
        """Test parameterizing IN clause with multiple literals."""
        sql = "SELECT * FROM users WHERE status IN ('active', 'pending')"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        # IN clause should use the column name for the parameter
        assert all(p.data_type == "string" for p in result.parameters)
        # Both parameters should have status-based names
        param_names_str = " ".join(sorted([p.name for p in result.parameters]))
        assert "status" in param_names_str
        assert normalize_sql(result.parameterized_sql) == "SELECT * FROM users WHERE status IN (:status, :status_1)"

    def test_postgres_between_clause_with_literals(self):
        """Test parameterizing BETWEEN clause with literals."""
        sql = "SELECT * FROM products WHERE price BETWEEN 10.00 AND 100.00"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        assert all(p.data_type == "float" for p in result.parameters)
        # BETWEEN should use column name for parameters
        param_names_str = " ".join(sorted([p.name for p in result.parameters]))
        assert "price" in param_names_str
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM products WHERE price BETWEEN :price AND :price_1"
        )

    def test_postgres_case_statement_with_literals(self):
        """Test parameterizing CASE statement with literals."""
        sql = (
            "SELECT CASE "
            "WHEN age < 18 THEN 'minor' "
            "WHEN age >= 65 THEN 'senior' "
            "ELSE 'adult' "
            "END as age_group FROM users"
        )
        result = parameterize_sql_query(sql, dialect="postgres")
        # Should only extract comparison values (18, 65), not THEN values
        # THEN/ELSE literals don't have column context, so they're skipped
        assert len(result.parameters) == 2
        # Verify the age comparisons were parameterized
        param_names = {p.name for p in result.parameters}
        assert "age" in param_names or "age_1" in param_names
        # Verify THEN/ELSE literals remain unchanged
        assert "'minor'" in result.parameterized_sql
        assert "'senior'" in result.parameterized_sql
        assert "'adult'" in result.parameterized_sql
        # Verify we only extracted integer comparisons
        data_types = [p.data_type for p in result.parameters]
        assert data_types.count("integer") == 2  # 18, 65

    def test_postgres_join_with_literals(self):
        """Test parameterizing JOIN queries with literals."""
        sql = (
            "SELECT u.name, o.total FROM users u "
            "INNER JOIN orders o ON u.id = o.user_id "
            "WHERE u.country = 'USA' AND o.total > 100.0"
        )
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        # Check intelligent naming
        param_names = {p.name for p in result.parameters}
        assert "country" in param_names
        assert "total" in param_names
        # Check values
        values_by_name = {p.name: p.example_value for p in result.parameters}
        assert values_by_name["country"] == "USA"
        assert values_by_name["total"] == 100.0

    def test_postgres_aggregate_functions_with_literals(self):
        """Test parameterizing aggregate functions with literals."""
        sql = (
            "SELECT user_id, COUNT(*) as order_count "
            "FROM orders WHERE total > 50.0 "
            "GROUP BY user_id HAVING COUNT(*) > 5"
        )
        result = parameterize_sql_query(sql, dialect="postgres")
        # Both WHERE and HAVING literals should be parameterized
        # HAVING COUNT(*) > 5 now gets parameterized with function name
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "total" in param_names
        assert "count" in param_names
        # Verify values
        param_by_name = {p.name: p for p in result.parameters}
        assert param_by_name["total"].example_value == 50.0
        assert param_by_name["count"].example_value == 5
        # Verify full SQL with both parameterized
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT user_id, COUNT(*) AS order_count FROM orders WHERE total > :total "
            "GROUP BY user_id HAVING COUNT(*) > :count"
        )

    def test_postgres_subquery_with_literals(self):
        """Test parameterizing subqueries with literals."""
        sql = "SELECT * FROM users WHERE id IN (  SELECT user_id FROM orders WHERE total > 100.0) AND country = 'USA'"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        # Verify full SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM users WHERE id IN ( SELECT user_id FROM orders WHERE total > :total ) AND country = :country"
        )

    def test_postgres_union_with_literals(self):
        """Test parameterizing UNION queries with literals."""
        sql = "SELECT name FROM users WHERE age > 18 UNION SELECT name FROM admins WHERE status = 'active'"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        # Check types
        types_by_value = {str(p.example_value): p.data_type for p in result.parameters}
        assert types_by_value["18"] == "integer"
        assert types_by_value["active"] == "string"

    def test_postgres_like_pattern_with_literals(self):
        """Test parameterizing LIKE patterns with literals."""
        sql = "SELECT * FROM users WHERE name LIKE 'John%' OR email LIKE '%@example.com'"
        result = parameterize_sql_query(sql, dialect="postgres")
        assert len(result.parameters) == 2
        assert all(p.data_type == "string" for p in result.parameters)
        # Check placeholders exist
        param_names = {p.name for p in result.parameters}
        assert "name" in param_names or "email" in param_names
        # Verify full SQL
        assert (
            normalize_sql(result.parameterized_sql) == "SELECT * FROM users WHERE name LIKE :name OR email LIKE :email"
        )

    def test_postgres_null_handling(self):
        """Test that NULL is not parameterized (it's not a literal value)."""
        sql = "SELECT * FROM users WHERE deleted_at IS NULL AND country = 'USA'"
        result = parameterize_sql_query(sql, dialect="postgres")
        # NULL should not be parameterized, only 'USA'
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "country"
        assert result.parameters[0].example_value == "USA"
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM users WHERE deleted_at IS NULL AND country = :country"
        )

    def test_postgres_complex_query_with_multiple_literals(self):
        """Test parameterizing a complex query with many literals."""
        sql = (
            "WITH ranked_orders AS ("
            "  SELECT *, ROW_NUMBER() OVER ("
            "    PARTITION BY user_id ORDER BY date DESC"
            "  ) as rn FROM orders WHERE date >= '2021-01-01' AND total > 50.0"
            ") "
            "SELECT u.name, ro.total FROM users u "
            "INNER JOIN ranked_orders ro ON u.id = ro.user_id "
            "WHERE u.country = 'USA' AND ro.rn <= 10 AND u.age >= 18"
        )
        result = parameterize_sql_query(sql, dialect="postgres")
        # Should extract: '2021-01-01' (datetime), 50.0 (float),
        # 'USA' (string), 10 (int), 18 (int)
        assert len(result.parameters) == 5
        # Verify parameter types
        param_types = {p.data_type for p in result.parameters}
        assert "datetime" in param_types
        assert "string" in param_types
        assert "float" in param_types
        assert "integer" in param_types

    def test_postgres_limit_offset_with_literals(self):
        """Test parameterizing LIMIT and OFFSET clauses."""
        sql = "SELECT * FROM users WHERE age > 18 LIMIT 10 OFFSET 20"
        result = parameterize_sql_query(sql, dialect="postgres")
        # Only the WHERE clause literal should be parameterized
        # LIMIT/OFFSET literals don't have column context (structural values)
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "age"
        assert result.parameters[0].example_value == 18
        assert result.parameters[0].data_type == "integer"
        # Verify full SQL with LIMIT and OFFSET unchanged
        assert normalize_sql(result.parameterized_sql) == "SELECT * FROM users WHERE age > :age LIMIT 10 OFFSET 20"

    def test_parameter_base_column_names_present(self):
        """Test that all extracted parameters have base column names."""
        sql = "SELECT * FROM users WHERE id = 123 AND name = 'John'"
        result = parameterize_sql_query(sql, dialect="postgres")
        for param in result.parameters:
            assert param.base_column_name is not None
            assert len(param.base_column_name) > 0

    def test_roundtrip_parameterize_then_substitute(self):
        """Test that parameterizing and then substituting works correctly."""
        original_sql = "SELECT * FROM users WHERE id = 123 AND name = 'John' AND active = TRUE"

        # Step 1: Parameterize
        result = parameterize_sql_query(original_sql, dialect="postgres")

        # Step 2: Build param_values from extracted parameters
        # example_value is already the correct type, so use it directly
        # Filter out None values (all parameters should have example values)
        param_values = {p.name: p.example_value for p in result.parameters if p.example_value is not None}

        # Step 3: Convert ExtractedParameters to QueryParameters for substitution
        query_parameters = [
            QueryParameter(
                name=p.name,
                data_type=p.data_type,
                description="Test parameter",
                example_value=p.example_value,
            )
            for p in result.parameters
        ]

        # Step 4: Substitute back
        substituted_sql = substitute_sql_parameters_safe(
            result.parameterized_sql, param_values, query_parameters, "postgres"
        )

        # The substituted SQL should be functionally equivalent to original
        assert "123" in substituted_sql
        assert "'John'" in substituted_sql or '"John"' in substituted_sql
        assert "TRUE" in substituted_sql or "true" in substituted_sql.lower()

    def test_overlapping_parameter_names_comprehensive(self):
        """Test parameters from columns with overlapping names are handled correctly."""
        sql = """
            SELECT * FROM orders
            WHERE user_id = 123
              AND user_id_secondary = 456
              AND date = '2021-01-01'
              AND datetime = '2021-01-01 10:00:00'
              AND status = 'active'
              AND status_code = 200
        """
        result = parameterize_sql_query(sql, "postgres")

        # Check that all parameters are extracted with distinct names
        param_names = {p.name for p in result.parameters}
        assert param_names == {"user_id", "user_id_secondary", "date", "datetime", "status", "status_code"}
        assert len(result.parameters) == 6

        # Check full parameterized SQL with proper placeholder format
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM orders WHERE user_id = :user_id AND user_id_secondary = :user_id_secondary "
            "AND date = :date AND datetime = :datetime AND status = :status AND status_code = :status_code"
        )

    def test_aggregate_count_star_parameterization(self):
        """Test HAVING count(*) > 10 gets parameterized with function name."""
        sql = "SELECT country, count(*) as customer_count FROM customers GROUP BY country HAVING count(*) > 10"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should extract the 10 with parameter name "count"
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "count"
        assert result.parameters[0].example_value == 10
        assert result.parameters[0].data_type == "integer"
        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT country, COUNT(*) AS customer_count FROM customers GROUP BY country HAVING COUNT(*) > :count"
        )

    def test_aggregate_sum_with_column_parameterization(self):
        """Test HAVING sum(revenue) > 1000 gets parameterized with combined name."""
        sql = "SELECT country, sum(revenue) FROM sales GROUP BY country HAVING sum(revenue) > 1000"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should extract the 1000 with parameter name "sum_revenue"
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "sum_revenue"
        assert result.parameters[0].example_value == 1000
        assert result.parameters[0].data_type == "integer"
        assert result.parameters[0].base_column_name == "revenue"
        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT country, SUM(revenue) FROM sales GROUP BY country HAVING SUM(revenue) > :sum_revenue"
        )

    def test_aggregate_avg_with_column_parameterization(self):
        """Test HAVING avg(price) < 50.0 gets parameterized with combined name."""
        sql = "SELECT category, avg(price) FROM products GROUP BY category HAVING avg(price) < 50.0"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should extract the 50.0 with parameter name "avg_price"
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "avg_price"
        assert result.parameters[0].example_value == 50.0
        assert result.parameters[0].data_type == "float"
        assert result.parameters[0].base_column_name == "price"
        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT category, AVG(price) FROM products GROUP BY category HAVING AVG(price) < :avg_price"
        )

    def test_scalar_function_round_parameterization(self):
        """Test WHERE ROUND(price) > 100 gets parameterized with function name."""
        sql = "SELECT * FROM products WHERE ROUND(price) > 100"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should extract the 100 with parameter name "round_price"
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "round_price"
        assert result.parameters[0].example_value == 100
        assert result.parameters[0].data_type == "integer"
        assert result.parameters[0].base_column_name == "price"
        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == ("SELECT * FROM products WHERE ROUND(price) > :round_price")

    def test_scalar_function_upper_parameterization(self):
        """Test WHERE UPPER(country) = 'USA' gets parameterized with function name."""
        sql = "SELECT * FROM customers WHERE UPPER(country) = 'USA'"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should extract 'USA' with parameter name "upper_country"
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "upper_country"
        assert result.parameters[0].example_value == "USA"
        assert result.parameters[0].data_type == "string"
        assert result.parameters[0].base_column_name == "country"
        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT * FROM customers WHERE UPPER(country) = :upper_country"
        )

    def test_arithmetic_expression_parameterization(self):
        """Test WHERE price * 1.1 > 100 gets parameterized with column name."""
        sql = "SELECT * FROM products WHERE price * 1.1 > 100"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should extract 100 with parameter name "price" (from the column in expression)
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "price"
        assert result.parameters[0].example_value == 100
        assert result.parameters[0].data_type == "integer"
        assert result.parameters[0].base_column_name == "price"
        # Verify full parameterized SQL - 1.1 should NOT be parameterized
        assert normalize_sql(result.parameterized_sql) == ("SELECT * FROM products WHERE price * 1.1 > :price")

    def test_multiple_aggregates_same_function(self):
        """Test HAVING with multiple count(*) comparisons."""
        sql = "SELECT country, count(*) FROM customers GROUP BY country HAVING count(*) > 10 AND count(*) < 100"
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should extract both values with distinct names
        assert len(result.parameters) == 2
        param_names = {p.name for p in result.parameters}
        assert "count" in param_names
        assert "count_1" in param_names
        # Check values
        values = {p.example_value for p in result.parameters}
        assert values == {10, 100}
        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT country, COUNT(*) FROM customers GROUP BY country HAVING COUNT(*) > :count AND COUNT(*) < :count_1"
        )

    def test_mixed_aggregates_parameterization(self):
        """Test HAVING with different aggregate functions."""
        sql = """
            SELECT country, sum(revenue), avg(price), count(*)
            FROM sales
            GROUP BY country
            HAVING sum(revenue) > 1000 AND avg(price) < 50.0 AND count(*) > 10
        """
        result = parameterize_sql_query(sql, dialect="postgres")

        # Should extract three parameters with distinct names
        assert len(result.parameters) == 3
        param_names = {p.name for p in result.parameters}
        assert "sum_revenue" in param_names
        assert "avg_price" in param_names
        assert "count" in param_names
        # Verify full parameterized SQL
        assert normalize_sql(result.parameterized_sql) == (
            "SELECT country, SUM(revenue), AVG(price), COUNT(*) FROM sales GROUP BY country "
            "HAVING SUM(revenue) > :sum_revenue AND AVG(price) < :avg_price AND COUNT(*) > :count"
        )

    def test_nested_function_parameterization(self):
        """Test WHERE with nested functions like ROUND(price * 0.9)."""
        sql = "SELECT * FROM products WHERE ROUND(price * 0.9) < 50"
        result = parameterize_sql_query(sql, dialect="postgres")

        # When column is nested in arithmetic inside function, we get function name only
        # because iter_expressions() on the Func doesn't find the deeply nested Column
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "round"
        assert result.parameters[0].example_value == 50
        assert result.parameters[0].base_column_name is None  # Column not directly found
        # Verify full parameterized SQL - 0.9 should NOT be parameterized
        assert normalize_sql(result.parameterized_sql) == ("SELECT * FROM products WHERE ROUND(price * 0.9) < :round")
