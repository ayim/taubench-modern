"""Unit tests for DataConnectionInspector column inspection with multiple schemas."""

from urllib.parse import urlparse

import pytest


@pytest.mark.asyncio
@pytest.mark.postgresql
async def test_column_inspection_with_multiple_schemas(postgres_testing):
    """Test that column inspection correctly handles same-named tables in different schemas.

    This test creates two schemas (schema_a and schema_b) each containing a table
    with the same name but different columns:
    - schema_a.test_table has column foo: text
    - schema_b.test_table has column bar: integer

    The test verifies that the inspector correctly identifies the columns for each
    table based on the schema.
    """
    import psycopg

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
        PostgresDataConnectionConfiguration,
        TableToInspect,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    # Parse connection URL to extract components
    url = postgres_testing.url()
    parsed = urlparse(url)

    # Set up database with two schemas and tables using psycopg
    async with await psycopg.AsyncConnection.connect(url) as conn:
        async with conn.cursor() as cur:
            # Create schemas
            await cur.execute("CREATE SCHEMA IF NOT EXISTS schema_a;")
            await cur.execute("CREATE SCHEMA IF NOT EXISTS schema_b;")

            # Create tables with different columns
            await cur.execute("CREATE TABLE schema_a.test_table (foo TEXT);")
            await cur.execute("CREATE TABLE schema_b.test_table (bar INTEGER);")

            # Insert sample data
            await cur.execute("INSERT INTO schema_a.test_table (foo) VALUES ('hello'), ('world');")
            await cur.execute("INSERT INTO schema_b.test_table (bar) VALUES (1), (2), (3);")

        await conn.commit()

    # Create DataConnection pointing to the test database
    config = PostgresDataConnectionConfiguration(
        host=parsed.hostname or "localhost",
        port=float(parsed.port or 5432),
        database=parsed.path.lstrip("/"),
        user=parsed.username or "postgres",
        password=parsed.password or "",
    )

    data_connection = DataConnection(
        id="test-connection-id",
        name="test-connection",
        description="Test connection for column inspection",
        engine="postgres",
        configuration=config,
    )

    # Create inspect request for both schemas
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[
            TableToInspect(name="test_table", database=None, schema="schema_a"),
            TableToInspect(name="test_table", database=None, schema="schema_b"),
        ],
        inspect_columns=True,
        n_sample_rows=10,
    )

    # Run inspection
    async with DataConnectionInspector(data_connection, request) as inspector:
        response = await inspector.inspect_connection()

    # Verify results
    assert len(response.tables) == 2, f"Expected 2 tables, got {len(response.tables)}"

    # Find table info for each schema
    schema_a_table = None
    schema_b_table = None
    for table in response.tables:
        if table.schema == "schema_a":
            schema_a_table = table
        elif table.schema == "schema_b":
            schema_b_table = table

    # Verify schema_a.test_table
    assert schema_a_table is not None, "schema_a.test_table not found in response"
    assert schema_a_table.name == "test_table"
    assert len(schema_a_table.columns) == 1, f"Expected 1 column for schema_a, got {len(schema_a_table.columns)}"

    foo_column = schema_a_table.columns[0]
    assert foo_column.name == "foo"
    assert "string" in foo_column.data_type.lower() or "text" in foo_column.data_type.lower(), (
        f"Expected string/text type for foo, got {foo_column.data_type}"
    )
    assert foo_column.sample_values is not None, "Expected sample values for foo column"
    assert set(foo_column.sample_values) == {"hello", "world"}, (
        f"Expected sample values {{'hello', 'world'}}, got {foo_column.sample_values}"
    )

    # Verify schema_b.test_table
    assert schema_b_table is not None, "schema_b.test_table not found in response"
    assert schema_b_table.name == "test_table"
    assert len(schema_b_table.columns) == 1, f"Expected 1 column for schema_b, got {len(schema_b_table.columns)}"

    bar_column = schema_b_table.columns[0]
    assert bar_column.name == "bar"
    assert "int" in bar_column.data_type.lower(), f"Expected int type for bar, got {bar_column.data_type}"
    assert bar_column.sample_values is not None, "Expected sample values for bar column"
    assert set(bar_column.sample_values) == {1, 2, 3}, (
        f"Expected sample values {{1, 2, 3}}, got {bar_column.sample_values}"
    )
