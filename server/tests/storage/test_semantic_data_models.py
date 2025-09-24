import typing
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage

    from .sample_model_creator import SampleModelCreator


async def check_semantic_data_model_storage_crud(
    model_creator: "SampleModelCreator",
) -> None:
    """Test semantic data model storage CRUD operations."""
    from uuid import uuid4

    await model_creator.setup()

    # Create sample data connections and file
    data_connection_1 = await model_creator.obtain_sample_data_connection("connection_1")
    data_connection_2 = await model_creator.obtain_sample_data_connection("connection_2")
    sample_file = await model_creator.obtain_sample_file()
    sample_thread = await model_creator.obtain_sample_thread()

    # Create a sample semantic model
    semantic_model = {
        "name": "test_semantic_model",
        "description": "A test semantic model",
        "tables": [
            {
                "name": "users",
                "base_table": {"database": "test_db", "schema": "public", "table": "users"},
                "dimensions": [
                    {"name": "user_id", "expr": "id", "data_type": "INTEGER"},
                    {"name": "user_name", "expr": "name", "data_type": "VARCHAR"},
                ],
                "facts": [{"name": "user_count", "expr": "COUNT(*)", "data_type": "INTEGER"}],
            }
        ],
    }

    # Test creating a semantic data model
    model_id = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,  # Generate new ID
        semantic_model=semantic_model,
        data_connection_ids=[data_connection_1.id, data_connection_2.id],
        file_references=[(sample_thread.thread_id, sample_file.file_ref)],
    )

    # Verify the model was created
    assert model_id is not None
    retrieved_model = await model_creator.storage.get_semantic_data_model(model_id)
    assert retrieved_model == semantic_model

    # Test updating the semantic data model
    updated_semantic_model = {
        "name": "updated_semantic_model",
        "description": "An updated test semantic model",
        "tables": [
            {
                "name": "products",
                "base_table": {"database": "test_db", "schema": "public", "table": "products"},
                "dimensions": [{"name": "product_id", "expr": "id", "data_type": "INTEGER"}],
            }
        ],
    }

    # Update with new data connections and file references
    data_connection_3 = await model_creator.obtain_sample_data_connection("connection_3")
    updated_model_id = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=model_id,  # Use existing ID
        semantic_model=updated_semantic_model,
        data_connection_ids=[data_connection_3.id],
        file_references=[(sample_thread.thread_id, sample_file.file_ref)],
    )

    # Verify the model was updated (should return the same ID)
    assert updated_model_id == model_id
    retrieved_updated_model = await model_creator.storage.get_semantic_data_model(model_id)
    assert retrieved_updated_model == updated_semantic_model

    # Test creating another semantic data model
    another_semantic_model = {
        "name": "another_semantic_model",
        "description": "Another test semantic model",
        "tables": [],
    }

    another_model_id = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,  # Generate new ID
        semantic_model=another_semantic_model,
        data_connection_ids=[data_connection_1.id],
        file_references=[],
    )

    # Verify both models exist
    assert another_model_id != model_id
    retrieved_another_model = await model_creator.storage.get_semantic_data_model(another_model_id)
    assert retrieved_another_model == another_semantic_model

    # Test deleting a semantic data model
    await model_creator.storage.delete_semantic_data_model(another_model_id)

    # Verify the model was deleted
    with pytest.raises(
        ValueError, match=f"Semantic data model with ID {another_model_id} not found"
    ):
        await model_creator.storage.get_semantic_data_model(another_model_id)

    # Verify the first model still exists
    retrieved_model = await model_creator.storage.get_semantic_data_model(model_id)
    assert retrieved_model == updated_semantic_model

    non_existent = str(uuid4())
    # Test deleting non-existent model
    with pytest.raises(ValueError, match="not found"):
        await model_creator.storage.delete_semantic_data_model(non_existent)

    # Test getting non-existent model
    with pytest.raises(ValueError, match="not found"):
        await model_creator.storage.get_semantic_data_model(non_existent)


