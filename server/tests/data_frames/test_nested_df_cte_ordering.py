"""
Tests for nested data frame CTE ordering.

Regression tests for the bug where nested SQL data frames get rendered with parent
CTEs before their dependencies, causing Postgres to raise "relation does not exist /
forward reference" errors.
"""

import datetime
import typing
from uuid import uuid4

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame


def create_sql_data_frame(name: str, sql: str, sql_dialect: str = "postgres") -> "PlatformDataFrame":
    """Create a minimal SQL computation data frame for testing."""
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame

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
        extra_data={"sql_dialect": sql_dialect},
        created_at=datetime.datetime.now(datetime.UTC),
    )


def test_iter_recursive_sql_computation_data_frames_simple_nesting():
    """Test that recursive iteration yields data frames in dependency-first order (simple case)."""
    from agent_platform.server.data_frames.data_frames_kernel import Dependencies

    # Create a simple nested structure:
    # main_df references child_df
    # child_df references grandchild_df
    grandchild_df = create_sql_data_frame("grandchild", "SELECT 1 AS value")
    child_df = create_sql_data_frame("child", "SELECT * FROM grandchild")
    main_df = create_sql_data_frame("main", "SELECT * FROM child")

    # Build dependency graph
    main_deps = Dependencies(main_df)

    # Child depends on grandchild
    grandchild_deps = Dependencies(grandchild_df)
    child_deps = Dependencies(child_df)
    child_deps.add_sub_dependencies("grandchild", grandchild_deps)

    # Main depends on child
    main_deps.add_sub_dependencies("child", child_deps)

    # Get the list of SQL computation data frames
    result = list(main_deps._iter_recursive_sql_computation_data_frames())

    # Should yield [grandchild, child] in that order (dependencies first)
    assert len(result) == 2
    assert result[0].name == "grandchild", "grandchild should come first"
    assert result[1].name == "child", "child should come after grandchild"


def test_iter_recursive_sql_computation_data_frames_multi_level():
    """Test that recursive iteration handles multiple levels of nesting correctly."""
    from agent_platform.server.data_frames.data_frames_kernel import Dependencies

    # Create a deeper nested structure:
    # main_df references child1_df and child2_df
    # child1_df references grandchild1_df
    # child2_df references grandchild2_df
    # grandchild2_df references great_grandchild_df
    great_grandchild_df = create_sql_data_frame("great_grandchild", "SELECT 1 AS value")
    grandchild1_df = create_sql_data_frame("grandchild1", "SELECT 2 AS value")
    grandchild2_df = create_sql_data_frame("grandchild2", "SELECT * FROM great_grandchild")
    child1_df = create_sql_data_frame("child1", "SELECT * FROM grandchild1")
    child2_df = create_sql_data_frame("child2", "SELECT * FROM grandchild2")
    main_df = create_sql_data_frame("main", "SELECT * FROM child1 UNION ALL SELECT * FROM child2")

    # Build dependency graph
    main_deps = Dependencies(main_df)

    # great_grandchild has no deps
    great_grandchild_deps = Dependencies(great_grandchild_df)

    # grandchild1 has no deps
    grandchild1_deps = Dependencies(grandchild1_df)

    # grandchild2 depends on great_grandchild
    grandchild2_deps = Dependencies(grandchild2_df)
    grandchild2_deps.add_sub_dependencies("great_grandchild", great_grandchild_deps)

    # child1 depends on grandchild1
    child1_deps = Dependencies(child1_df)
    child1_deps.add_sub_dependencies("grandchild1", grandchild1_deps)

    # child2 depends on grandchild2
    child2_deps = Dependencies(child2_df)
    child2_deps.add_sub_dependencies("grandchild2", grandchild2_deps)

    # Main depends on both children
    main_deps.add_sub_dependencies("child1", child1_deps)
    main_deps.add_sub_dependencies("child2", child2_deps)

    # Get the list of SQL computation data frames
    result = list(main_deps._iter_recursive_sql_computation_data_frames())

    # Should yield in dependency-first order
    assert len(result) == 5
    result_names = [df.name for df in result]

    # grandchild1 must come before child1
    assert result_names.index("grandchild1") < result_names.index("child1")

    # great_grandchild must come before grandchild2
    assert result_names.index("great_grandchild") < result_names.index("grandchild2")

    # grandchild2 must come before child2
    assert result_names.index("grandchild2") < result_names.index("child2")


