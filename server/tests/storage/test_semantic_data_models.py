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

    from agent_platform.core.errors.base import PlatformHTTPError

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
    with pytest.raises(PlatformHTTPError, match=f"Semantic data model with ID {another_model_id} not found"):
        await model_creator.storage.get_semantic_data_model(another_model_id)

    # Verify the first model still exists
    retrieved_model = await model_creator.storage.get_semantic_data_model(model_id)
    assert retrieved_model == updated_semantic_model

    non_existent = str(uuid4())
    # Test deleting non-existent model
    with pytest.raises(PlatformHTTPError, match="not found"):
        await model_creator.storage.delete_semantic_data_model(non_existent)

    # Test getting non-existent model
    with pytest.raises(PlatformHTTPError, match="not found"):
        await model_creator.storage.get_semantic_data_model(non_existent)


@pytest.mark.asyncio
async def test_semantic_data_model_storage_crud(
    storage: "SQLiteStorage|PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test semantic data model storage CRUD operations with SQLite."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(storage, tmpdir)
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
    model_ids = await model_creator.storage.get_thread_semantic_data_model_ids(sample_thread.thread_id)
    assert model_ids == []

    models = await model_creator.storage.get_thread_semantic_data_models(sample_thread.thread_id)
    assert models == []

    # Test setting semantic data models
    initial_model_ids = [semantic_data_model_1, semantic_data_model_2]
    await model_creator.storage.set_thread_semantic_data_models(sample_thread.thread_id, initial_model_ids)

    # Verify the models were set
    model_ids = await model_creator.storage.get_thread_semantic_data_model_ids(sample_thread.thread_id)
    assert set(model_ids) == set(initial_model_ids)

    models = await model_creator.storage.get_thread_semantic_data_models(sample_thread.thread_id)
    assert len(models) == 2

    # Test replacing models (set_thread_semantic_data_models should replace all existing)
    new_model_ids = [semantic_data_model_2, semantic_data_model_3]
    await model_creator.storage.set_thread_semantic_data_models(sample_thread.thread_id, new_model_ids)

    # Verify the models were replaced
    model_ids = await model_creator.storage.get_thread_semantic_data_model_ids(sample_thread.thread_id)
    assert set(model_ids) == set(new_model_ids)

    models = await model_creator.storage.get_thread_semantic_data_models(sample_thread.thread_id)
    assert len(models) == 2

    # Test setting empty models list (should remove all associations)
    await model_creator.storage.set_thread_semantic_data_models(sample_thread.thread_id, [])

    model_ids = await model_creator.storage.get_thread_semantic_data_model_ids(sample_thread.thread_id)
    assert model_ids == []

    models = await model_creator.storage.get_thread_semantic_data_models(sample_thread.thread_id)
    assert models == []


@pytest.mark.asyncio
async def test_thread_semantic_data_model_storage_crud(
    storage: "SQLiteStorage|PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test thread semantic data model storage CRUD operations with SQLite."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(storage, tmpdir)
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
    await model_creator.storage.set_agent_semantic_data_models(sample_agent.agent_id, initial_model_ids)

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
async def test_agent_semantic_data_model_storage_crud(
    storage: "SQLiteStorage|PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test agent semantic data model storage CRUD operations with SQLite."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(storage, tmpdir)
    await check_agent_semantic_data_model_storage_crud(model_creator)


async def check_list_semantic_data_models(
    model_creator: "SampleModelCreator",
) -> None:
    """Test listing semantic data models with associations."""
    await model_creator.setup()

    # Create sample data connections and files
    data_connection_1 = await model_creator.obtain_sample_data_connection("connection_1")
    data_connection_2 = await model_creator.obtain_sample_data_connection("connection_2")
    sample_file = await model_creator.obtain_sample_file()
    sample_thread = await model_creator.obtain_sample_thread()
    sample_agent = await model_creator.obtain_sample_agent()

    # Create some spurious models which should not affect the results
    model_creator.sample_thread = None
    model_creator.sample_agent = None
    await model_creator.obtain_sample_agent(agent_name="Spurious Agent")
    await model_creator.obtain_sample_thread()

    # Create first semantic data model
    semantic_model_1 = {
        "name": "test_semantic_model_1",
        "description": "First test semantic model",
        "tables": [
            {
                "name": "users",
                "base_table": {"database": "test_db", "schema": "public", "table": "users"},
                "dimensions": [
                    {"name": "user_id", "expr": "id", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    model_id_1 = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_1,
        data_connection_ids=[data_connection_1.id],
        file_references=[(sample_thread.thread_id, sample_file.file_ref)],
    )

    # Create second semantic data model
    semantic_model_2 = {
        "name": "test_semantic_model_2",
        "description": "Second test semantic model",
        "tables": [
            {
                "name": "products",
                "base_table": {"database": "test_db", "schema": "public", "table": "products"},
                "dimensions": [
                    {"name": "product_id", "expr": "id", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    model_id_2 = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_2,
        data_connection_ids=[data_connection_2.id],
        file_references=[],
    )
    # Create second semantic data model
    semantic_model_3 = {
        "name": "test_semantic_model_3",
        "description": "Second test semantic model",
        "tables": [
            {
                "name": "products",
                "base_table": {"database": "test_db", "schema": "public", "table": "products"},
                "dimensions": [
                    {"name": "product_id", "expr": "id", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    model_id_3 = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_3,
        data_connection_ids=[data_connection_2.id],
        file_references=[],
    )

    # Associate models with agent and thread
    await model_creator.storage.set_agent_semantic_data_models(sample_agent.agent_id, [model_id_1, model_id_2])
    await model_creator.storage.set_thread_semantic_data_models(sample_thread.thread_id, [model_id_1])

    # Test listing all semantic data models
    all_models = await model_creator.storage.list_semantic_data_models()

    def check_models(all_models):
        for model in all_models:
            model_id = model["semantic_data_model_id"]
            if model_id == model_id_1:
                assert model["agent_ids"] == {sample_agent.agent_id}
                assert model["thread_ids"] == {sample_thread.thread_id}
            elif model_id == model_id_2:
                assert model["agent_ids"] == {sample_agent.agent_id}
                assert model["thread_ids"] == set()
            elif model_id == model_id_3:
                assert model["agent_ids"] == set()
                assert model["thread_ids"] == set()
            else:
                raise ValueError(
                    f"Model {model} not found. Checked ids: {model_id_1}, "
                    f"{model_id_2}, {model_id_3}, Model id: {model_id}"
                )

    check_models(all_models)

    # Test listing semantic data models with agent_id
    agent_models = await model_creator.storage.list_semantic_data_models(agent_id=sample_agent.agent_id)
    assert len(agent_models) == 2
    check_models(agent_models)

    # Test listing semantic data models with thread_id
    thread_models = await model_creator.storage.list_semantic_data_models(thread_id=sample_thread.thread_id)
    assert len(thread_models) == 1
    check_models(thread_models)

    # Test listing semantic data models with agent_id and thread_id
    agent_thread_models = await model_creator.storage.list_semantic_data_models(
        agent_id=sample_agent.agent_id, thread_id=sample_thread.thread_id
    )
    assert len(agent_thread_models) == 2
    check_models(agent_thread_models)


@pytest.mark.asyncio
async def test_list_semantic_data_models(
    storage: "SQLiteStorage|PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test listing semantic data models with SQLite."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(storage, tmpdir)
    await check_list_semantic_data_models(model_creator)


async def check_semantic_data_model_metadata(
    model_creator: "SampleModelCreator",
) -> None:
    """Test semantic data model metadata field handling."""
    from datetime import UTC, datetime

    await model_creator.setup()

    # Create sample data connection
    data_connection = await model_creator.obtain_sample_data_connection("test_connection")

    # Create a semantic model with metadata
    semantic_model_with_metadata = {
        "name": "test_model_with_metadata",
        "description": "A test model with metadata",
        "tables": [
            {
                "name": "users",
                "base_table": {
                    "data_connection_id": data_connection.id,
                    "database": "test_db",
                    "schema": "public",
                    "table": "users",
                },
                "dimensions": [
                    {"name": "user_id", "expr": "id", "data_type": "INTEGER"},
                ],
            }
        ],
        "metadata": {
            "input_data_connection_snapshots": [
                {
                    "source_type": "data_connection",
                    "data_connection_id": data_connection.id,
                    "engine": "postgres",
                    "inspected_at": datetime.now(UTC).isoformat(),
                    "inspector_version": "1.0.0",
                    "tables_snapshot": [
                        {
                            "name": "users",
                            "database": "test_db",
                            "schema": "public",
                            "columns": [
                                {
                                    "name": "id",
                                    "data_type": "INTEGER",
                                    "sample_values": [1, 2, 3],
                                },
                                {
                                    "name": "name",
                                    "data_type": "VARCHAR",
                                    "sample_values": ["Alice", "Bob"],
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    }

    # Test creating semantic model with metadata
    model_id = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_with_metadata,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )

    # Verify metadata was stored
    retrieved_model = await model_creator.storage.get_semantic_data_model(model_id)
    assert retrieved_model is not None
    assert "metadata" in retrieved_model
    assert retrieved_model["metadata"] is not None
    assert "input_data_connection_snapshots" in retrieved_model["metadata"]

    snapshots = retrieved_model["metadata"]["input_data_connection_snapshots"]
    assert isinstance(snapshots, list)
    assert len(snapshots) == 1

    snapshot = snapshots[0]
    assert snapshot["source_type"] == "data_connection"
    assert snapshot["data_connection_id"] == data_connection.id
    assert snapshot["engine"] == "postgres"
    assert "inspector_version" in snapshot
    assert "tables_snapshot" in snapshot
    assert len(snapshot["tables_snapshot"]) == 1
    assert snapshot["tables_snapshot"][0]["name"] == "users"

    # Test creating semantic model without metadata (backward compatibility)
    semantic_model_without_metadata = {
        "name": "test_model_without_metadata",
        "description": "A test model without metadata",
        "tables": [
            {
                "name": "products",
                "base_table": {
                    "data_connection_id": data_connection.id,
                    "database": "test_db",
                    "schema": "public",
                    "table": "products",
                },
                "dimensions": [
                    {"name": "product_id", "expr": "id", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    model_id_no_metadata = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_without_metadata,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )

    # Verify model without metadata works fine
    retrieved_model_no_metadata = await model_creator.storage.get_semantic_data_model(model_id_no_metadata)
    assert retrieved_model_no_metadata is not None
    # Metadata field may or may not be present (both are valid)
    assert retrieved_model_no_metadata.get("metadata") is None or "metadata" not in retrieved_model_no_metadata


@pytest.mark.asyncio
async def test_semantic_data_model_metadata(
    storage: "SQLiteStorage|PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test semantic data model metadata field handling."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(storage, tmpdir)
    await check_semantic_data_model_metadata(model_creator)
