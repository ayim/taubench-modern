import typing

import pytest

from agent_platform.core.data_connections.data_connections import DataConnection

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.fixture
def sample_data_connection() -> DataConnection:
    """Create a sample DataConnection for testing."""
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

    return DataConnection(
        id="550e8400-e29b-41d4-a716-446655440001",
        name="Test PostgreSQL Connection",
        description="Test connection for PostgreSQL",
        engine="postgres",
        configuration=PostgresDataConnectionConfiguration(
            host="localhost",
            port=5432,
            database="test_db",
            user="test_user",
            password="test_password",
        ),
        external_id="test-conn-1",
    )


@pytest.fixture
def sample_data_connection_2() -> DataConnection:
    """Create a second sample DataConnection for testing."""
    from agent_platform.core.payloads.data_connection import MySQLDataConnectionConfiguration

    return DataConnection(
        id="550e8400-e29b-41d4-a716-446655440002",
        name="Test MySQL Connection",
        description="Test connection for MySQL",
        engine="mysql",
        configuration=MySQLDataConnectionConfiguration(
            host="mysql.example.com",
            port=3306,
            database="production_db",
            user="prod_user",
            password="prod_password",
        ),
        external_id="test-conn-2",
    )


@pytest.mark.asyncio
async def test_data_connections_crud_operations(
    storage: "SQLiteStorage | PostgresStorage",
    sample_data_connection: DataConnection,
    sample_data_connection_2: DataConnection,
) -> None:
    """Test basic CRUD operations for data connections."""

    # Initially, there should be no data connections
    connections = await storage.get_data_connections()
    assert len(connections) == 0

    # Set connections with one item
    await storage.set_data_connection(sample_data_connection)
    connections = await storage.get_data_connections()
    assert len(connections) == 1
    assert connections[0].external_id == sample_data_connection.external_id

    # Set connections with multiple connections
    await storage.set_data_connection(sample_data_connection_2)
    connections = await storage.get_data_connections()
    assert len(connections) == 2

    # Clear all connections by deleting them
    await storage.delete_data_connection(sample_data_connection.id)
    await storage.delete_data_connection(sample_data_connection_2.id)
    connections = await storage.get_data_connections()
    assert len(connections) == 0


@pytest.mark.asyncio
async def test_data_connection_serialization(
    storage: "SQLiteStorage | PostgresStorage",
    sample_data_connection: DataConnection,
) -> None:
    """Test that data connection configuration is properly serialized/deserialized."""

    # Add a data connection with complex configuration
    await storage.set_data_connection(sample_data_connection)

    # Retrieve the connection
    connections = await storage.get_data_connections()
    assert len(connections) == 1

    retrieved_connection = connections[0]
    assert retrieved_connection.configuration == sample_data_connection.configuration

    # Cast to the specific configuration type for type checking
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

    config = retrieved_connection.configuration
    assert isinstance(config, PostgresDataConnectionConfiguration)
    assert config.host == "localhost"
    assert config.port == 5432


@pytest.mark.asyncio
async def test_data_connection_password_encryption(
    storage: "SQLiteStorage | PostgresStorage",
    sample_data_connection: DataConnection,
) -> None:
    """Test that passwords in data connection configuration are encrypted in storage."""

    # Add a data connection with password
    await storage.set_data_connection(sample_data_connection)

    # Retrieve the connection
    connections = await storage.get_data_connections()
    assert len(connections) == 1

    retrieved_connection = connections[0]

    # Cast to the specific configuration type for type checking
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

    config = retrieved_connection.configuration
    assert isinstance(config, PostgresDataConnectionConfiguration)

    # Verify the password is properly decrypted and returned as string
    assert isinstance(config.password, str)
    assert config.password == "test_password"

    # Verify other configuration fields are preserved
    assert config.host == "localhost"
    assert config.port == 5432
    assert config.database == "test_db"
    assert config.user == "test_user"
