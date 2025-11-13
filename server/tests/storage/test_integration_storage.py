"""Unit tests for integration storage methods."""

from uuid import uuid4

import pytest

from agent_platform.core.data_connections import DataConnection
from agent_platform.core.document_intelligence.integrations import IntegrationKind
from agent_platform.core.integrations import Integration
from agent_platform.core.integrations.settings.data_server import (
    DataServerEndpoint,
    DataServerSettings,
)
from agent_platform.core.integrations.settings.reducto import ReductoSettings
from agent_platform.core.payloads.data_connection import (
    DataConnectionTag,
    MySQLDataConnectionConfiguration,
    PostgresDataConnectionConfiguration,
    SQLiteDataConnectionConfiguration,
)
from agent_platform.server.storage.errors import IntegrationNotFoundError


@pytest.mark.asyncio
async def test_integration_crud_operations(storage) -> None:
    """Test create, get, list, upsert, and delete operations for integrations."""

    integration_id = str(uuid4())
    data_server_settings = DataServerSettings(
        username="test_user",
        password="secret_password_123",
        endpoints=[DataServerEndpoint(host="api.dataserver.com", port=443, kind="http")],
    )
    reducto_settings = ReductoSettings(
        endpoint="https://reducto.com/api",
        api_key="secret_token_456",
        external_id="workspace_123",
    )

    data_server_integration = Integration(
        id=integration_id,
        kind="data_server",
        settings=data_server_settings,
        description="Primary data server",
        version="1",
    )

    await storage.upsert_integration(data_server_integration)

    fetched_integration = await storage.get_integration_by_kind(IntegrationKind.DATA_SERVER)
    assert fetched_integration.kind == IntegrationKind.DATA_SERVER
    assert fetched_integration.settings.model_dump() == data_server_settings.model_dump()
    assert fetched_integration.id == integration_id
    assert fetched_integration.description == "Primary data server"
    assert fetched_integration.version == "1"

    fetched_by_id = await storage.get_integration(integration_id)
    assert fetched_by_id.id == integration_id

    integrations = await storage.list_integrations()
    assert len(integrations) == 1
    assert integrations[0].kind == IntegrationKind.DATA_SERVER

    updated_settings = DataServerSettings(
        username="updated_user",
        password="new_secret_password_789",
        endpoints=[DataServerEndpoint(host="new-api.dataserver.com", port=443, kind="http")],
    )
    updated_integration = Integration(
        id=integration_id,
        kind="data_server",
        settings=updated_settings,
        description="Primary data server",
        version="2",
    )
    await storage.upsert_integration(updated_integration)

    fetched_updated = await storage.get_integration_by_kind("data_server")
    assert fetched_updated.settings.model_dump() == updated_settings.model_dump()
    assert fetched_updated.version == "2"

    reducto_integration = Integration(
        id=str(uuid4()),
        kind="reducto",
        settings=reducto_settings,
        description="Agent level observability",
        version="beta",
    )
    await storage.upsert_integration(reducto_integration)

    all_integrations = await storage.list_integrations()
    assert len(all_integrations) == 2
    kinds = {integration.kind for integration in all_integrations}
    assert kinds == {IntegrationKind.DATA_SERVER, IntegrationKind.REDUCTO}

    filtered_data_server = await storage.list_integrations(kind="data_server")
    assert len(filtered_data_server) == 1
    assert filtered_data_server[0].version == "2"

    await storage.delete_integration(IntegrationKind.DATA_SERVER)

    remaining_integrations = await storage.list_integrations()
    assert len(remaining_integrations) == 1
    assert remaining_integrations[0].kind == IntegrationKind.REDUCTO

    await storage.delete_integration_by_id(reducto_integration.id)

    assert await storage.list_integrations() == []

    with pytest.raises(IntegrationNotFoundError):
        await storage.get_integration_by_kind(IntegrationKind.DATA_SERVER)

    with pytest.raises(IntegrationNotFoundError):
        await storage.delete_integration("non_existent_kind")

    with pytest.raises(IntegrationNotFoundError):
        await storage.delete_integration_by_id(str(uuid4()))


@pytest.mark.asyncio
async def test_integration_allows_multiple_same_kind(storage) -> None:
    """Test that duplicate kind rows are permitted for different integrations."""

    settings1 = DataServerSettings(
        username="user1",
        password="pass1",
        endpoints=[DataServerEndpoint(host="api1.com", port=443, kind="http")],
    )
    integration1 = Integration(
        id=str(uuid4()),
        kind="data_server",
        settings=settings1,
    )
    await storage.upsert_integration(integration1)

    settings2 = DataServerSettings(
        username="user2",
        password="pass2",
        endpoints=[DataServerEndpoint(host="api2.com", port=443, kind="http")],
    )
    integration2 = Integration(
        id=integration1.id,
        kind="data_server",
        settings=settings2,
    )

    await storage.upsert_integration(integration2)

    agent_settings = DataServerSettings(
        username="agent",
        password="agent-pass",
        endpoints=[DataServerEndpoint(host="api-agent.com", port=443, kind="http")],
    )
    agent_integration = Integration(
        id=str(uuid4()),
        kind="data_server",
        settings=agent_settings,
    )
    await storage.upsert_integration(agent_integration)

    another_agent_settings = DataServerSettings(
        username="second-agent",
        password="agent-pass-2",
        endpoints=[DataServerEndpoint(host="api-agent-2.com", port=443, kind="http")],
    )
    another_agent_integration = Integration(
        id=str(uuid4()),
        kind="data_server",
        settings=another_agent_settings,
    )
    await storage.upsert_integration(another_agent_integration)

    integrations = await storage.list_integrations()
    assert len(integrations) == 3

    assert any(i.id == integration1.id for i in integrations)
    assert {i.settings.model_dump_json() for i in integrations} == {
        settings2.model_dump_json(),
        agent_settings.model_dump_json(),
        another_agent_settings.model_dump_json(),
    }


