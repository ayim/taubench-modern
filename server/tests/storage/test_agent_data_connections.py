import typing
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage

    from .sample_model_creator import SampleModelCreator


async def check_agent_data_connection_storage_crud(
    model_creator: "SampleModelCreator",
) -> None:
    """Test agent data connection storage CRUD operations."""
    await model_creator.setup()

    # Create sample agent and data connections
    sample_agent = await model_creator.obtain_sample_agent()
    data_connection_1 = await model_creator.obtain_sample_data_connection("connection_1")
    data_connection_2 = await model_creator.obtain_sample_data_connection("connection_2")
    data_connection_3 = await model_creator.obtain_sample_data_connection("connection_3")

    # Test initial state - no connections associated
    connection_ids = await model_creator.storage.get_agent_data_connection_ids(
        sample_agent.agent_id
    )
    assert connection_ids == []

    connections = await model_creator.storage.get_agent_data_connections(sample_agent.agent_id)
    assert connections == []

    # Test setting data connections
    initial_connection_ids = [data_connection_1.id, data_connection_2.id]
    await model_creator.storage.set_agent_data_connections(
        sample_agent.agent_id, initial_connection_ids
    )

    # Verify the connections were set
    connection_ids = await model_creator.storage.get_agent_data_connection_ids(
        sample_agent.agent_id
    )
    assert set(connection_ids) == set(initial_connection_ids)

    connections = await model_creator.storage.get_agent_data_connections(sample_agent.agent_id)
    assert len(connections) == 2
    connection_ids_from_objects = {conn.id for conn in connections}
    assert connection_ids_from_objects == set(initial_connection_ids)

    # Verify the connection objects have correct data
    for conn in connections:
        assert conn.name in ["connection_1", "connection_2"]
        assert conn.engine == "sqlite"
        assert conn.configuration is not None

    # Test replacing connections (set_agent_data_connections should replace all existing)
    new_connection_ids = [data_connection_2.id, data_connection_3.id]
    await model_creator.storage.set_agent_data_connections(
        sample_agent.agent_id, new_connection_ids
    )

    # Verify the connections were replaced
    connection_ids = await model_creator.storage.get_agent_data_connection_ids(
        sample_agent.agent_id
    )
    assert set(connection_ids) == set(new_connection_ids)

    connections = await model_creator.storage.get_agent_data_connections(sample_agent.agent_id)
    assert len(connections) == 2
    connection_ids_from_objects = {conn.id for conn in connections}
    assert connection_ids_from_objects == set(new_connection_ids)

    # Test setting empty connections list (should remove all associations)
    await model_creator.storage.set_agent_data_connections(sample_agent.agent_id, [])

    connection_ids = await model_creator.storage.get_agent_data_connection_ids(
        sample_agent.agent_id
    )
    assert connection_ids == []

    connections = await model_creator.storage.get_agent_data_connections(sample_agent.agent_id)
    assert connections == []


@pytest.mark.asyncio
async def test_agent_data_connection_storage_crud_sqlite(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
) -> None:
    """Test agent data connection storage CRUD operations with SQLite."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await check_agent_data_connection_storage_crud(model_creator)


@pytest.mark.asyncio
async def test_agent_data_connection_storage_crud_postgres(
    postgres_storage: "PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test agent data connection storage CRUD operations with Postgres."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(postgres_storage, tmpdir)
    await check_agent_data_connection_storage_crud(model_creator)
