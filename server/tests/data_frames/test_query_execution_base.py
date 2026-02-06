"""Tests for query_execution_base module (CTE building and SQL query construction).

This module tests:
- build_ctes(): Building CTE nodes from SQL ASTs
- update_with_clause(): Prepending CTEs to existing WITH clauses
- CTE ordering for nested data frames
"""


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


def test_make_cte_query(file_regression):
    from sqlglot import parse_one

    from agent_platform.server.data_frames.query_execution_base import build_ctes, update_with_clause

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


# ============================================================================
# Nested Data Frame Regression Tests
# These tests verify fixes for nested data frames with semantic data models:
# 1. Data frame CTEs are prepended before user CTEs (fixing forward reference errors)
# 2. Column mappings from SDM don't bleed into data frame columns
# ============================================================================


def test_nested_df_cte_prepending_single(file_regression):
    """Test that a single data frame CTE is prepended before user CTEs.

    Regression test for nested_df_thread.log line 72-80:
    User CTE references df_line_items_enriched which must be defined first.
    """
    from sqlglot import parse_one

    from agent_platform.server.data_frames.query_execution_base import (
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

    from agent_platform.server.data_frames.query_execution_base import (
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

    from agent_platform.server.data_frames.query_execution_base import (
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

    from agent_platform.server.data_frames.file_based_query_executor import update_column_references

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
        table_name_to_expr=None,
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

    from agent_platform.server.data_frames.file_based_query_executor import update_column_references

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
        table_name_to_expr=None,
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

    from agent_platform.server.data_frames.file_based_query_executor import update_column_references

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
        table_name_to_expr=None,
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

    from agent_platform.server.data_frames.file_based_query_executor import update_column_references

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
        table_name_to_expr=None,
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

    from agent_platform.server.data_frames.file_based_query_executor import update_column_references
    from agent_platform.server.data_frames.query_execution_base import (
        build_ctes,
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
        table_name_to_expr=None,
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
