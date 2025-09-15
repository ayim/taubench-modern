from uuid import uuid4

import pytest

from agent_platform.core.data_connections.data_connections import DataConnection
from agent_platform.core.payloads.data_connection import (
    MySQLDataConnectionConfiguration,
    PostgresDataConnectionConfiguration,
)
from agent_platform.server.storage.errors import DataConnectionNotFoundError
from agent_platform.server.storage.postgres import PostgresStorage


@pytest.fixture
def sample_data_connection() -> DataConnection:
    return DataConnection(
        id=str(uuid4()),
        name="Test PostgreSQL Connection",
        description="Test connection for PostgreSQL database",
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
    return DataConnection(
        id=str(uuid4()),
        name="Test MySQL Connection",
        description="Test connection for MySQL database",
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
async def test_data_connection_crud_operations(
    storage: PostgresStorage,
    sample_data_connection: DataConnection,
    sample_data_connection_2: DataConnection,
) -> None:
    connections = await storage.get_data_connections()
    assert len(connections) == 0

    await storage.set_data_connection(sample_data_connection)
    connections = await storage.get_data_connections()
    assert len(connections) == 1
    assert connections[0].id == sample_data_connection.id
    assert connections[0].name == sample_data_connection.name
    assert connections[0].configuration == sample_data_connection.configuration

    retrieved_connection = await storage.get_data_connection(sample_data_connection.id)
    assert retrieved_connection.id == sample_data_connection.id
    assert retrieved_connection.name == sample_data_connection.name
    assert retrieved_connection.configuration == sample_data_connection.configuration

    with pytest.raises(DataConnectionNotFoundError):
        await storage.get_data_connection(str(uuid4()))

    updated_connection = DataConnection(
        id=sample_data_connection.id,
        name="Updated PostgreSQL Connection",
        description="Updated test connection",
        engine="postgres",
        configuration=PostgresDataConnectionConfiguration(
            host="updated-host",
            port=5433,
            database="updated_db",
            user="updated_user",
            password="updated_password",
        ),
        external_id="updated-conn-1",
    )
    await storage.update_data_connection(updated_connection)
    retrieved_updated = await storage.get_data_connection(sample_data_connection.id)
    assert retrieved_updated.name == "Updated PostgreSQL Connection"
    assert retrieved_updated.engine == "postgres"
    assert isinstance(retrieved_updated.configuration, PostgresDataConnectionConfiguration)
    assert retrieved_updated.configuration.host == "updated-host"

    await storage.set_data_connection(sample_data_connection_2)
    connections = await storage.get_data_connections()
    assert len(connections) == 2

    await storage.delete_data_connection(sample_data_connection.id)
    connections = await storage.get_data_connections()
    assert len(connections) == 1
    assert connections[0].id == sample_data_connection_2.id

    with pytest.raises(DataConnectionNotFoundError):
        await storage.delete_data_connection(str(uuid4()))
