import pytest

from agent_platform.core.data_server.data_server import (
    DataServerDetails,
    DataServerEndpoint,
    DataServerEndpointKind,
)
from agent_platform.core.document_intelligence.integrations import (
    DocumentIntelligenceIntegration,
    IntegrationKind,
)
from agent_platform.core.utils import SecretString
from agent_platform.server.storage.errors import (
    DIDSConnectionDetailsNotFoundError,
    DocumentIntelligenceIntegrationNotFoundError,
)
from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.fixture
def sample_integration() -> DocumentIntelligenceIntegration:
    """Create a sample DocumentIntelligenceIntegration for testing."""
    return DocumentIntelligenceIntegration(
        kind=IntegrationKind.REDUCTO,
        endpoint="https://api.example.com/reducto",
        api_key=SecretString("test-api-key-123"),
    )


@pytest.fixture
def sample_data_server_details() -> DataServerDetails:
    """Create sample DIDS connection details for testing."""
    return DataServerDetails(
        username="test_user",
        password=SecretString("test_password"),
        data_server_endpoints=[
            DataServerEndpoint(host="localhost", port=8080, kind=DataServerEndpointKind.HTTP),
        ],
    )


@pytest.mark.asyncio
async def test_document_intelligence_integration_crud_operations(
    storage: SQLiteStorage,
    sample_integration: DocumentIntelligenceIntegration,
) -> None:
    """Test Create, Read, Update, and Delete operations for document intelligence integrations."""

    # Initially, there should be no integrations
    integrations = await storage.list_document_intelligence_integrations()
    assert len(integrations) == 0

    # Test getting non-existent integration raises error
    with pytest.raises(DocumentIntelligenceIntegrationNotFoundError):
        await storage.get_document_intelligence_integration("non-existent-kind")

    # Create (set) an integration
    await storage.set_document_intelligence_integration(sample_integration)

    # List should now return one integration
    integrations = await storage.list_document_intelligence_integrations()
    assert len(integrations) == 1
    retrieved_integration = integrations[0]

    # Verify the retrieved integration matches the original
    assert retrieved_integration.kind == sample_integration.kind
    assert retrieved_integration.endpoint == sample_integration.endpoint
    assert retrieved_integration.api_key.value == sample_integration.api_key.value

    # Test getting integration by kind
    integration_by_kind = await storage.get_document_intelligence_integration(
        sample_integration.kind
    )
    assert integration_by_kind.kind == sample_integration.kind
    assert integration_by_kind.endpoint == sample_integration.endpoint
    assert integration_by_kind.api_key.value == sample_integration.api_key.value

    # Test updating the integration
    updated_integration = DocumentIntelligenceIntegration(
        kind=IntegrationKind.REDUCTO,  # Same kind to update existing
        endpoint="https://api.updated.com/reducto",
        api_key=SecretString("updated-api-key-456"),
    )
    await storage.set_document_intelligence_integration(updated_integration)

    # Verify the update
    updated_retrieved = await storage.get_document_intelligence_integration(sample_integration.kind)
    assert updated_retrieved.endpoint == "https://api.updated.com/reducto"
    assert updated_retrieved.api_key.value == "updated-api-key-456"
    assert updated_retrieved.kind == sample_integration.kind

    # List should still return one integration
    integrations = await storage.list_document_intelligence_integrations()
    assert len(integrations) == 1

    # Test deleting the integration
    await storage.delete_document_intelligence_integration(sample_integration.kind)

    # List should now be empty
    integrations = await storage.list_document_intelligence_integrations()
    assert len(integrations) == 0

    # Getting deleted integration should raise error
    with pytest.raises(DocumentIntelligenceIntegrationNotFoundError):
        await storage.get_document_intelligence_integration(sample_integration.kind)

    # Deleting non-existent integration should raise error
    with pytest.raises(DocumentIntelligenceIntegrationNotFoundError):
        await storage.delete_document_intelligence_integration("non-existent-kind")


@pytest.mark.asyncio
async def test_integration_update_same_kind(
    storage: SQLiteStorage,
) -> None:
    """Test that setting an integration with the same kind updates the existing one."""

    # Create first integration
    integration1 = DocumentIntelligenceIntegration(
        kind=IntegrationKind.REDUCTO,
        endpoint="https://api1.example.com/reducto",
        api_key=SecretString("api-key-1"),
    )

    # Set first integration
    await storage.set_document_intelligence_integration(integration1)

    # List should return one integration
    integrations = await storage.list_document_intelligence_integrations()
    assert len(integrations) == 1

    # Create second integration with the same kind but different endpoint/key
    integration2 = DocumentIntelligenceIntegration(
        kind=IntegrationKind.REDUCTO,  # Same kind - should update existing
        endpoint="https://api2.example.com/reducto",
        api_key=SecretString("api-key-2"),
    )

    # Set second integration (should update, not create new)
    await storage.set_document_intelligence_integration(integration2)

    # List should still return only one integration (updated)
    integrations = await storage.list_document_intelligence_integrations()
    assert len(integrations) == 1

    # Verify the integration was updated to integration2's values
    retrieved = await storage.get_document_intelligence_integration(IntegrationKind.REDUCTO)
    assert retrieved.endpoint == "https://api2.example.com/reducto"
    assert retrieved.api_key.value == "api-key-2"
    assert retrieved.kind == IntegrationKind.REDUCTO


