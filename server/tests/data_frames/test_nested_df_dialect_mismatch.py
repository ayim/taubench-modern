"""
Tests for nested data frame SQL dialect mismatch issues.

Regression tests for the bug where nested data frames with different SQL dialects
cause sqlglot transpilation errors when building the final query.
"""

import datetime
import typing
from uuid import uuid4

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame


def create_sql_data_frame_with_dialect(
    name: str,
    sql: str,
    sql_dialect: str | None = "postgres",
) -> "PlatformDataFrame":
    """Create a SQL computation data frame with a specific dialect."""
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame

    extra_data = PlatformDataFrame.build_extra_data(sql_dialect=sql_dialect)

    return PlatformDataFrame(
        data_frame_id=str(uuid4()),
        user_id="test_user",
        agent_id="test_agent",
        thread_id="test_thread",
        num_rows=0,
        num_columns=0,
        column_headers=[],
        columns={},
        name=name,
        input_id_type="sql_computation",
        computation=sql,
        computation_input_sources={},
        description=f"Test data frame {name}",
        parquet_contents=None,
        extra_data=extra_data,
        created_at=datetime.datetime.now(datetime.UTC),
    )


def test_nested_df_with_jsonb_operators_postgres():
    """Test that JSONB operators work correctly when all data frames use postgres dialect."""
    from agent_platform.server.data_frames.data_frames_kernel import Dependencies

    # All using postgres dialect
    base_df = create_sql_data_frame_with_dialect(
        "base_df",
        'SELECT 1 AS id, \'{"key": "value"}\'::jsonb AS data',
        sql_dialect="postgres",
    )
    child_df = create_sql_data_frame_with_dialect(
        "child_df",
        "SELECT id, data->>'key' AS extracted_value FROM base_df",
        sql_dialect="postgres",
    )

    # Build dependency graph
    main_deps = Dependencies(child_df)
    base_deps = Dependencies(base_df)
    main_deps.add_sub_dependencies("base_df", base_deps)

    # Get SQL computation data frames
    sql_computation_dfs = list(main_deps._iter_recursive_sql_computation_data_frames())

    # Build the full SQL query
    full_sql = main_deps._build_full_sql_query(
        child_df,
        sql_computation_dfs,
        logical_table_name_to_actual_table_name={},
        table_name_to_column_names_to_expr={},
    )

    # Verify the SQL contains JSONB operators and can be parsed
    assert "->>" in full_sql or "json" in full_sql.lower()

    import sqlglot

    parsed = sqlglot.parse_one(full_sql, dialect="postgres")
    assert parsed is not None


def test_nested_df_dialect_mismatch_duckdb_to_postgres():
    """Test dialect mismatch: base created with DuckDB, child created with Postgres.

    With the fix, this should now work: nested DFs are transpiled to the target dialect
    before transformations are applied.
    """
    from agent_platform.server.data_frames.data_frames_kernel import Dependencies

    # Base was created with DuckDB (or None) dialect
    base_df = create_sql_data_frame_with_dialect(
        "base_df",
        "SELECT 1 AS id, 'test value' AS data",
        sql_dialect=None,  # Default/DuckDB
    )

    # Child created with Postgres dialect
    child_df = create_sql_data_frame_with_dialect(
        "child_df",
        "SELECT id, data AS extracted_value FROM base_df",
        sql_dialect="postgres",
    )

    # Build dependency graph
    main_deps = Dependencies(child_df)
    base_deps = Dependencies(base_df)
    main_deps.add_sub_dependencies("base_df", base_deps)

    # Get SQL computation data frames
    sql_computation_dfs = list(main_deps._iter_recursive_sql_computation_data_frames())

    # Build the full SQL query - with the fix, this should transpile correctly
    full_sql = main_deps._build_full_sql_query(
        child_df,
        sql_computation_dfs,
        logical_table_name_to_actual_table_name={},
        table_name_to_column_names_to_expr={},
    )

    # Verify the SQL is valid postgres
    import sqlglot

    parsed = sqlglot.parse_one(full_sql, dialect="postgres")
    assert parsed is not None

    # Try to execute in DuckDB to verify it works
    import ibis

    con = ibis.duckdb.connect()
    result = con.sql(full_sql, dialect="postgres")
    df = result.to_pandas()
    assert len(df) == 1
    assert df.iloc[0]["extracted_value"] == "test value"


def test_nested_df_generates_valid_postgres_jsonb_sql():
    """Test that complex JSONB SQL is correctly generated (parse validation only).

    This verifies that nested data frames with Postgres JSONB operators generate
    syntactically correct SQL, even though we can't execute Postgres-specific
    functions in DuckDB. Simulates the l4_with_adv_json_df pattern from the logs.
    """
    from agent_platform.server.data_frames.data_frames_kernel import Dependencies

    pricing_json = '{"currency": "USD", "base_price": 100, "discounts": [{"percent_off": 10}, {"percent_off": 5}]}'
    base_df = create_sql_data_frame_with_dialect(
        "products_df",
        f"""
        SELECT
            1 AS product_id,
            '{pricing_json}'::jsonb AS pricing_rules_json
        """,
        sql_dialect="postgres",
    )

    child_df = create_sql_data_frame_with_dialect(
        "enriched_df",
        """
        SELECT
            product_id,
            pricing_rules_json->>'currency' AS price_currency,
            (pricing_rules_json->>'base_price')::decimal AS base_price,
            (
                SELECT COALESCE(SUM((d->>'percent_off')::numeric), 0)
                FROM jsonb_array_elements(pricing_rules_json->'discounts') d
            ) AS total_discount_percent
        FROM products_df
        """,
        sql_dialect="postgres",
    )

    # Build dependency graph
    main_deps = Dependencies(child_df)
    base_deps = Dependencies(base_df)
    main_deps.add_sub_dependencies("products_df", base_deps)

    # Get SQL computation data frames
    sql_computation_dfs = list(main_deps._iter_recursive_sql_computation_data_frames())

    # Build the full SQL query
    full_sql = main_deps._build_full_sql_query(
        child_df,
        sql_computation_dfs,
        logical_table_name_to_actual_table_name={},
        table_name_to_column_names_to_expr={},
    )

    # Verify the generated SQL is valid Postgres (parse check only, no execution)
    import sqlglot

    parsed = sqlglot.parse_one(full_sql, dialect="postgres")
    assert parsed is not None

    # Verify JSONB operators are preserved correctly
    assert "jsonb_array_elements" in full_sql.lower(), "JSONB function should be preserved"
    assert "->>" in full_sql, "JSONB text extraction operator should be present"
    assert "pricing_rules_json" in full_sql, "Column name should be present"

    # Verify CTEs are in correct order
    assert full_sql.index("products_df AS") < full_sql.index("SELECT"), (
        "products_df CTE should be defined before the main SELECT"
    )
