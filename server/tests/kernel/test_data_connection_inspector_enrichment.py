"""Integration tests for DataConnectionInspector partial enrichment."""

import pytest

from agent_platform.core.payloads.semantic_data_model_payloads import (
    ColumnInfo,
    TableInfo,
)
from agent_platform.server.kernel.data_connection_inspector import DataConnectionInspector

pytest_plugins = ["server.tests.storage_fixtures"]


async def _create_sqlite_connection(sqlite_storage, tmp_path):
    import sqlite3
    from uuid import uuid4

    from agent_platform.core.data_connections.data_connections import (
        DataConnection as DbDataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SQLiteDataConnection,
        SQLiteDataConnectionConfiguration,
    )

    db_path = tmp_path / "enrichment_test.sqlite"
    connection = sqlite3.connect(str(db_path))
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    cursor.execute("CREATE TABLE orders (id INTEGER, total INTEGER)")
    cursor.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    cursor.executemany(
        "INSERT INTO orders (id, total) VALUES (?, ?)",
        [(10, 120), (11, 200)],
    )
    connection.commit()
    connection.close()

    connection_id = str(uuid4())
    payload_connection = SQLiteDataConnection(
        name="sqlite-enrichment",
        description="SQLite enrichment test",
        configuration=SQLiteDataConnectionConfiguration(db_file=str(db_path)),
    )
    db_connection = DbDataConnection.from_payload(payload_connection, connection_id=connection_id)
    await sqlite_storage.set_data_connection(db_connection)
    return await sqlite_storage.get_data_connection(connection_id)


async def _run_enrichment(db_data_connection, tables_info):
    from agent_platform.core.payloads.data_connection import DataConnectionsInspectRequest

    request = DataConnectionsInspectRequest(
        tables_to_inspect=None,
        inspect_columns=True,
        n_sample_rows=10,
    )
    async with DataConnectionInspector(db_data_connection, request) as inspector:
        return await inspector.enrich_missing_column_samples(tables_info)


@pytest.mark.asyncio
async def test_enrich_missing_column_samples_with_sqlite(sqlite_storage, tmp_path):
    """Enrich missing column samples using a real SQLite data connection."""
    db_data_connection = await _create_sqlite_connection(sqlite_storage, tmp_path)
    tables_info = [
        TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="name", data_type="unknown", sample_values=None),
            ],
        )
    ]

    result = await _run_enrichment(db_data_connection, tables_info)

    assert result.columns_enriched == 1
    assert result.columns_failed == 0
    assert tables_info[0].columns[0].sample_values is not None


@pytest.mark.asyncio
async def test_no_enrichment_when_samples_present(sqlite_storage, tmp_path):
    """No enrichment work is done when sample_values are already set."""
    db_data_connection = await _create_sqlite_connection(sqlite_storage, tmp_path)
    tables_info = [
        TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="name", data_type="TEXT", sample_values=["Alice"]),
            ],
        )
    ]

    result = await _run_enrichment(db_data_connection, tables_info)

    assert result.columns_enriched == 0
    assert result.columns_failed == 0
    assert result.errors == []


@pytest.mark.asyncio
async def test_enrichment_handles_missing_table(sqlite_storage, tmp_path):
    """Missing tables are reported while other tables still enrich."""
    db_data_connection = await _create_sqlite_connection(sqlite_storage, tmp_path)
    tables_info = [
        TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="name", data_type="unknown", sample_values=None),
            ],
        ),
        TableInfo(
            name="missing_table",
            columns=[
                ColumnInfo(name="ghost", data_type="unknown", sample_values=None),
            ],
        ),
    ]

    result = await _run_enrichment(db_data_connection, tables_info)

    assert result.columns_enriched == 1
    assert result.columns_failed == 1
    assert result.errors


@pytest.mark.asyncio
async def test_enrichment_with_multiple_tables_mixed(sqlite_storage, tmp_path):
    """Mixed tables enrich only missing columns."""
    db_data_connection = await _create_sqlite_connection(sqlite_storage, tmp_path)
    tables_info = [
        TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="name", data_type="unknown", sample_values=None),
                ColumnInfo(name="id", data_type="INTEGER", sample_values=[1]),
            ],
        ),
        TableInfo(
            name="orders",
            columns=[
                ColumnInfo(name="total", data_type="unknown", sample_values=None),
            ],
        ),
    ]

    result = await _run_enrichment(db_data_connection, tables_info)

    assert result.columns_enriched == 2
    assert result.columns_failed == 0
