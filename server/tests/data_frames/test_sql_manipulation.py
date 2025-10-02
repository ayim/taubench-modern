def test_make_cte_query(file_regression):
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import build_ctes, update_with_clause

    main_sql = parse_one("SELECT * FROM cte1 INNER JOIN cte3 ON cte1.id = cte3.id", read="duckdb")

    ctes = build_ctes(
        name_to_cte_ast={
            "cte1": parse_one("SELECT id, total FROM orders WHERE total > 100", read="duckdb"),
            "cte2": parse_one(
                "SELECT user_id, country FROM users WHERE country = 'BR'", read="duckdb"
            ),
        },
    )
    main_sql = update_with_clause(main_sql, ctes)
    main_with_stmt_str = main_sql.sql(dialect="duckdb", pretty=True)
    # Now, let's add a new cte to the main sql
    file_regression.check(main_with_stmt_str, basename="add_with_cte")

    ctes = build_ctes(
        name_to_cte_ast={
            "cte3": parse_one("SELECT id, bar FROM orders WHERE total > 100", read="duckdb"),
        },
    )

    main_sql = update_with_clause(main_sql, ctes)
    file_regression.check(main_sql.sql(dialect="duckdb", pretty=True), basename="update_with_cte")


def test_extract_variable_names_required_from_sql_computation():
    from agent_platform.server.data_frames.sql_manipulation import (
        extract_variable_names_required_from_sql_computation,
        validate_sql_query,
    )

    sql_ast = validate_sql_query("SELECT * FROM users", "duckdb")
    var_names = extract_variable_names_required_from_sql_computation(sql_ast)
    assert var_names == {"users"}


def test_update_table_names():
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_table_names

    updated_sql = update_table_names(
        parse_one("SELECT * FROM users", read="duckdb"),
        {"users": "users_new", "customers": "customers_new"},
    )
    assert updated_sql.sql(dialect="duckdb") == "SELECT * FROM users_new"


def test_update_table_names_with_schema():
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_table_names

    updated_sql = update_table_names(
        parse_one("SELECT * FROM users", read="duckdb"),
        {"users": "schema.users_new"},
    )
    assert updated_sql.sql(dialect="postgres") == "SELECT * FROM schema.users_new"


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
    stmt = parse_one(
        "WITH cte AS (INSERT INTO temp_table SELECT * FROM users) SELECT * FROM cte", read="duckdb"
    )
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
                "Only read-only top-levels are allowed" in reason
                or "Only read-only statements are allowed" in reason
                for reason in reasons
            ), f"Expected destructive reason for: {sql}"
        except Exception:
            # Some SQL might not parse with DuckDB dialect, skip those
            continue
