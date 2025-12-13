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
            "cte2": parse_one("SELECT user_id, country FROM users WHERE country = 'BR'", read="duckdb"),
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


def test_update_column_table_qualifiers(file_regression):
    """Test that column table qualifiers are updated from logical to physical names.

    This is critical for MySQL and other databases where column table qualifiers
    must match the actual table names in FROM/JOIN clauses.

    Regression test for the issue where:
    - Logical SQL: SELECT Invoices.document_layout FROM Invoices
    - Table name update: SELECT Invoices.document_layout FROM invoice_documents (WRONG)
    - Should be: SELECT invoice_documents.document_layout FROM invoice_documents (CORRECT)
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import (
        update_column_table_qualifiers,
        update_table_names,
    )

    # Test simple qualified column
    input_sql = "SELECT Invoices.document_layout, Invoices.model_type FROM Invoices"
    sql = parse_one(input_sql, read="mysql")
    logical_to_physical = {"Invoices": "invoice_documents"}

    # First update table names in FROM clause
    sql = update_table_names(sql, logical_to_physical)
    # Then update column table qualifiers
    sql = update_column_table_qualifiers(sql, logical_to_physical)

    result = sql.sql(dialect="mysql")

    file_regression.check(f"""
input-sql:
{input_sql}

logical_to_physical:
{logical_to_physical}

final-sql:
{result}
""")


def test_update_column_table_qualifiers_with_joins(file_regression):
    """Test column qualifier updates with JOIN operations."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import (
        update_column_table_qualifiers,
        update_table_names,
    )

    input_sql = "SELECT Orders.order_id, Items.product_id FROM Orders JOIN Items ON Orders.id = Items.order_id"
    sql = parse_one(input_sql, read="mysql")
    logical_to_physical = {"Orders": "sales_orders", "Items": "order_items"}

    sql = update_table_names(sql, logical_to_physical)
    sql = update_column_table_qualifiers(sql, logical_to_physical)

    result = sql.sql(dialect="mysql")

    file_regression.check(f"""
input-sql:
{input_sql}

logical_to_physical:
{logical_to_physical}

final-sql:
{result}
""")


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

    input_sql = "SELECT e.full_name, d.dept_name FROM employees e JOIN departments d ON e.dept_id = d.id"
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
    input_sql = "SELECT * FROM order_line_items oli JOIN product_catalog_basic pcb ON pcb.product_id = oli.product_id"
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
    input_sql = "SELECT e1.full_name, e2.full_name FROM employees e1 JOIN employees e2 ON e1.id = e2.manager_id"
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
    input_sql = "SELECT e.full_name, c.contact_name FROM employees e JOIN contacts c ON e.contact_id = c.id"
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


# ============================================================================
# Nested Data Frame Regression Tests
# These tests verify fixes for nested data frames with semantic data models:
# 1. Data frame CTEs are prepended before user CTEs (fixing forward reference errors)
# 2. Column mappings from SDM don't bleed into data frame columns
# ============================================================================


def _format_nested_df_test_output(
    input_sql: str,
    df_ctes: dict | None,
    data_frame_names: set | None,
    column_mappings: dict | None,
    output_sql: str,
) -> str:
    """Format nested DF test inputs and outputs for file regression testing."""
    import json

    lines = [
        "=" * 80,
        "INPUT SQL:",
        "=" * 80,
        input_sql.strip(),
        "",
    ]

    if df_ctes is not None:
        lines.extend(
            [
                "=" * 80,
                "DATA FRAME CTEs TO PREPEND:",
                "=" * 80,
                json.dumps(df_ctes, indent=2),
                "",
            ]
        )

    if data_frame_names is not None:
        lines.extend(
            [
                "=" * 80,
                "DATA FRAME NAMES (excluded from column mapping):",
                "=" * 80,
                json.dumps(sorted(list(data_frame_names)), indent=2),
                "",
            ]
        )

    if column_mappings is not None:
        lines.extend(
            [
                "=" * 80,
                "SDM COLUMN MAPPINGS:",
                "=" * 80,
                json.dumps(column_mappings, indent=2),
                "",
            ]
        )

    lines.extend(
        [
            "=" * 80,
            "OUTPUT SQL:",
            "=" * 80,
            output_sql.strip(),
        ]
    )

    return "\n".join(lines)


