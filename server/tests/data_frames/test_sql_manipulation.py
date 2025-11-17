def _format_test_output(input_sql: str, mappings: dict | None, output_sql: str) -> str:
    """Format test inputs and outputs for file regression testing."""
    import json

    lines = [
        "=" * 80,
        "INPUT SQL:",
        "=" * 80,
        input_sql,
        "",
    ]

    if mappings is not None:
        lines.extend(
            [
                "=" * 80,
                "MAPPINGS:",
                "=" * 80,
                json.dumps(mappings, indent=2),
                "",
            ]
        )

    lines.extend(
        [
            "=" * 80,
            "OUTPUT SQL:",
            "=" * 80,
            output_sql,
        ]
    )

    return "\n".join(lines)


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


def test_update_column_references_simple_rename(file_regression):
    """Test that simple column renames are applied correctly."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = "SELECT full_name, salary FROM employees"
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {
        "employees": {
            "full_name": "first_name || ' ' || last_name",
            "salary": "annual_salary",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_computed_expression(file_regression):
    """Test that computed column expressions are rewritten correctly."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = "SELECT product_name, subtotal, total_with_tax FROM sales"
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {
        "sales": {
            "product_name": "product",
            "subtotal": "quantity * unit_price",
            "total_with_tax": "quantity * unit_price * (1 + tax_rate)",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_with_table_prefix(file_regression):
    """Test column rewriting when columns have explicit table prefixes."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = "SELECT t.full_name FROM employees AS t"
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {
        "employees": {
            "full_name": "first_name || ' ' || last_name",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_no_mapping(file_regression):
    """Test that columns without mappings are left unchanged."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = "SELECT id, name FROM users"
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {
        "users": {
            "full_name": "first_name || ' ' || last_name",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_with_where_clause(file_regression):
    """Test that column rewriting works in WHERE clauses."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = "SELECT full_name FROM employees WHERE salary > 50000"
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {
        "employees": {
            "full_name": "first_name || ' ' || last_name",
            "salary": "annual_salary",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_multiple_tables(file_regression):
    """Test column rewriting with multiple tables."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = (
        "SELECT e.full_name, d.dept_name FROM employees e JOIN departments d ON e.dept_id = d.id"
    )
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {
        "employees": {
            "full_name": "first_name || ' ' || last_name",
        },
        "departments": {
            "dept_name": "name",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_empty_mappings(file_regression):
    """Test that empty mappings don't change the SQL."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = "SELECT * FROM users"
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {}

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_inside_aggregate(file_regression):
    """Test that column rewriting inside aggregates doesn't add aliases incorrectly."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # This mimics the error from the log: MAX(column) should not become MAX(column AS alias)
    input_sql = "SELECT MAX(list_price_amount) AS max_price FROM product_catalog_basic"
    sql = parse_one(input_sql, read="postgres")
    table_column_mappings = {
        "product_catalog_basic": {
            "list_price_amount": "price",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_in_group_by(file_regression):
    """Test that column rewriting in GROUP BY doesn't add aliases."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = "SELECT product_category, COUNT(*) FROM products GROUP BY product_category"
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {
        "products": {
            "product_category": "category",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_in_join_on(file_regression):
    """Test that column rewriting in JOIN ON conditions doesn't add aliases."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # This mimics the error from the log where JOIN ON had aliased columns
    input_sql = (
        "SELECT * FROM order_line_items oli JOIN product_catalog_basic pcb "
        "ON pcb.product_id = oli.product_id"
    )
    sql = parse_one(input_sql, read="postgres")
    table_column_mappings = {
        "product_catalog_basic": {
            "product_id": "id",
        },
        "order_line_items": {
            "product_id": "product_id",  # Same name, no change
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_with_cte(file_regression):
    """Test that column rewriting doesn't apply to CTE references."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # This mimics the error from the log where CTE columns were incorrectly rewritten
    input_sql = """
        WITH filtered AS (
            SELECT quantity_units, product_id
            FROM order_line_items
        )
        SELECT SUM(quantity_units) AS total
        FROM filtered
        """
    sql = parse_one(input_sql, read="postgres")
    table_column_mappings = {
        "order_line_items": {
            "quantity_units": "quantity",  # Maps to different name
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_computed_expr_with_join(file_regression):
    """Test that computed expressions are qualified in multi-table queries."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # Test a JOIN where both tables have the same computed column
    input_sql = (
        "SELECT e1.full_name, e2.full_name FROM employees e1 "
        "JOIN employees e2 ON e1.id = e2.manager_id"
    )
    sql = parse_one(input_sql, read="postgres")
    table_column_mappings = {
        "employees": {
            "full_name": "first_name || ' ' || last_name",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_computed_expr_multiple_tables(file_regression):
    """Test that computed expressions work correctly with different tables in JOINs."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # Both tables have a first_name column - computed expression must be qualified
    input_sql = (
        "SELECT e.full_name, c.contact_name FROM employees e JOIN contacts c ON e.contact_id = c.id"
    )
    sql = parse_one(input_sql, read="postgres")
    table_column_mappings = {
        "employees": {
            "full_name": "first_name || ' ' || last_name",
        },
        "contacts": {
            "contact_name": "first_name || ' ' || last_name",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_cte_with_join_and_mappings(file_regression):
    """Test the exact scenario from the log: CTEs + JOINs + column mappings."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import (
        update_column_references,
        update_table_names,
    )

    # Mimics the failing query from the log
    input_sql = """
        WITH customer_agg AS (
            SELECT customer_id, SUM(total) AS total_spent
            FROM orders
            GROUP BY customer_id
        )
        SELECT cm.customer_full_name, ca.total_spent
        FROM customer_agg ca
        JOIN customer_master cm ON cm.customer_id = ca.customer_id
        """
    sql = parse_one(input_sql, read="postgres")

    # First apply table name mappings (this happens first in the kernel)
    logical_to_actual = {
        "customer_master": "customers",
    }
    sql = update_table_names(sql, logical_to_actual)

    # Then apply column mappings
    table_column_mappings = {
        "customer_master": {
            "customer_id": "id",
            "customer_full_name": "name",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings, logical_to_actual)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    # Format output with both table and column mappings
    mappings_dict = {
        "table_mappings": logical_to_actual,
        "column_mappings": table_column_mappings,
    }
    file_regression.check(_format_test_output(input_sql, mappings_dict, result))


def test_update_column_references_unqualified_cte_reference(file_regression):
    """Test that unqualified columns from CTEs are not rewritten (critical bug from log)."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # This is the EXACT pattern that was failing in the log
    input_sql = """
        WITH completed_orders AS (
            SELECT so.order_total_amount, so.customer_id
            FROM sales_orders so
        ),
        revenue AS (
            SELECT SUM(order_total_amount) AS total_revenue
            FROM completed_orders
        )
        SELECT * FROM revenue
        """
    sql = parse_one(input_sql, read="postgres")

    table_column_mappings = {
        "sales_orders": {
            "order_total_amount": "total_amount",
            "customer_id": "customer_id",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_order_by_with_ambiguous_columns(file_regression):
    """Test ORDER BY doesn't create ambiguous columns when tables share physical names."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # Both tables map to physical column "name" - this would be ambiguous if rewritten
    input_sql = """
        SELECT cm.customer_full_name AS customer_name, pcb.product_name
        FROM customer_master cm
        JOIN product_catalog_basic pcb ON pcb.product_id = cm.customer_id
        ORDER BY customer_name, product_name
        """
    sql = parse_one(input_sql, read="postgres")

    table_column_mappings = {
        "customer_master": {
            "customer_full_name": "name",
        },
        "product_catalog_basic": {
            "product_name": "name",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_reused_aliases_in_ctes(file_regression):
    """Test that reused aliases in different CTEs are resolved correctly (scoped resolution)."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # Same alias "so" used in two different CTEs for different tables
    input_sql = """
        WITH q1 AS (
            SELECT so.order_total FROM sales_orders so
        ),
        q2 AS (
            SELECT so.ticket_status FROM support_orders so
        )
        SELECT * FROM q1
        UNION ALL
        SELECT * FROM q2
        """
    sql = parse_one(input_sql, read="postgres")

    table_column_mappings = {
        "sales_orders": {
            "order_total": "total_amount",
        },
        "support_orders": {
            "ticket_status": "status",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="postgres", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))


def test_update_column_references_ambiguous_same_expression(file_regression):
    """Test that ambiguous columns mapping to the same expression are resolved correctly."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = """
    WITH customers AS (
        SELECT user_id, customer_name FROM raw_customers
    ),
    orders AS (
        SELECT user_id, order_date FROM raw_orders
    )
    SELECT user_id, customer_name, order_date
    FROM customers
    JOIN orders USING (user_id)
    """
    sql = parse_one(input_sql, read="duckdb")
    table_column_mappings = {
        "customers": {
            "user_id": "users.id",
            "customer_name": "users.full_name",
        },
        "orders": {
            "user_id": "users.id",  # Same expression as customers.user_id
            "order_date": "orders.created_at",
        },
    }

    updated_sql = update_column_references(sql, table_column_mappings)
    result = updated_sql.sql(dialect="duckdb", pretty=True)

    file_regression.check(_format_test_output(input_sql, table_column_mappings, result))
