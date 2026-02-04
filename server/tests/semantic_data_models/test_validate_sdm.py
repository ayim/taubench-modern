"""Tests for validate_sdm schema uniqueness validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from agent_platform.core.semantic_data_model import SemanticDataModel
from agent_platform.core.semantic_data_model.schemas import Schema
from agent_platform.server.semantic_data_models import validate_sdm

pytest_plugins = ["server.tests.storage_fixtures"]

if TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


def _make_sdm_with_schema(name: str, schema_name: str) -> SemanticDataModel:
    """Helper to create a minimal SDM with one schema."""
    return SemanticDataModel(
        name=name,
        tables=[],
        schemas=[
            Schema(
                name=schema_name,
                description="Test schema",
                json_schema={"type": "object"},
            )
        ],
    )


async def _save_sdm(storage: SQLiteStorage | PostgresStorage, sdm: SemanticDataModel) -> str:
    """Helper to save an SDM and return its ID."""
    return await storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=sdm,
        data_connection_ids=[],
        file_references=[],
    )


@pytest.mark.asyncio
async def test_validate_sdm_create_with_unique_schema_name(
    storage: SQLiteStorage | PostgresStorage,
) -> None:
    """Test creating a new SDM with a schema name that doesn't conflict."""
    # Create an existing SDM with a schema
    existing_sdm = _make_sdm_with_schema("existing_model", "existing_schema")
    await _save_sdm(storage, existing_sdm)

    # Validate a new SDM with a different schema name - should pass
    new_sdm = _make_sdm_with_schema("new_model", "new_schema")
    await validate_sdm(new_sdm, storage)  # No exception = success


@pytest.mark.asyncio
async def test_validate_sdm_update_with_same_schema_name(
    storage: SQLiteStorage | PostgresStorage,
) -> None:
    """Test updating an existing SDM where the schema name hasn't changed."""
    # Create an SDM with a schema
    sdm = _make_sdm_with_schema("my_model", "my_schema")
    sdm_id = await _save_sdm(storage, sdm)

    # Validate the same SDM for update - should pass
    # Set the id so validate_sdm knows to exclude this SDM
    sdm.id = sdm_id
    await validate_sdm(sdm, storage)  # No exception = success


@pytest.mark.asyncio
async def test_validate_sdm_create_with_conflicting_schema_name(
    storage: SQLiteStorage | PostgresStorage,
) -> None:
    """Test creating a new SDM with a schema name that conflicts with an existing one."""
    # Create an existing SDM with a schema
    existing_sdm = _make_sdm_with_schema("existing_model", "shared_schema")
    await _save_sdm(storage, existing_sdm)

    # Try to create a new SDM with the same schema name - should fail
    new_sdm = _make_sdm_with_schema("new_model", "shared_schema")
    with pytest.raises(ValueError, match="already used by another semantic data model"):
        await validate_sdm(new_sdm, storage)


@pytest.mark.asyncio
async def test_validate_sdm_update_with_conflicting_schema_name(
    storage: SQLiteStorage | PostgresStorage,
) -> None:
    """Test updating an SDM to use a schema name that conflicts with another SDM."""
    # Create two SDMs with different schema names
    sdm_a = _make_sdm_with_schema("model_a", "schema_a")
    sdm_a_id = await _save_sdm(storage, sdm_a)

    sdm_b = _make_sdm_with_schema("model_b", "schema_b")
    await _save_sdm(storage, sdm_b)

    # Try to update SDM A to use schema_b's name - should fail
    updated_sdm_a = _make_sdm_with_schema("model_a", "schema_b")
    # Set the id so validate_sdm knows to exclude this SDM
    updated_sdm_a.id = sdm_a_id
    with pytest.raises(ValueError, match="already used by another semantic data model"):
        await validate_sdm(updated_sdm_a, storage)