@pytest.mark.asyncio
async def test_dids_connection_details_crud_operations(
    storage: SQLiteStorage,
    sample_data_server_details: DataServerDetails,
) -> None:
    """Test Create, Read, Update, and Delete operations for DIDS connection details."""

    # Initially, there should be no connection details
    with pytest.raises(DIDSConnectionDetailsNotFoundError):
        await storage.get_dids_connection_details()

    # Test deleting non-existent connection details
    with pytest.raises(DIDSConnectionDetailsNotFoundError):
        await storage.delete_dids_connection_details()

    # Set connection details
    await storage.set_dids_connection_details(sample_data_server_details)

    # Get connection details
    retrieved_details = await storage.get_dids_connection_details()
    assert retrieved_details.username == sample_data_server_details.username
    assert retrieved_details.password is not None
    assert sample_data_server_details.password is not None
    assert retrieved_details.password_str == sample_data_server_details.password_str
    assert (
        retrieved_details.data_server_endpoints == sample_data_server_details.data_server_endpoints
    )

    # Update connection details
    updated_details = DataServerDetails(
        username="updated_user",
        password=SecretString("updated_password"),
        data_server_endpoints=[
            DataServerEndpoint(host="updated-host", port=9090, kind=DataServerEndpointKind.MYSQL),
        ],
    )
    await storage.set_dids_connection_details(updated_details)

    # Verify the update
    retrieved_updated = await storage.get_dids_connection_details()
    assert retrieved_updated.username == "updated_user"
    assert retrieved_updated.password is not None
    assert retrieved_updated.password_str == "updated_password"
    assert len(retrieved_updated.data_server_endpoints) == 1
    assert retrieved_updated.data_server_endpoints[0].host == "updated-host"
    assert retrieved_updated.data_server_endpoints[0].port == 9090
    assert retrieved_updated.data_server_endpoints[0].kind == DataServerEndpointKind.MYSQL

    # Delete connection details
    await storage.delete_dids_connection_details()

    # Getting deleted connection details should raise error
    with pytest.raises(DIDSConnectionDetailsNotFoundError):
        await storage.get_dids_connection_details()

    # Deleting already deleted connection details should raise error
    with pytest.raises(DIDSConnectionDetailsNotFoundError):
        await storage.delete_dids_connection_details()


@pytest.mark.asyncio
async def test_integration_with_special_characters(
    storage: SQLiteStorage,
) -> None:
    """Test integration with special characters in fields."""

    special_integration = DocumentIntelligenceIntegration(
        kind=IntegrationKind.REDUCTO,
        endpoint="https://api.example.com/path?param=value&other=123",
        api_key=SecretString("key-with-special-chars!@#$%^&*()"),
    )

    # Set integration
    await storage.set_document_intelligence_integration(special_integration)

    # Retrieve and verify
    retrieved = await storage.get_document_intelligence_integration(special_integration.kind)
    assert retrieved.endpoint == "https://api.example.com/path?param=value&other=123"
    assert retrieved.api_key.value == "key-with-special-chars!@#$%^&*()"


@pytest.mark.asyncio
async def test_integration_kind_uniqueness(
    storage: SQLiteStorage,
) -> None:
    """Test that integration kinds are unique and setting with the same kind updates."""

    # Create integration
    integration = DocumentIntelligenceIntegration(
        kind=IntegrationKind.REDUCTO,
        endpoint="https://api.example.com/original",
        api_key=SecretString("original-key"),
    )

    # Set the integration
    await storage.set_document_intelligence_integration(integration)

    # Create another integration with the same kind but different data
    updated_integration = DocumentIntelligenceIntegration(
        kind=IntegrationKind.REDUCTO,  # Same kind
        endpoint="https://api.example.com/updated",
        api_key=SecretString("updated-key"),
    )

    # Set should update the existing integration
    await storage.set_document_intelligence_integration(updated_integration)

    # Should still have only one integration
    integrations = await storage.list_document_intelligence_integrations()
    assert len(integrations) == 1

    # And it should have the updated data
    retrieved = await storage.get_document_intelligence_integration(IntegrationKind.REDUCTO)
    assert retrieved.endpoint == "https://api.example.com/updated"
    assert retrieved.api_key.value == "updated-key"