def test_nested_df_cte_prepending_single(file_regression):
    """Test that a single data frame CTE is prepended before user CTEs.

    Regression test for nested_df_thread.log line 72-80:
    User CTE references df_line_items_enriched which must be defined first.
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import (
        build_ctes,
        update_with_clause,
    )

    input_sql = """
        WITH user_aggregation AS (
            SELECT dli.order_id, SUM(dli.line_total) AS total
            FROM df_line_items_enriched dli
            GROUP BY dli.order_id
        )
        SELECT * FROM user_aggregation
        """
    main_sql = parse_one(input_sql, read="postgres")

    df_ctes_dict = {
        "df_line_items_enriched": (
            "SELECT order_id, product_id, line_total FROM order_line_items "
            "JOIN products ON order_line_items.product_id = products.id"
        ),
    }
    df_ctes = build_ctes(name_to_cte_ast={name: parse_one(sql, read="postgres") for name, sql in df_ctes_dict.items()})

    result_sql = update_with_clause(main_sql, df_ctes)
    result_str = result_sql.sql(dialect="postgres", pretty=True)

    # Verify ordering
    df_pos = result_str.find("df_line_items_enriched AS")
    user_pos = result_str.find("user_aggregation AS")
    assert df_pos < user_pos, "Data frame must come before user CTE"

    file_regression.check(_format_nested_df_test_output(input_sql, df_ctes_dict, None, None, result_str))


def test_nested_df_cte_prepending_multiple(file_regression):
    """Test that multiple data frame CTEs are prepended before user CTEs.

    Regression test for nested_df_thread.log line 183-201:
    User query references multiple data frames that must be available.
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import (
        build_ctes,
        update_with_clause,
    )

    input_sql = """
        WITH combined AS (
            SELECT olt.order_id, olt.subtotal, so.order_total
            FROM df_order_line_totals olt
            JOIN df_order_totals so ON olt.order_id = so.order_id
        )
        SELECT * FROM combined WHERE subtotal <> order_total
        """
    main_sql = parse_one(input_sql, read="postgres")

    df_ctes_dict = {
        "df_order_line_totals": ("SELECT order_id, SUM(line_total) AS subtotal FROM lines GROUP BY order_id"),
        "df_order_totals": "SELECT order_id, order_total FROM orders",
    }
    df_ctes = build_ctes(name_to_cte_ast={name: parse_one(sql, read="postgres") for name, sql in df_ctes_dict.items()})

    result_sql = update_with_clause(main_sql, df_ctes)
    result_str = result_sql.sql(dialect="postgres", pretty=True)

    # Verify both DFs come before user CTE
    df1_pos = result_str.find("df_order_line_totals AS")
    df2_pos = result_str.find("df_order_totals AS")
    user_pos = result_str.find("combined AS")
    assert df1_pos < user_pos, "df_order_line_totals must come before user CTE"
    assert df2_pos < user_pos, "df_order_totals must come before user CTE"

    file_regression.check(_format_nested_df_test_output(input_sql, df_ctes_dict, None, None, result_str))