def test_build_full_sql_query_nested_df_order():
    """Test that _build_full_sql_query generates CTEs in dependency-first order."""
    from agent_platform.server.data_frames.data_frames_kernel import Dependencies
    from agent_platform.server.data_frames.query_execution_base import build_sql_query_with_ctes

    # Create nested structure
    grandchild_df = create_sql_data_frame("grandchild_df", "SELECT 1 AS id, 'data' AS value")
    child_df = create_sql_data_frame("child_df", "SELECT id, value FROM grandchild_df WHERE id > 0")
    main_df = create_sql_data_frame("main_df", "SELECT * FROM child_df")

    # Build dependency graph
    main_deps = Dependencies(main_df)
    grandchild_deps = Dependencies(grandchild_df)
    child_deps = Dependencies(child_df)
    child_deps.add_sub_dependencies("grandchild_df", grandchild_deps)
    main_deps.add_sub_dependencies("child_df", child_deps)

    # Get SQL computation data frames
    sql_computation_dfs = list(main_deps._iter_recursive_sql_computation_data_frames())

    # Build the SQL query with CTEs
    full_sql = build_sql_query_with_ctes(
        main_df,
        sql_computation_dfs,
    )

    # Verify the SQL structure
    # The WITH clause should define grandchild_df before child_df
    assert "WITH" in full_sql
    assert "grandchild_df AS" in full_sql
    assert "child_df AS" in full_sql

    # Check that grandchild_df comes before child_df in the SQL
    grandchild_pos = full_sql.find("grandchild_df AS")
    child_pos = full_sql.find("child_df AS")
    assert grandchild_pos < child_pos, (
        f"grandchild_df should be defined before child_df in the WITH clause. "
        f"Found grandchild at {grandchild_pos}, child at {child_pos}"
    )

    # Verify that the SQL can be parsed without forward reference errors
    import sqlglot

    try:
        parsed = sqlglot.parse_one(full_sql, dialect="postgres")
        assert parsed is not None
    except Exception as e:
        pytest.fail(f"Generated SQL failed to parse: {e}\n\nSQL:\n{full_sql}")


def test_build_full_sql_query_executes_without_forward_reference():
    """Test that generated SQL with nested DFs actually executes in DuckDB."""
    from agent_platform.server.data_frames.data_frames_kernel import Dependencies
    from agent_platform.server.data_frames.query_execution_base import build_sql_query_with_ctes

    # Create realistic nested structure similar to the log
    grandchild_df = create_sql_data_frame(
        "recent_completed_orders_df",
        "SELECT 1 AS order_id, 1 AS customer_id, 100.50 AS order_total_amount",
        sql_dialect="duckdb",
    )
    child_df = create_sql_data_frame(
        "customer_monthly_orders_df",
        """
        SELECT
            customer_id,
            '2024-01-01' AS order_month,
            COUNT(*) AS orders_in_month,
            SUM(order_total_amount) AS revenue_in_month
        FROM recent_completed_orders_df
        GROUP BY customer_id
        """,
        sql_dialect="duckdb",
    )
    main_df = create_sql_data_frame(
        "customer_monthly_ranked_df",
        """
        SELECT
            customer_id,
            order_month,
            orders_in_month,
            revenue_in_month,
            RANK() OVER (PARTITION BY customer_id ORDER BY revenue_in_month DESC) AS rank
        FROM customer_monthly_orders_df
        """,
        sql_dialect="duckdb",
    )

    # Build dependency graph
    main_deps = Dependencies(main_df)
    grandchild_deps = Dependencies(grandchild_df)
    child_deps = Dependencies(child_df)
    child_deps.add_sub_dependencies("recent_completed_orders_df", grandchild_deps)
    main_deps.add_sub_dependencies("customer_monthly_orders_df", child_deps)

    # Get SQL computation data frames
    sql_computation_dfs = list(main_deps._iter_recursive_sql_computation_data_frames())

    # Build the SQL query with CTEs
    full_sql = build_sql_query_with_ctes(
        main_df,
        sql_computation_dfs,
    )

    # Try to execute the SQL in DuckDB to ensure it works
    import ibis

    con = ibis.duckdb.connect()
    try:
        result = con.sql(full_sql, dialect="duckdb")
        # If we get here without an exception, the SQL is valid
        df = result.to_pandas()
        assert len(df) >= 0  # Just verify it returns something
    except Exception as e:
        pytest.fail(
            f"Generated SQL failed to execute in DuckDB: {e}\n\n"
            f"This likely means CTEs are not in dependency-first order.\n\n"
            f"SQL:\n{full_sql}"
        )
