from unittest.mock import patch
from uuid import uuid4

import pytest

from agent_platform.core.platforms.azure import AzureOpenAIPlatformParameters
from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.platforms.openai import OpenAIPlatformParameters
from agent_platform.core.utils import SecretString
from agent_platform.server.storage.errors import (
    InvalidUUIDError,
    PlatformConfigNotFoundError,
    PlatformConfigWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.sqlite import SQLiteStorage

# Register platform parameters for testing
PlatformParameters.register_platform_parameters("openai", OpenAIPlatformParameters)
PlatformParameters.register_platform_parameters("azure", AzureOpenAIPlatformParameters)


@pytest.fixture
def sample_openai_platform_params() -> OpenAIPlatformParameters:
    """Sample OpenAI platform parameters for testing."""
    return OpenAIPlatformParameters(
        name="Test OpenAI Config",
        description="Test OpenAI platform configuration",
        openai_api_key=SecretString("test-openai-key"),
        models={"OpenAI": ["gpt-4", "gpt-3.5-turbo"]},
    )


@pytest.fixture
def sample_azure_platform_params() -> AzureOpenAIPlatformParameters:
    """Sample Azure platform parameters for testing."""
    return AzureOpenAIPlatformParameters(
        name="Test Azure Config",
        description="Test Azure platform configuration",
        azure_api_key=SecretString("test-azure-key"),
        azure_endpoint_url="https://test.openai.azure.com/",
        azure_deployment_name="test-deployment",
        azure_api_version="2023-03-15-preview",
        models={"Azure": ["gpt-4", "gpt-35-turbo"]},
    )


@pytest.mark.asyncio
async def test_platform_params_crud_operations(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test Create, Read, Update, and Delete operations for platform parameters."""

    # Create
    await storage.create_platform_params(sample_openai_platform_params)

    # Read
    retrieved_params = await storage.get_platform_params(sample_openai_platform_params.platform_id)
    assert retrieved_params is not None
    assert retrieved_params.platform_id == sample_openai_platform_params.platform_id
    assert retrieved_params.name == sample_openai_platform_params.name
    assert retrieved_params.description == sample_openai_platform_params.description
    assert retrieved_params.kind == "openai"
    assert retrieved_params.models == sample_openai_platform_params.models

    # Update
    updated_params = sample_openai_platform_params.model_copy(
        update={
            "name": "Updated OpenAI Config",
            "description": "Updated description",
            "models": {"OpenAI": ["gpt-4", "gpt-4-turbo"]},
        }
    )
    await storage.update_platform_params(sample_openai_platform_params.platform_id, updated_params)

    retrieved_updated = await storage.get_platform_params(sample_openai_platform_params.platform_id)
    assert retrieved_updated.name == "Updated OpenAI Config"
    assert retrieved_updated.description == "Updated description"
    assert retrieved_updated.models == {"OpenAI": ["gpt-4", "gpt-4-turbo"]}

    # Delete
    await storage.delete_platform_params(sample_openai_platform_params.platform_id)

    with pytest.raises(PlatformConfigNotFoundError):
        await storage.get_platform_params(sample_openai_platform_params.platform_id)


@pytest.mark.asyncio
async def test_list_platform_params(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_openai_platform_params: OpenAIPlatformParameters,
    sample_azure_platform_params: AzureOpenAIPlatformParameters,
) -> None:
    """Test listing platform parameters for a user."""

    # Initially empty
    params_list = await storage.list_platform_params()
    assert len(params_list) == 0

    # Create two platform configurations
    await storage.create_platform_params(sample_openai_platform_params)
    await storage.create_platform_params(sample_azure_platform_params)

    # List should return both
    params_list = await storage.list_platform_params()
    assert len(params_list) == 2

    # Verify the configurations are present
    platform_ids = {p.platform_id for p in params_list}
    assert sample_openai_platform_params.platform_id in platform_ids
    assert sample_azure_platform_params.platform_id in platform_ids

    # Verify the configurations have correct types
    kinds = {p.kind for p in params_list}
    assert "openai" in kinds
    assert "azure" in kinds


@pytest.mark.asyncio
async def test_platform_params_with_same_name_not_allowed(
    storage: SQLiteStorage,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test that platform parameters with the same name are not allowed (since they're global)."""

    # Create the first platform params
    params1 = sample_openai_platform_params.model_copy(update={"name": "Shared Name"})
    await storage.create_platform_params(params1)

    # Try to create another with the same name should fail
    params2 = sample_openai_platform_params.model_copy(
        update={
            "name": "Shared Name",
            "platform_id": str(uuid4()),  # Different platform_id
        }
    )

    with pytest.raises(
        PlatformConfigWithNameAlreadyExistsError,
        match="Platform params with name 'Shared Name' already exists",
    ):
        await storage.create_platform_params(params2)


@pytest.mark.asyncio
async def test_create_platform_params_duplicate_id_error(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test that creating platform parameters with duplicate ID raises error."""

    # Create the first platform params
    await storage.create_platform_params(sample_openai_platform_params)

    # Try to create another with the same platform_id should fail
    duplicate_params = sample_openai_platform_params.model_copy(update={"name": "Different Name"})

    with pytest.raises(RecordAlreadyExistsError, match="already exists"):
        await storage.create_platform_params(duplicate_params)


@pytest.mark.asyncio
async def test_create_platform_params_duplicate_name_error(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test that creating platform parameters with duplicate name for same user raises error."""

    # Create the first platform params
    await storage.create_platform_params(sample_openai_platform_params)

    # Try to create another with the same name should fail
    duplicate_name_params = OpenAIPlatformParameters(
        name=sample_openai_platform_params.name,  # Same name
        description="Different description",
        openai_api_key=SecretString("different-key"),
        platform_id=str(uuid4()),  # Different ID
    )

    with pytest.raises(
        PlatformConfigWithNameAlreadyExistsError,
        match=f"Platform params with name '{sample_openai_platform_params.name}' already exists",
    ):
        await storage.create_platform_params(duplicate_name_params)


@pytest.mark.asyncio
async def test_get_platform_params_not_found_error(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test that getting non-existent platform parameters raises error."""

    non_existent_id = str(uuid4())

    with pytest.raises(
        PlatformConfigNotFoundError, match=f"Platform params {non_existent_id} not found"
    ):
        await storage.get_platform_params(non_existent_id)


@pytest.mark.asyncio
async def test_update_platform_params_not_found_error(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test that updating non-existent platform parameters raises error."""

    non_existent_id = str(uuid4())

    with pytest.raises(
        PlatformConfigNotFoundError, match=f"Platform params {non_existent_id} not found"
    ):
        await storage.update_platform_params(non_existent_id, sample_openai_platform_params)


@pytest.mark.asyncio
async def test_update_platform_params_name_conflict_error(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_openai_platform_params: OpenAIPlatformParameters,
    sample_azure_platform_params: AzureOpenAIPlatformParameters,
) -> None:
    """Test that updating platform parameters with conflicting name raises error."""

    # Create two platform configurations
    await storage.create_platform_params(sample_openai_platform_params)
    await storage.create_platform_params(sample_azure_platform_params)

    # Try to update azure config to have the same name as openai config
    updated_azure = sample_azure_platform_params.model_copy(
        update={"name": sample_openai_platform_params.name}
    )

    with pytest.raises(
        PlatformConfigWithNameAlreadyExistsError,
        match=f"Platform params with name '{sample_openai_platform_params.name}' already exists",
    ):
        await storage.update_platform_params(
            sample_azure_platform_params.platform_id, updated_azure
        )


@pytest.mark.asyncio
async def test_update_platform_params_same_name_allowed(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test that updating platform parameters with the same name is allowed."""

    # Create platform params
    await storage.create_platform_params(sample_openai_platform_params)

    # Update with same name but different description should work
    updated_params = sample_openai_platform_params.model_copy(
        update={
            "name": sample_openai_platform_params.name,  # Same name
            "description": "Updated description",
        }
    )

    await storage.update_platform_params(sample_openai_platform_params.platform_id, updated_params)

    # Verify the update worked
    retrieved = await storage.get_platform_params(sample_openai_platform_params.platform_id)
    assert retrieved.description == "Updated description"


@pytest.mark.asyncio
async def test_delete_platform_params_not_found_error(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test that deleting non-existent platform parameters raises error."""

    non_existent_id = str(uuid4())

    with pytest.raises(
        PlatformConfigNotFoundError, match=f"Platform params {non_existent_id} not found"
    ):
        await storage.delete_platform_params(non_existent_id)


@pytest.mark.asyncio
async def test_platform_params_invalid_uuid_errors(
    storage: SQLiteStorage,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test that invalid UUIDs raise appropriate errors."""

    invalid_uuid = "not-a-uuid"

    # Test get with invalid platform_params_id
    with pytest.raises(InvalidUUIDError):
        await storage.get_platform_params(invalid_uuid)

    # Test update with invalid platform_params_id
    with pytest.raises(InvalidUUIDError):
        await storage.update_platform_params(invalid_uuid, sample_openai_platform_params)

    # Test delete with invalid platform_params_id
    with pytest.raises(InvalidUUIDError):
        await storage.delete_platform_params(invalid_uuid)


@pytest.mark.asyncio
async def test_platform_params_serialization_deserialization(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test that complex platform parameters are properly serialized and deserialized."""

    # Create a complex platform configuration with all possible fields
    complex_params = OpenAIPlatformParameters(
        name="Complex Config",
        description="A complex configuration with all fields",
        openai_api_key=SecretString("sk-test-key-123"),
        models={
            "OpenAI": ["gpt-4", "gpt-3.5-turbo", "text-embedding-ada-002"],
            "CustomProvider": ["custom-model-1", "custom-model-2"],
        },
        platform_id=str(uuid4()),
        # Let created_at and updated_at use their default factories
    )

    # Create and retrieve
    await storage.create_platform_params(complex_params)
    retrieved = await storage.get_platform_params(complex_params.platform_id)

    # Verify all fields are preserved
    assert retrieved.name == complex_params.name
    assert retrieved.description == complex_params.description
    assert retrieved.models == complex_params.models
    assert retrieved.kind == "openai"
    assert retrieved.platform_id == complex_params.platform_id
    # Note: dates might be slightly different due to serialization, so we just check they exist
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None


@pytest.mark.asyncio
async def test_platform_params_list_ordering(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test that listing platform parameters returns them in created_at DESC order."""

    # Create multiple platform configurations with slight delays
    import asyncio

    params1 = OpenAIPlatformParameters(
        name="First Config",
        openai_api_key=SecretString("key1"),
        platform_id=str(uuid4()),
    )
    await storage.create_platform_params(params1)

    await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

    params2 = OpenAIPlatformParameters(
        name="Second Config",
        openai_api_key=SecretString("key2"),
        platform_id=str(uuid4()),
    )
    await storage.create_platform_params(params2)

    await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

    params3 = OpenAIPlatformParameters(
        name="Third Config",
        openai_api_key=SecretString("key3"),
        platform_id=str(uuid4()),
    )
    await storage.create_platform_params(params3)

    # List should return in reverse chronological order (newest first)
    params_list = await storage.list_platform_params()
    assert len(params_list) == 3

    # The most recently created should be first
    assert params_list[0].name == "Third Config"
    assert params_list[1].name == "Second Config"
    assert params_list[2].name == "First Config"


@pytest.mark.asyncio
async def test_platform_params_json_serialization_edge_cases(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test edge cases in JSON serialization for SQLite."""

    # Test with None values and empty collections
    edge_case_params = OpenAIPlatformParameters(
        name="Edge Case Config",
        description=None,  # None description
        openai_api_key=SecretString("test-key"),
        models=None,  # None models
        platform_id=str(uuid4()),
    )

    # Create and retrieve
    await storage.create_platform_params(edge_case_params)
    retrieved = await storage.get_platform_params(edge_case_params.platform_id)

    # Verify None values are handled correctly
    assert retrieved.name == "Edge Case Config"
    assert retrieved.description is None
    assert retrieved.kind == "openai"

    # We will auto-populate the allowlist when empty to
    # what server used to default to for this platform
    assert retrieved.models == {"openai": ["gpt-4-1"]}


@pytest.mark.asyncio
async def test_platform_params_concurrent_operations(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test concurrent operations on platform parameters."""

    import asyncio

    # Create multiple configs concurrently
    async def create_config(i: int):
        params = OpenAIPlatformParameters(
            name=f"Concurrent Config {i}",
            openai_api_key=SecretString(f"key-{i}"),
            platform_id=str(uuid4()),
        )
        await storage.create_platform_params(params)
        return params

    # Create 5 configs concurrently
    tasks = [create_config(i) for i in range(5)]
    created_params = await asyncio.gather(*tasks)

    # Verify all were created
    params_list = await storage.list_platform_params()
    assert len(params_list) == 5

    # Verify all configs are present
    created_names = {p.name for p in created_params}
    retrieved_names = {p.name for p in params_list}
    assert created_names == retrieved_names


@pytest.mark.asyncio
async def test_platform_params_database_encryption(
    storage: SQLiteStorage,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test that data is encrypted in the database and can be decrypted on retrieval."""

    # Create platform params (this will use actual encryption)
    await storage.create_platform_params(sample_openai_platform_params)

    # Query the database directly to verify data is encrypted
    async with storage._cursor() as cur:
        await cur.execute(
            "SELECT enc_parameters FROM v2_platform_params WHERE platform_params_id = ?",
            (sample_openai_platform_params.platform_id,),
        )
        row = await cur.fetchone()
        assert row is not None

        encrypted_data = row[0]

        # Verify the encrypted data doesn't contain plaintext secrets
        assert "test-openai-key" not in encrypted_data
        assert sample_openai_platform_params.name not in encrypted_data

        # Verify it's a non-empty encrypted string
        assert isinstance(encrypted_data, str)
        assert len(encrypted_data) > 0

    # Verify we can retrieve and decrypt the data properly
    retrieved_params = await storage.get_platform_params(sample_openai_platform_params.platform_id)
    assert retrieved_params.platform_id == sample_openai_platform_params.platform_id
    assert retrieved_params.name == sample_openai_platform_params.name
    assert retrieved_params.models == sample_openai_platform_params.models


@pytest.mark.asyncio
async def test_platform_params_encryption_error_handling(
    storage: SQLiteStorage,
    sample_openai_platform_params: OpenAIPlatformParameters,
) -> None:
    """Test error handling when encryption/decryption fails."""

    # Test encryption failure during create
    with patch.object(storage, "_secret_manager") as mock_secret_manager:
        mock_secret_manager.store.side_effect = RuntimeError("Encryption failed")

        with pytest.raises(RuntimeError, match="Encryption failed"):
            await storage.create_platform_params(sample_openai_platform_params)

    # Create a platform config successfully first
    await storage.create_platform_params(sample_openai_platform_params)

    # Test decryption failure during get
    with patch.object(storage, "_secret_manager") as mock_secret_manager:
        mock_secret_manager.fetch.side_effect = RuntimeError("Decryption failed")

        with pytest.raises(RuntimeError, match="Decryption failed"):
            await storage.get_platform_params(sample_openai_platform_params.platform_id)
