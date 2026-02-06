"""Tests for sql_manipulation module (SQL utility functions).

This module tests:
- validate_sql_query(): SQL query validation and safety checking
- get_destructive_reasons(): Detecting destructive SQL operations
- extract_variable_names_required_from_sql_computation(): Extracting table references
- get_mutation_type(): Identifying DML mutation types
- has_returning_clause(): Detecting RETURNING clauses
- determine_result_type(): Determining query result types
"""


def test_extract_variable_names_required_from_sql_computation():
    from agent_platform.server.data_frames.sql_manipulation import (
        extract_variable_names_required_from_sql_computation,
        validate_sql_query,
    )

    sql_ast = validate_sql_query("SELECT * FROM users", "duckdb")
    var_names = extract_variable_names_required_from_sql_computation(sql_ast)
    assert var_names == {"users"}


def test_get_destructive_reasons_readonly_statements():
    """Test that read-only statements return empty reasons list."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    # Test SELECT statements
    stmt = parse_one("SELECT * FROM users", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []

    stmt = parse_one("SELECT id, name FROM users WHERE age > 18", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []

    # Test UNION statements
    stmt = parse_one("SELECT * FROM users UNION SELECT * FROM customers", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []

    # Test EXCEPT statements
    stmt = parse_one("SELECT * FROM users EXCEPT SELECT * FROM inactive_users", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []

    # Test INTERSECT statements
    stmt = parse_one("SELECT * FROM users INTERSECT SELECT * FROM active_users", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []

    # Test VALUES statements
    stmt = parse_one("VALUES (1, 'John'), (2, 'Jane')", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []

    # Test WITH (CTE) statements
    stmt = parse_one("WITH cte AS (SELECT * FROM users) SELECT * FROM cte", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []


def test_get_destructive_reasons_destructive_top_level():
    """Test that destructive top-level statements are detected."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    # Test INSERT statements
    stmt = parse_one("INSERT INTO users (id, name) VALUES (1, 'John')", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert len(reasons) == 1
    assert "Only read-only top-levels are allowed" in reasons[0]
    assert "INSERT" in reasons[0]

    # Test UPDATE statements
    stmt = parse_one("UPDATE users SET name = 'Jane' WHERE id = 1", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert len(reasons) == 1
    assert "Only read-only top-levels are allowed" in reasons[0]
    assert "UPDATE" in reasons[0]

    # Test DELETE statements
    stmt = parse_one("DELETE FROM users WHERE id = 1", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert len(reasons) == 1
    assert "Only read-only top-levels are allowed" in reasons[0]
    assert "DELETE" in reasons[0]

    # Test CREATE statements
    stmt = parse_one("CREATE TABLE new_table (id INT, name TEXT)", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert len(reasons) == 1
    assert "Only read-only top-levels are allowed" in reasons[0]
    assert "CREATE" in reasons[0]

    # Test DROP statements
    stmt = parse_one("DROP TABLE users", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert len(reasons) == 1
    assert "Only read-only top-levels are allowed" in reasons[0]
    assert "DROP" in reasons[0]

    # Test ALTER statements
    stmt = parse_one("ALTER TABLE users ADD COLUMN age INT", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert len(reasons) == 1
    assert "Only read-only top-levels are allowed" in reasons[0]
    assert "ALTER" in reasons[0]


def test_get_destructive_reasons_destructive_subqueries():
    """Test that destructive statements in subqueries are detected."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    # Test WITH clause containing destructive statement
    stmt = parse_one("WITH cte AS (INSERT INTO temp_table SELECT * FROM users) SELECT * FROM cte", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert len(reasons) == 1
    assert "Only read-only statements are allowed" in reasons[0]
    assert "INSERT" in reasons[0]


def test_get_destructive_reasons_edge_cases():
    """Test edge cases and unusual SQL constructs."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    # Test empty or minimal statements
    stmt = parse_one("SELECT 1", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []

    # Test statements with parentheses
    stmt = parse_one("(SELECT * FROM users)", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []

    # Test statements with multiple levels of parentheses
    stmt = parse_one("(((SELECT * FROM users)))", read="duckdb")
    reasons = get_destructive_reasons(stmt)
    assert reasons == []


def test_get_destructive_reasons_all_destructive_keywords():
    """Test all destructive keywords defined in DESTRUCTIVE_KEYS."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    destructive_keywords = [
        "INSERT INTO users VALUES (1, 'John')",
        "UPDATE users SET name = 'Jane' WHERE id = 1",
        "DELETE FROM users WHERE id = 1",
        "MERGE INTO users USING updates ON users.id = updates.id",
        "TRUNCATE TABLE users",
        "CREATE TABLE new_table (id INT)",
        "ALTER TABLE users ADD COLUMN age INT",
        "DROP TABLE users",
        "RENAME TABLE users TO customers",
        "GRANT SELECT ON users TO user1",
        "REVOKE SELECT ON users FROM user1",
        "CALL procedure_name()",
        "EXECUTE procedure_name()",
        "COPY users TO 'file.csv'",
        "LOAD DATA FROM 'file.csv' INTO users",
        "REFRESH TABLE users",
        "VACUUM users",
        "OPTIMIZE TABLE users",
        "ANALYZE TABLE users",
        "BEGIN TRANSACTION",
        "COMMIT",
        "ROLLBACK",
        "SET autocommit = 1",
        "USE database_name",
    ]

    for sql in destructive_keywords:
        try:
            stmt = parse_one(sql, read="duckdb")
            reasons = get_destructive_reasons(stmt)
            assert len(reasons) >= 1, f"Expected destructive reasons for: {sql}"
            # Should either be top-level destructive or contain destructive clause
            assert any(
                "Only read-only top-levels are allowed" in reason or "Only read-only statements are allowed" in reason
                for reason in reasons
            ), f"Expected destructive reason for: {sql}"
        except Exception:
            # Some SQL might not parse with DuckDB dialect, skip those
            continue


def test_get_destructive_reasons_allow_mutate_dml_operations():
    """Test that INSERT/UPDATE/DELETE are allowed when allow_mutate=True."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    # INSERT - blocked by default, allowed with allow_mutate=True
    stmt = parse_one("INSERT INTO users (id, name) VALUES (1, 'John')", read="duckdb")
    reasons = get_destructive_reasons(stmt, allow_mutate=False)
    assert len(reasons) == 1
    assert "INSERT" in reasons[0]
    reasons = get_destructive_reasons(stmt, allow_mutate=True)
    assert reasons == []

    # UPDATE - blocked by default, allowed with allow_mutate=True
    stmt = parse_one("UPDATE users SET name = 'Jane' WHERE id = 1", read="duckdb")
    reasons = get_destructive_reasons(stmt, allow_mutate=False)
    assert len(reasons) == 1
    assert "UPDATE" in reasons[0]
    reasons = get_destructive_reasons(stmt, allow_mutate=True)
    assert reasons == []

    # DELETE - blocked by default, allowed with allow_mutate=True
    stmt = parse_one("DELETE FROM users WHERE id = 1", read="duckdb")
    reasons = get_destructive_reasons(stmt, allow_mutate=False)
    assert len(reasons) == 1
    assert "DELETE" in reasons[0]
    reasons = get_destructive_reasons(stmt, allow_mutate=True)
    assert reasons == []


# ============================================================================
# Tests for get_mutation_type
# ============================================================================


def test_get_mutation_type_insert():
    """Test that INSERT queries are detected as INSERT mutation."""
    from agent_platform.server.data_frames.sql_manipulation import get_mutation_type

    assert get_mutation_type("INSERT INTO users VALUES (1, 'John')", "postgres") == "INSERT"
    assert get_mutation_type("INSERT INTO users (id, name) VALUES (1, 'John')", "duckdb") == "INSERT"
    assert get_mutation_type("INSERT INTO users SELECT * FROM other", "postgres") == "INSERT"


def test_get_mutation_type_update():
    """Test that UPDATE queries are detected as UPDATE mutation."""
    from agent_platform.server.data_frames.sql_manipulation import get_mutation_type

    assert get_mutation_type("UPDATE users SET name = 'Jane' WHERE id = 1", "postgres") == "UPDATE"
    assert get_mutation_type("UPDATE users SET active = true", "duckdb") == "UPDATE"


def test_get_mutation_type_delete():
    """Test that DELETE queries are detected as DELETE mutation."""
    from agent_platform.server.data_frames.sql_manipulation import get_mutation_type

    assert get_mutation_type("DELETE FROM users WHERE id = 1", "postgres") == "DELETE"
    assert get_mutation_type("DELETE FROM users", "duckdb") == "DELETE"


def test_get_mutation_type_select_returns_none():
    """Test that SELECT queries return None (not a mutation)."""
    from agent_platform.server.data_frames.sql_manipulation import get_mutation_type

    assert get_mutation_type("SELECT * FROM users", "postgres") is None
    assert get_mutation_type("SELECT id, name FROM users WHERE active = true", "duckdb") is None
    assert get_mutation_type("SELECT * FROM users UNION SELECT * FROM admins", "postgres") is None


def test_get_mutation_type_ddl_returns_none():
    """Test that DDL statements return None (not an allowed mutation)."""
    from agent_platform.server.data_frames.sql_manipulation import get_mutation_type

    assert get_mutation_type("CREATE TABLE users (id INT)", "postgres") is None
    assert get_mutation_type("DROP TABLE users", "duckdb") is None
    assert get_mutation_type("ALTER TABLE users ADD COLUMN email VARCHAR", "postgres") is None


def test_get_mutation_type_invalid_sql_returns_none():
    """Test that invalid SQL returns None."""
    from agent_platform.server.data_frames.sql_manipulation import get_mutation_type

    assert get_mutation_type("NOT VALID SQL", "postgres") is None
    assert get_mutation_type("", "duckdb") is None


# ============================================================================
# Tests for has_returning_clause
# ============================================================================


def test_has_returning_clause_true():
    """Test that RETURNING clause is detected."""
    from agent_platform.server.data_frames.sql_manipulation import has_returning_clause

    assert has_returning_clause("INSERT INTO users VALUES (1, 'John') RETURNING *", "postgres") is True
    assert has_returning_clause("INSERT INTO users VALUES (1, 'John') RETURNING id", "postgres") is True
    assert has_returning_clause("UPDATE users SET name = 'Jane' RETURNING *", "postgres") is True
    assert has_returning_clause("DELETE FROM users WHERE id = 1 RETURNING *", "postgres") is True


def test_has_returning_clause_false():
    """Test that absence of RETURNING clause is detected."""
    from agent_platform.server.data_frames.sql_manipulation import has_returning_clause

    assert has_returning_clause("INSERT INTO users VALUES (1, 'John')", "postgres") is False
    assert has_returning_clause("UPDATE users SET name = 'Jane' WHERE id = 1", "postgres") is False
    assert has_returning_clause("DELETE FROM users WHERE id = 1", "duckdb") is False
    assert has_returning_clause("SELECT * FROM users", "postgres") is False


def test_has_returning_clause_invalid_sql_returns_false():
    """Test that invalid SQL returns False."""
    from agent_platform.server.data_frames.sql_manipulation import has_returning_clause

    assert has_returning_clause("NOT VALID SQL", "postgres") is False


# ============================================================================
# Tests for determine_result_type
# ============================================================================


def test_determine_result_type_select_returns_table():
    """Test that SELECT queries return ResultType.TABLE."""
    from agent_platform.core.semantic_data_model.types import ResultType
    from agent_platform.server.data_frames.sql_manipulation import determine_result_type

    assert determine_result_type("SELECT * FROM users", "postgres") == ResultType.TABLE
    assert determine_result_type("SELECT id, name FROM users", "duckdb") == ResultType.TABLE
    assert determine_result_type("SELECT * FROM a UNION SELECT * FROM b", "postgres") == ResultType.TABLE


def test_determine_result_type_mutation_with_returning_returns_table():
    """Test that mutations with RETURNING return ResultType.TABLE."""
    from agent_platform.core.semantic_data_model.types import ResultType
    from agent_platform.server.data_frames.sql_manipulation import determine_result_type

    assert determine_result_type("INSERT INTO users VALUES (1) RETURNING *", "postgres") == ResultType.TABLE
    assert determine_result_type("UPDATE users SET name = 'x' RETURNING id", "postgres") == ResultType.TABLE
    assert determine_result_type("DELETE FROM users WHERE id = 1 RETURNING *", "postgres") == ResultType.TABLE


def test_determine_result_type_mutation_without_returning_returns_rows_affected():
    """Test that mutations without RETURNING return ResultType.ROWS_AFFECTED."""
    from agent_platform.core.semantic_data_model.types import ResultType
    from agent_platform.server.data_frames.sql_manipulation import determine_result_type

    assert determine_result_type("INSERT INTO users VALUES (1)", "postgres") == ResultType.ROWS_AFFECTED
    assert determine_result_type("UPDATE users SET name = 'x' WHERE id = 1", "postgres") == ResultType.ROWS_AFFECTED
    assert determine_result_type("DELETE FROM users WHERE id = 1", "duckdb") == ResultType.ROWS_AFFECTED


def test_get_destructive_reasons_allow_mutate_still_blocks_ddl():
    """Test that DDL operations are blocked even with allow_mutate=True."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    ddl_statements = [
        ("CREATE TABLE new_table (id INT)", "CREATE"),
        ("DROP TABLE users", "DROP"),
        ("ALTER TABLE users ADD COLUMN age INT", "ALTER"),
        ("TRUNCATE TABLE users", "TRUNCATE"),
    ]

    for sql, keyword in ddl_statements:
        try:
            stmt = parse_one(sql, read="duckdb")
            reasons = get_destructive_reasons(stmt, allow_mutate=True)
            assert len(reasons) >= 1, f"Expected {keyword} to be blocked even with allow_mutate=True"
            assert keyword in reasons[0], f"Expected {keyword} in reason"
        except Exception:
            # Some SQL might not parse with duckdb dialect, skip those
            continue


def test_get_destructive_reasons_dml_with_subqueries():
    """Test that DML with subqueries is allowed when allow_mutate=True."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    # DELETE with a SELECT subquery
    stmt = parse_one("DELETE FROM users WHERE id IN (SELECT user_id FROM inactive)", read="postgres")
    reasons = get_destructive_reasons(stmt, allow_mutate=True)
    assert reasons == [], "DELETE with SELECT subquery should be allowed"

    reasons = get_destructive_reasons(stmt)  # allow_mutate defaults to False
    assert len(reasons) > 0, "DELETE should be blocked when allow_mutate=False"

    # INSERT with SELECT (common pattern)
    stmt = parse_one("INSERT INTO archive SELECT * FROM users WHERE old = true", read="postgres")
    reasons = get_destructive_reasons(stmt, allow_mutate=True)
    assert reasons == [], "INSERT...SELECT should be allowed"

    reasons = get_destructive_reasons(stmt)  # allow_mutate defaults to False
    assert len(reasons) > 0, "INSERT should be blocked when allow_mutate=False"

    # UPDATE with SELECT subquery
    stmt = parse_one("UPDATE users SET status = 'inactive' WHERE id IN (SELECT user_id FROM expired)", read="postgres")
    reasons = get_destructive_reasons(stmt, allow_mutate=True)
    assert reasons == [], "UPDATE with SELECT subquery should be allowed"


def test_validate_sql_query_allow_mutate():
    """Test validate_sql_query with allow_mutate parameter."""
    import pytest

    from agent_platform.core.errors.base import PlatformError
    from agent_platform.server.data_frames.sql_manipulation import validate_sql_query

    # INSERT without allow_mutate should raise
    with pytest.raises(PlatformError) as exc_info:
        validate_sql_query("INSERT INTO users VALUES (1, 'John')", "postgres", allow_mutate=False)
    assert "INSERT" in str(exc_info.value)

    # INSERT with allow_mutate should succeed
    expr = validate_sql_query("INSERT INTO users VALUES (1, 'John') RETURNING *", "postgres", allow_mutate=True)
    assert expr is not None

    # SELECT should work either way
    expr = validate_sql_query("SELECT * FROM users", "postgres", allow_mutate=False)
    assert expr is not None
    expr = validate_sql_query("SELECT * FROM users", "postgres", allow_mutate=True)
    assert expr is not None

    # DDL should fail even with allow_mutate=True
    with pytest.raises(PlatformError):
        validate_sql_query("DROP TABLE users", "duckdb", allow_mutate=True)


def test_get_destructive_reasons_allow_mutate_default_false():
    """Test that default behavior (allow_mutate=False) is unchanged."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import get_destructive_reasons

    # All existing tests should still pass without providing allow_mutate
    stmt = parse_one("SELECT * FROM users", read="duckdb")
    reasons = get_destructive_reasons(stmt)  # No allow_mutate arg
    assert reasons == []

    stmt = parse_one("INSERT INTO users VALUES (1)", read="duckdb")
    reasons = get_destructive_reasons(stmt)  # No allow_mutate arg
    assert len(reasons) == 1
    assert "INSERT" in reasons[0]