@pytest.mark.asyncio
async def test_semantic_data_model_storage_crud_sqlite(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
) -> None:
    """Test semantic data model storage CRUD operations with SQLite."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await check_semantic_data_model_storage_crud(model_creator)


@pytest.mark.asyncio
async def test_semantic_data_model_storage_crud_postgres(
    postgres_storage: "PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test semantic data model storage CRUD operations with PostgreSQL."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(postgres_storage, tmpdir)
    await check_semantic_data_model_storage_crud(model_creator)


async def check_thread_semantic_data_model_storage_crud(
    model_creator: "SampleModelCreator",
) -> None:
    """Test thread semantic data model storage CRUD operations."""
    await model_creator.setup()

    # Create sample thread and semantic data models
    sample_thread = await model_creator.obtain_sample_thread()
    semantic_data_model_1 = await model_creator.obtain_sample_semantic_data_model("model_1")
    semantic_data_model_2 = await model_creator.obtain_sample_semantic_data_model("model_2")
    semantic_data_model_3 = await model_creator.obtain_sample_semantic_data_model("model_3")

    # Test initial state - no semantic data models associated
    model_ids = await model_creator.storage.get_thread_semantic_data_model_ids(
        sample_thread.thread_id
    )
    assert model_ids == []

    models = await model_creator.storage.get_thread_semantic_data_models(sample_thread.thread_id)
    assert models == []

    # Test setting semantic data models
    initial_model_ids = [semantic_data_model_1, semantic_data_model_2]
    await model_creator.storage.set_thread_semantic_data_models(
        sample_thread.thread_id, initial_model_ids
    )

    # Verify the models were set
    model_ids = await model_creator.storage.get_thread_semantic_data_model_ids(
        sample_thread.thread_id
    )
    assert set(model_ids) == set(initial_model_ids)

    models = await model_creator.storage.get_thread_semantic_data_models(sample_thread.thread_id)
    assert len(models) == 2

    # Test replacing models (set_thread_semantic_data_models should replace all existing)
    new_model_ids = [semantic_data_model_2, semantic_data_model_3]
    await model_creator.storage.set_thread_semantic_data_models(
        sample_thread.thread_id, new_model_ids
    )

    # Verify the models were replaced
    model_ids = await model_creator.storage.get_thread_semantic_data_model_ids(
        sample_thread.thread_id
    )
    assert set(model_ids) == set(new_model_ids)

    models = await model_creator.storage.get_thread_semantic_data_models(sample_thread.thread_id)
    assert len(models) == 2

    # Test setting empty models list (should remove all associations)
    await model_creator.storage.set_thread_semantic_data_models(sample_thread.thread_id, [])

    model_ids = await model_creator.storage.get_thread_semantic_data_model_ids(
        sample_thread.thread_id
    )
    assert model_ids == []

    models = await model_creator.storage.get_thread_semantic_data_models(sample_thread.thread_id)
    assert models == []


@pytest.mark.asyncio
async def test_thread_semantic_data_model_storage_crud_sqlite(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
) -> None:
    """Test thread semantic data model storage CRUD operations with SQLite."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await check_thread_semantic_data_model_storage_crud(model_creator)


@pytest.mark.asyncio
async def test_thread_semantic_data_model_storage_crud_postgres(
    postgres_storage: "PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test thread semantic data model storage CRUD operations with Postgres."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(postgres_storage, tmpdir)
    await check_thread_semantic_data_model_storage_crud(model_creator)


async def check_agent_semantic_data_model_storage_crud(
    model_creator: "SampleModelCreator",
) -> None:
    """Test agent semantic data model storage CRUD operations."""
    await model_creator.setup()

    # Create sample agent and semantic data models
    sample_agent = await model_creator.obtain_sample_agent()
    semantic_data_model_1 = await model_creator.obtain_sample_semantic_data_model("model_1")
    semantic_data_model_2 = await model_creator.obtain_sample_semantic_data_model("model_2")
    semantic_data_model_3 = await model_creator.obtain_sample_semantic_data_model("model_3")

    # Test initial state - no semantic data models associated
    model_ids = await model_creator.storage.get_agent_semantic_data_model_ids(sample_agent.agent_id)
    assert model_ids == []

    models = await model_creator.storage.get_agent_semantic_data_models(sample_agent.agent_id)
    assert models == []

    # Test setting semantic data models
    initial_model_ids = [semantic_data_model_1, semantic_data_model_2]
    await model_creator.storage.set_agent_semantic_data_models(
        sample_agent.agent_id, initial_model_ids
    )

    # Verify the models were set
    model_ids = await model_creator.storage.get_agent_semantic_data_model_ids(sample_agent.agent_id)
    assert set(model_ids) == set(initial_model_ids)

    models = await model_creator.storage.get_agent_semantic_data_models(sample_agent.agent_id)
    assert len(models) == 2

    # Test replacing models (set_agent_semantic_data_models should replace all existing)
    new_model_ids = [semantic_data_model_2, semantic_data_model_3]
    await model_creator.storage.set_agent_semantic_data_models(sample_agent.agent_id, new_model_ids)

    # Verify the models were replaced
    model_ids = await model_creator.storage.get_agent_semantic_data_model_ids(sample_agent.agent_id)
    assert set(model_ids) == set(new_model_ids)

    models = await model_creator.storage.get_agent_semantic_data_models(sample_agent.agent_id)
    assert len(models) == 2

    # Test setting empty models list (should remove all associations)
    await model_creator.storage.set_agent_semantic_data_models(sample_agent.agent_id, [])

    model_ids = await model_creator.storage.get_agent_semantic_data_model_ids(sample_agent.agent_id)
    assert model_ids == []

    models = await model_creator.storage.get_agent_semantic_data_models(sample_agent.agent_id)
    assert models == []


@pytest.mark.asyncio
async def test_agent_semantic_data_model_storage_crud_sqlite(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
) -> None:
    """Test agent semantic data model storage CRUD operations with SQLite."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await check_agent_semantic_data_model_storage_crud(model_creator)


@pytest.mark.asyncio
async def test_agent_semantic_data_model_storage_crud_postgres(
    postgres_storage: "PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test agent semantic data model storage CRUD operations with Postgres."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(postgres_storage, tmpdir)
    await check_agent_semantic_data_model_storage_crud(model_creator)