def test_nested_df_cte_deep_nesting(file_regression):
    """Test deeply nested user CTEs that reference data frames.

    Regression test for nested_df_thread.log line 214-223:
    Multi-layer user CTEs all referencing data frames.
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import (
        build_ctes,
        update_with_clause,
    )

    input_sql = """
        WITH layer1 AS (
            SELECT * FROM df_enriched WHERE revenue > 100
        ),
        layer2 AS (
            SELECT l1.*, df_totals.total FROM layer1 l1
            JOIN df_totals ON l1.order_id = df_totals.order_id
        ),
        layer3 AS (
            SELECT l2.*, COUNT(*) OVER (PARTITION BY l2.order_id) AS cnt
            FROM layer2 l2
        )
        SELECT * FROM layer3
        """
    main_sql = parse_one(input_sql, read="postgres")

    df_ctes_dict = {
        "df_enriched": "SELECT order_id, product_id, revenue FROM sales",
        "df_totals": "SELECT order_id, SUM(amount) AS total FROM orders GROUP BY order_id",
    }
    df_ctes = build_ctes(name_to_cte_ast={name: parse_one(sql, read="postgres") for name, sql in df_ctes_dict.items()})

    result_sql = update_with_clause(main_sql, df_ctes)
    result_str = result_sql.sql(dialect="postgres", pretty=True)

    # Verify all DFs come before all user layers
    df1_pos = result_str.find("df_enriched AS")
    df2_pos = result_str.find("df_totals AS")
    l1_pos = result_str.find("layer1 AS")
    l2_pos = result_str.find("layer2 AS")
    l3_pos = result_str.find("layer3 AS")
    assert df1_pos < l1_pos, "df_enriched must come before user layers"
    assert df2_pos < l1_pos, "df_totals must come before user layers"
    assert l1_pos < l2_pos, "layer1 must come before layer2"
    assert l2_pos < l3_pos, "layer2 must come before layer3"

    file_regression.check(_format_nested_df_test_output(input_sql, df_ctes_dict, None, None, result_str))


def test_nested_df_column_mapping_exclusion(file_regression):
    """Test that SDM column mappings are NOT applied to data frame columns.

    Regression test for nested_df_thread.log line 153-159:
    Querying df_line_items_enriched.product_category should not be rewritten
    to 'category' even though SDM has that mapping.
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = """
        SELECT dli.order_id, dli.product_category, SUM(dli.line_total) AS total
        FROM df_line_items_enriched dli
        GROUP BY dli.order_id, dli.product_category
        """
    sql = parse_one(input_sql, read="postgres")

    # SDM has a mapping for product_category that should NOT apply to the data frame
    column_mappings = {
        "product_catalog": {"product_category": "category"},
    }
    data_frame_names = {"df_line_items_enriched"}

    result_sql = update_column_references(
        sql,
        column_mappings,
        logical_table_name_to_actual_table_name=None,
        data_frame_names=data_frame_names,
    )
    result_str = result_sql.sql(dialect="postgres", pretty=True)

    # product_category should remain unchanged
    assert "product_category" in result_str
    assert "dli.category" not in result_str

    file_regression.check(_format_nested_df_test_output(input_sql, None, data_frame_names, column_mappings, result_str))


def test_nested_df_column_mapping_sdm_still_works(file_regression):
    """Test that SDM column mappings ARE still applied to SDM tables.

    Ensures that excluding data frames doesn't break normal SDM rewrites.
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = """
        SELECT pc.product_id, pc.product_category, pc.product_name
        FROM product_catalog pc
        """
    sql = parse_one(input_sql, read="postgres")

    column_mappings = {
        "product_catalog": {
            "product_category": "category",
            "product_name": "name",
        },
    }
    data_frame_names = {"df_line_items_enriched"}  # Different table

    result_sql = update_column_references(
        sql,
        column_mappings,
        logical_table_name_to_actual_table_name=None,
        data_frame_names=data_frame_names,
    )
    result_str = result_sql.sql(dialect="postgres", pretty=True)

    # Mappings SHOULD be applied to SDM table
    assert "category" in result_str or "name" in result_str

    file_regression.check(_format_nested_df_test_output(input_sql, None, data_frame_names, column_mappings, result_str))


def test_nested_df_mixed_df_and_sdm(file_regression):
    """Test column mappings with both data frames and SDM tables in same query.

    This is the most complex real-world scenario: joining a data frame with
    an SDM table where both have similar column names.
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    input_sql = """
        SELECT
            dli.order_id,
            dli.product_category AS df_category,
            pc.product_category AS sdm_category,
            pc.product_name
        FROM df_line_items_enriched dli
        JOIN product_catalog pc ON dli.product_id = pc.product_id
        """
    sql = parse_one(input_sql, read="postgres")

    column_mappings = {
        "product_catalog": {
            "product_category": "category",
            "product_name": "name",
        },
    }
    data_frame_names = {"df_line_items_enriched"}

    result_sql = update_column_references(
        sql,
        column_mappings,
        logical_table_name_to_actual_table_name=None,
        data_frame_names=data_frame_names,
    )
    result_str = result_sql.sql(dialect="postgres", pretty=True)

    # Data frame columns should NOT be rewritten
    assert "dli.product_category" in result_str

    # SDM columns SHOULD be rewritten
    result_lower = result_str.lower()
    assert "pc.category" in result_lower or "category as" in result_lower

    file_regression.check(_format_nested_df_test_output(input_sql, None, data_frame_names, column_mappings, result_str))


