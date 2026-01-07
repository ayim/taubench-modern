"""PostgreSQL-specific data frame tests."""

import datetime
import typing

import pytest

if typing.TYPE_CHECKING:
    import testing.postgresql

    from agent_platform.server.storage.postgres import PostgresStorage


@pytest.mark.asyncio
async def test_numeric_nan_handling_with_ibis(
    storage: "PostgresStorage",
    postgres_testing: "testing.postgresql.Postgresql",
) -> None:
    """Test that PostgreSQL NUMERIC columns with NaN are handled via IbisTableAdapter.

    This test verifies that IbisTableAdapter.to_pyarrow() automatically casts
    DECIMAL columns to float64 before PyArrow conversion, preventing the error:
    "The string 'NaN' is not a valid decimal128 number".

    Architecture:
        - create_ibis_connection(): Standard factory for creating Ibis connections
        - AsyncIbisConnection: Async wrapper around Ibis connection
        - IbisTableAdapter: Handles DECIMAL→float64 transformation
    """
    import math
    from urllib.parse import urlparse

    import pyarrow

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration
    from agent_platform.server.kernel.ibis_table_adapter import IbisTableAdapter
    from agent_platform.server.kernel.ibis_utils import create_ibis_connection

    # 1. Create a PostgreSQL table with NaN values in the v2 schema
    table_name = "test_nan_ibis"

    async with storage._transaction() as cur:
        # Drop table if it exists from previous run
        await cur.execute(f"DROP TABLE IF EXISTS v2.{table_name}")

        # Create table with NUMERIC columns in the v2 schema
        await cur.execute(
            f"""
            CREATE TABLE v2.{table_name} (
                date_col DATE,
                normal_value NUMERIC,
                nan_value NUMERIC
            )
            """
        )
        # Insert data including NaN values
        await cur.execute(
            f"""
            INSERT INTO v2.{table_name} VALUES
            ('2024-01-01', 0.5, 'NaN'::NUMERIC),
            ('2024-02-01', 0.75, 'NaN'::NUMERIC),
            ('2024-03-01', 0.5, 0.5),
            ('2024-04-01', 1.0, 'NaN'::NUMERIC)
            """
        )

    # 2. Connect to PostgreSQL via Ibis
    dsn = postgres_testing.url()
    parsed = urlparse(dsn)

    # Create a DataConnection object for the test PostgreSQL instance
    data_connection = DataConnection(
        id="test_postgres_nan",
        name="test_postgres_connection",
        description="Test PostgreSQL connection for NaN handling",
        engine="postgres",
        configuration=PostgresDataConnectionConfiguration(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") if parsed.path else "test",
            user=parsed.username or "postgres",
            password=parsed.password or "",
            schema="v2",  # Use v2 schema where our test tables live
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    ibis_conn = await create_ibis_connection(data_connection)

    try:
        # Get the table via Ibis (create_ibis_connection returns AsyncIbisConnection)
        async_table = await ibis_conn.table(table_name)

        # 3. Test the fix: IbisTableAdapter.to_pyarrow() casts DECIMAL to float64
        # Without this, PyArrow would fail with: "The string 'NaN' is not a valid decimal128 number"
        adapter = IbisTableAdapter(async_table)
        pyarrow_table = await adapter.to_pyarrow()

        # 4. Verify that NUMERIC columns were cast to float64
        assert pyarrow_table.schema.field("normal_value").type == pyarrow.float64()
        assert pyarrow_table.schema.field("nan_value").type == pyarrow.float64()

        # 5. Verify data is correct
        pylist = pyarrow_table.to_pylist()
        assert len(pylist) == 4

        # Row 0: Contains NaN
        assert pylist[0]["date_col"] == datetime.date(2024, 1, 1)
        assert pylist[0]["normal_value"] == 0.5
        assert math.isnan(pylist[0]["nan_value"])

        # Row 1: Contains NaN
        assert pylist[1]["date_col"] == datetime.date(2024, 2, 1)
        assert pylist[1]["normal_value"] == 0.75
        assert math.isnan(pylist[1]["nan_value"])

        # Row 2: Normal value (not NaN)
        assert pylist[2]["date_col"] == datetime.date(2024, 3, 1)
        assert pylist[2]["normal_value"] == 0.5
        assert pylist[2]["nan_value"] == 0.5  # Not NaN

        # Row 3: Contains NaN
        assert pylist[3]["date_col"] == datetime.date(2024, 4, 1)
        assert pylist[3]["normal_value"] == 1.0
        assert math.isnan(pylist[3]["nan_value"])

    finally:
        # Cleanup: drop the test table
        async with storage._transaction() as cur:
            await cur.execute(f"DROP TABLE IF EXISTS v2.{table_name}")
