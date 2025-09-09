import pytest

from agent_platform.core.data_server.data_connection import (
    DataConnection,
    DataConnectionEngine,
)
from agent_platform.server.storage import PostgresStorage, SQLiteStorage


@pytest.fixture
def sample_data_connection() -> DataConnection:
    """Create a sample DataConnection for testing."""
    return DataConnection(
        external_id="test-conn-1",
        name="Test PostgreSQL Connection",
        engine=DataConnectionEngine.POSTGRES.value,
        configuration={
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_password",
        },
    )


@pytest.fixture
def sample_data_connection_2() -> DataConnection:
    """Create a second sample DataConnection for testing."""
    return DataConnection(
        external_id="test-conn-2",
        name="Test MySQL Connection",
        engine="mysql",
        configuration={
            "host": "mysql.example.com",
            "port": 3306,
            "database": "production_db",
            "user": "prod_user",
            "password": "prod_password",
        },
    )


@pytest.mark.asyncio
async def test_set_data_connections_replace_all(
    storage: "SQLiteStorage | PostgresStorage",
    sample_data_connection: DataConnection,
    sample_data_connection_2: DataConnection,
) -> None:
    """Test that set_dids_data_connections replaces all existing connections (PUT semantics)."""

    # Initially, there should be no data connections
    connections = await storage.get_dids_data_connections()
    assert len(connections) == 0

    # Set connections with one item
    await storage.set_dids_data_connections([sample_data_connection])
    connections = await storage.get_dids_data_connections()
    assert len(connections) == 1
    assert connections[0].external_id == sample_data_connection.external_id

    # Set connections with multiple connections
    await storage.set_dids_data_connections([sample_data_connection, sample_data_connection_2])
    connections = await storage.get_dids_data_connections()
    assert len(connections) == 2

    # Set connections with empty list (should clear all)
    await storage.set_dids_data_connections([])
    connections = await storage.get_dids_data_connections()
    assert len(connections) == 0


@pytest.mark.asyncio
async def test_data_connection_serialization(
    storage: "SQLiteStorage | PostgresStorage",
    sample_data_connection: DataConnection,
) -> None:
    """Test that data connection configuration is properly serialized/deserialized."""

    # Add a data connection with complex configuration
    await storage.set_dids_data_connections([sample_data_connection])

    # Retrieve the connection
    connections = await storage.get_dids_data_connections()
    assert len(connections) == 1

    retrieved_connection = connections[0]
    assert retrieved_connection.configuration == sample_data_connection.configuration
    assert isinstance(retrieved_connection.configuration, dict)
    assert retrieved_connection.configuration["host"] == "localhost"
    assert retrieved_connection.configuration["port"] == 5432


@pytest.mark.asyncio
async def test_data_connection_password_encryption(
    storage: "SQLiteStorage | PostgresStorage",
    sample_data_connection: DataConnection,
) -> None:
    """Test that passwords in data connection configuration are encrypted in storage."""
    from agent_platform.core.utils import SecretString

    # Add a data connection with password
    await storage.set_dids_data_connections([sample_data_connection])

    # Retrieve the connection
    connections = await storage.get_dids_data_connections()
    assert len(connections) == 1

    retrieved_connection = connections[0]

    # Verify the password is properly decrypted and returned as SecretString
    assert isinstance(retrieved_connection.configuration["password"], SecretString)
    assert retrieved_connection.configuration["password"].get_secret_value() == "test_password"

    # Verify other configuration fields are preserved
    assert retrieved_connection.configuration["host"] == "localhost"
    assert retrieved_connection.configuration["port"] == 5432
    assert retrieved_connection.configuration["database"] == "test_db"
    assert retrieved_connection.configuration["user"] == "test_user"