def test_nested_df_column_mapping_unqualified_exclusion(file_regression):
    """Test that UNQUALIFIED columns from data frames are NOT rewritten by SDM mappings."""
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import update_column_references

    # Use UNQUALIFIED columns - this is the key difference from the qualified test
    input_sql = """
        SELECT product_category, product_name, line_total
        FROM df_line_items_enriched
        WHERE product_category = 'Electronics'
        ORDER BY line_total DESC
        """
    sql = parse_one(input_sql, read="postgres")

    # SDM has mappings for these column names that should NOT apply to the data frame
    column_mappings = {
        "product_catalog": {
            "product_category": "category",
            "product_name": "name",
        },
    }
    data_frame_names = {"df_line_items_enriched"}

    result_sql = update_column_references(
        sql,
        column_mappings,
        logical_table_name_to_actual_table_name=None,
        data_frame_names=data_frame_names,
    )
    result_str = result_sql.sql(dialect="postgres", pretty=True)

    # CRITICAL: All columns should remain unchanged (not rewritten to 'category' or 'name')
    assert "product_category" in result_str, "Unqualified DF column should not be rewritten"
    assert "product_name" in result_str, "Unqualified DF column should not be rewritten"
    # Make sure they weren't incorrectly rewritten
    assert "category" not in result_str.lower() or "product_category" in result_str.lower()

    file_regression.check(_format_nested_df_test_output(input_sql, None, data_frame_names, column_mappings, result_str))


def test_nested_df_combined_cte_and_column_fixes(file_regression):
    """Test both fixes together: CTE prepending + column mapping exclusion.

    This simulates the full pipeline as it runs in production.
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.sql_manipulation import (
        build_ctes,
        update_column_references,
        update_with_clause,
    )

    input_sql = """
        WITH aggregated AS (
            SELECT
                dli.product_category,
                SUM(dli.line_total) AS category_total
            FROM df_line_items_enriched dli
            GROUP BY dli.product_category
        )
        SELECT
            a.product_category,
            a.category_total,
            pc.product_name
        FROM aggregated a
        JOIN product_catalog pc ON a.product_category = pc.product_category
        """
    main_sql = parse_one(input_sql, read="postgres")

    # Step 1: Prepend data frame CTEs
    df_ctes_dict = {
        "df_line_items_enriched": (
            "SELECT product_id, product_category, line_total FROM order_lines "
            "JOIN products ON order_lines.product_id = products.id"
        ),
    }
    df_ctes = build_ctes(name_to_cte_ast={name: parse_one(sql, read="postgres") for name, sql in df_ctes_dict.items()})
    result_sql = update_with_clause(main_sql, df_ctes)

    # Step 2: Apply column mappings with DF exclusion
    column_mappings = {
        "product_catalog": {
            "product_category": "category",
            "product_name": "name",
        },
    }
    data_frame_names = {"df_line_items_enriched"}

    result_sql = update_column_references(
        result_sql,
        column_mappings,
        logical_table_name_to_actual_table_name=None,
        data_frame_names=data_frame_names,
    )
    result_str = result_sql.sql(dialect="postgres", pretty=True)

    # Verify CTE ordering
    df_pos = result_str.find("df_line_items_enriched AS")
    user_pos = result_str.find("aggregated AS")
    assert df_pos < user_pos, "DF CTE must come first"

    # Verify column mapping exclusion for DF
    assert "dli.product_category" in result_str, "DF columns should not be rewritten"

    file_regression.check(
        _format_nested_df_test_output(input_sql, df_ctes_dict, data_frame_names, column_mappings, result_str)
    )
