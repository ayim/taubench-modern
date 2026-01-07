"""Tests for semantic data models utility functions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_cannot_create_semantic_data_model_with_duplicate_name(
    storage: SQLiteStorage | PostgresStorage,
    tmpdir: Path,
) -> None:
    """Test that validation fails when creating an SDM when one already exists with the same name."""
    from tests.storage.sample_model_creator import SampleModelCreator

    from agent_platform.server.semantic_data_models import (
        SemanticDataModelWithNameAlreadyExistsError,
        validate_semantic_data_model_name_is_unique,
    )

    model_creator = SampleModelCreator(storage, tmpdir)
    await model_creator.setup()

    # Create sample data connection
    data_connection = await model_creator.obtain_sample_data_connection("connection_1")

    # Create first semantic data model
    semantic_model_1 = {
        "name": "my_sales_model",
        "description": "First model",
        "tables": [
            {
                "name": "users",
                "base_table": {"database": "test_db", "schema": "public", "table": "users"},
                "dimensions": [{"name": "user_id", "expr": "id", "data_type": "INTEGER"}],
            }
        ],
    }

    model_id_1 = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_1,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )
    assert model_id_1 is not None

    # Try to validate creating another model with the same name (should fail)
    with pytest.raises(SemanticDataModelWithNameAlreadyExistsError) as exc_info:
        await validate_semantic_data_model_name_is_unique("my_sales_model", storage=storage)
    assert "my_sales_model" in str(exc_info.value)
    assert "case-insensitive" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cannot_rename_semantic_data_model_to_existing_name(
    storage: SQLiteStorage | PostgresStorage,
    tmpdir: Path,
) -> None:
    """Test that validation fails when renaming an SDM when one already exists with that name."""
    from tests.storage.sample_model_creator import SampleModelCreator

    from agent_platform.server.semantic_data_models import (
        SemanticDataModelWithNameAlreadyExistsError,
        validate_semantic_data_model_name_is_unique,
    )

    model_creator = SampleModelCreator(storage, tmpdir)
    await model_creator.setup()

    # Create sample data connection
    data_connection = await model_creator.obtain_sample_data_connection("connection_1")

    # Create first semantic data model
    semantic_model_1 = {
        "name": "sales_model",
        "description": "First model",
        "tables": [
            {
                "name": "users",
                "base_table": {"database": "test_db", "schema": "public", "table": "users"},
                "dimensions": [{"name": "user_id", "expr": "id", "data_type": "INTEGER"}],
            }
        ],
    }

    model_id_1 = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_1,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )
    assert model_id_1 is not None

    # Create a second model with a different name
    semantic_model_2 = {
        "name": "orders_model",
        "description": "Second model with different name",
        "tables": [
            {
                "name": "orders",
                "base_table": {"database": "test_db", "schema": "public", "table": "orders"},
                "dimensions": [{"name": "order_id", "expr": "id", "data_type": "INTEGER"}],
            }
        ],
    }

    model_id_2 = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model_2,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )
    assert model_id_2 is not None

    # Try to validate renaming model_2 to have the same name as model_1 (should fail)
    with pytest.raises(SemanticDataModelWithNameAlreadyExistsError) as exc_info:
        await validate_semantic_data_model_name_is_unique("sales_model", exclude_model_id=model_id_2, storage=storage)
    assert "sales_model" in str(exc_info.value)

    # Verify model_2 still has its original name
    retrieved_model_2 = await model_creator.storage.get_semantic_data_model(model_id_2)
    assert retrieved_model_2["name"] == "orders_model"


@pytest.mark.asyncio
async def test_semantic_data_model_name_validation_is_case_insensitive(
    storage: SQLiteStorage | PostgresStorage,
    tmpdir: Path,
) -> None:
    """Test that name validation is case-insensitive."""
    from tests.storage.sample_model_creator import SampleModelCreator

    from agent_platform.server.semantic_data_models import (
        SemanticDataModelWithNameAlreadyExistsError,
        validate_semantic_data_model_name_is_unique,
    )

    model_creator = SampleModelCreator(storage, tmpdir)
    await model_creator.setup()

    # Create sample data connection
    data_connection = await model_creator.obtain_sample_data_connection("connection_1")

    # Create semantic data model with lowercase name
    semantic_model = {
        "name": "my_model",
        "description": "Test model",
        "tables": [
            {
                "name": "users",
                "base_table": {"database": "test_db", "schema": "public", "table": "users"},
                "dimensions": [{"name": "user_id", "expr": "id", "data_type": "INTEGER"}],
            }
        ],
    }

    model_id = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )
    assert model_id is not None

    # Try to validate creating a model with different case (should fail)
    with pytest.raises(SemanticDataModelWithNameAlreadyExistsError) as exc_info:
        await validate_semantic_data_model_name_is_unique("MY_MODEL", storage=storage)
    assert "MY_MODEL" in str(exc_info.value)

    # Try other case variations
    with pytest.raises(SemanticDataModelWithNameAlreadyExistsError):
        await validate_semantic_data_model_name_is_unique("My_Model", storage=storage)


@pytest.mark.asyncio
async def test_can_validate_semantic_data_model_name_with_exclusion(
    storage: SQLiteStorage | PostgresStorage,
    tmpdir: Path,
) -> None:
    """Test that validation passes when checking a model's own name with exclusion."""
    from tests.storage.sample_model_creator import SampleModelCreator

    from agent_platform.server.semantic_data_models import validate_semantic_data_model_name_is_unique

    model_creator = SampleModelCreator(storage, tmpdir)
    await model_creator.setup()

    # Create sample data connection
    data_connection = await model_creator.obtain_sample_data_connection("connection_1")

    # Create semantic data model
    semantic_model = {
        "name": "my_unique_model",
        "description": "Test model",
        "tables": [
            {
                "name": "users",
                "base_table": {"database": "test_db", "schema": "public", "table": "users"},
                "dimensions": [{"name": "user_id", "expr": "id", "data_type": "INTEGER"}],
            }
        ],
    }

    model_id = await model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )
    assert model_id is not None

    # Validating the model's own name with exclusion should pass (for updates)
    await validate_semantic_data_model_name_is_unique("my_unique_model", exclude_model_id=model_id, storage=storage)

    # Can also validate a completely new name
    await validate_semantic_data_model_name_is_unique("brand_new_model", storage=storage)