@pytest.mark.asyncio
async def test_integration_settings_encryption(storage) -> None:
    """Test that integration settings are properly encrypted/decrypted."""

    sensitive_settings = ReductoSettings(
        endpoint="https://secure-api.com",
        api_key="very_secret_key_12345",
        external_id="secure_workspace",
    )

    integration = Integration(id=str(uuid4()), kind="reducto", settings=sensitive_settings)

    await storage.upsert_integration(integration)

    fetched = await storage.get_integration_by_kind("reducto")
    assert fetched.settings.model_dump() == sensitive_settings.model_dump()

    assert fetched.settings.endpoint == sensitive_settings.endpoint
    assert fetched.settings.api_key == sensitive_settings.api_key
    assert fetched.settings.external_id == sensitive_settings.external_id


@pytest.mark.asyncio
async def test_unknown_integration_kind_handling(storage) -> None:
    """Test that unknown integration kinds are handled gracefully without crashing."""

    from agent_platform.core.integrations.settings.unhandled import UnhandledIntegrationSettings

    unknown_settings_data = {
        "endpoint": "https://secure-service.com",
        "api_key": "secure_key_123",
        "custom_field": "custom_value",
        "version": "2.0",
    }

    unknown_integration = Integration(
        id=str(uuid4()),
        kind="secure_service",
        settings=UnhandledIntegrationSettings(
            kind="secure_service", raw_data=unknown_settings_data
        ),
    )

    await storage.upsert_integration(unknown_integration)

    fetched = await storage.get_integration_by_kind("secure_service")
    assert fetched.kind == "secure_service"
    assert isinstance(fetched.settings, UnhandledIntegrationSettings)
    assert fetched.settings.raw_data == unknown_settings_data

    all_integrations = await storage.list_integrations()
    secure_service_integrations = [i for i in all_integrations if i.kind == "secure_service"]
    assert len(secure_service_integrations) == 1
    assert secure_service_integrations[0].settings.raw_data == unknown_settings_data


@pytest.mark.asyncio
async def test_remove_data_connection_tag(storage) -> None:
    """Test that remove_data_connection_tag removes the specified tag from a data connection."""

    connection1 = DataConnection(
        id=str(uuid4()),
        external_id="ext-1",
        name="Connection 1",
        description="Test connection 1",
        engine="postgres",
        configuration=PostgresDataConnectionConfiguration(
            host="localhost",
            port=5432,
            database="testdb",
            user="testuser",
            password="testpass",
        ),
        tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE],
    )

    connection2 = DataConnection(
        id=str(uuid4()),
        external_id="ext-2",
        name="Connection 2",
        description="Test connection 2",
        engine="mysql",
        configuration=MySQLDataConnectionConfiguration(
            host="localhost",
            port=3306,
            database="testdb",
            user="testuser",
            password="testpass",
        ),
        tags=["other_tag"],
    )

    connection3 = DataConnection(
        id=str(uuid4()),
        external_id="ext-3",
        name="Connection 3",
        description="Test connection 3",
        engine="sqlite",
        configuration=SQLiteDataConnectionConfiguration(
            db_file="/tmp/test.db",
        ),
        tags=[],
    )

    await storage.set_data_connection(connection1)
    await storage.set_data_connection(connection2)
    await storage.set_data_connection(connection3)

    all_connections = await storage.get_data_connections()
    assert len(all_connections) == 3

    data_intel_connections = [
        c for c in all_connections if DataConnectionTag.DOCUMENT_INTELLIGENCE in c.tags
    ]
    assert len(data_intel_connections) == 1

    other_tag_connections = [c for c in all_connections if "other_tag" in c.tags]
    assert len(other_tag_connections) == 1

    untagged_connections = [c for c in all_connections if len(c.tags) == 0]
    assert len(untagged_connections) == 1

    await storage.remove_data_connection_tag(
        connection1.id, DataConnectionTag.DOCUMENT_INTELLIGENCE
    )

    all_connections_after = await storage.get_data_connections()
    assert len(all_connections_after) == 3

    data_intel_connections_after = [
        c for c in all_connections_after if DataConnectionTag.DOCUMENT_INTELLIGENCE in c.tags
    ]
    assert len(data_intel_connections_after) == 0

    other_tag_connections_after = [c for c in all_connections_after if "other_tag" in c.tags]
    assert len(other_tag_connections_after) == 1
