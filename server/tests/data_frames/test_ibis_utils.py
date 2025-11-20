import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from agent_platform.server.kernel.ibis_utils import create_ibis_connection


@pytest.mark.asyncio
async def test_create_ibis_connection_sqlite(tmp_path: Path):
    """Test creating an ibis connection to SQLite and performing SQL operations."""
    import asyncio

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import SQLiteDataConnectionConfiguration
    from agent_platform.server.kernel.ibis_utils import IbisDbCallNotInWorkerThreadError

    # Create a SQLite database with some tables and data
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    cursor.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)")

    # Insert sample data
    cursor.execute("INSERT INTO users (name, age) VALUES ('Alice', 30)")
    cursor.execute("INSERT INTO users (name, age) VALUES ('Bob', 25)")
    cursor.execute("INSERT INTO users (name, age) VALUES ('Charlie', 35)")

    cursor.execute("INSERT INTO orders (user_id, amount) VALUES (1, 100.50)")
    cursor.execute("INSERT INTO orders (user_id, amount) VALUES (1, 200.75)")
    cursor.execute("INSERT INTO orders (user_id, amount) VALUES (2, 150.00)")

    conn.commit()
    conn.close()

    # Create a DataConnection object
    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_sqlite_connection",
        description="Test SQLite connection",
        engine="sqlite",
        configuration=SQLiteDataConnectionConfiguration(db_file=str(db_file)),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Create ibis connection
    con = await create_ibis_connection(data_connection)

    # Perform SQL operations with ibis
    # 1. Simple SELECT query
    users_table = con.sql("SELECT * FROM users")  # no need for threads

    with pytest.raises(IbisDbCallNotInWorkerThreadError):
        # Make sure it errors when accessed from the main thread
        users_table.to_pandas()

    # thread required to execute the query
    users_result = await asyncio.to_thread(users_table.to_pandas)

    assert len(users_result) == 3
    assert set(users_result["name"].tolist()) == {"Alice", "Bob", "Charlie"}

    table = con.table("users")
    assert table.schema()
    assert table.columns
    assert table["age"].type()
