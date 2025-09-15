import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def sample_postgres_data_connection():
    """Sample PostgreSQL data connection payload for API requests."""
    return {
        "name": "test-postgres-connection",
        "description": "Test PostgreSQL connection",
        "engine": "postgres",
        "configuration": {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
            "schema": "public",
            "sslmode": "require",
        },
    }


@pytest.fixture
def sample_mysql_data_connection():
    """Sample MySQL data connection payload for API requests."""
    return {
        "name": "test-mysql-connection",
        "description": "Test MySQL connection",
        "engine": "mysql",
        "configuration": {
            "host": "localhost",
            "port": 3306,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
            "ssl": True,
        },
    }


def test_create_data_connection(client: TestClient, sample_postgres_data_connection: dict):
    """Test creating a data connection via API."""
    response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == sample_postgres_data_connection["name"]
    assert data["description"] == sample_postgres_data_connection["description"]
    assert data["engine"] == sample_postgres_data_connection["engine"]
    assert data["configuration"] == sample_postgres_data_connection["configuration"]
    assert "id" in data
    assert data["id"] is not None


def test_create_data_connection_with_storage_error(
    client: TestClient, sample_postgres_data_connection: dict, storage
):
    """Test creating a data connection when storage operation fails."""
    with patch.object(storage, "set_data_connection", side_effect=Exception("Storage error")):
        response = client.post(
            "/api/v2/private/data-connections/", json=sample_postgres_data_connection
        )

    assert response.status_code == 500
    error_data = response.json()
    assert "Failed to create data connection" in error_data["error"]["message"]


def test_list_data_connections_empty(client: TestClient):
    """Test listing data connections when none exist."""
    response = client.get("/api/v2/private/data-connections/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_data_connections_multiple(
    client: TestClient, sample_postgres_data_connection: dict, sample_mysql_data_connection: dict
):
    """Test listing multiple data connections."""
    response1 = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )
    assert response1.status_code == 200

    response2 = client.post("/api/v2/private/data-connections/", json=sample_mysql_data_connection)
    assert response2.status_code == 200

    response = client.get("/api/v2/private/data-connections/")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    connection_names = {conn["name"] for conn in data}
    expected_names = {sample_postgres_data_connection["name"], sample_mysql_data_connection["name"]}
    assert connection_names == expected_names


def test_list_data_connections_with_storage_error(client: TestClient, storage):
    """Test listing data connections when storage operation fails."""
    with patch.object(storage, "get_data_connections", side_effect=Exception("Storage error")):
        response = client.get("/api/v2/private/data-connections/")

    assert response.status_code == 500
    error_data = response.json()
    assert "Failed to list data connections" in error_data["error"]["message"]


def test_get_data_connection_by_id(client: TestClient, sample_postgres_data_connection: dict):
    """Test getting a specific data connection by ID."""
    create_response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )
    assert create_response.status_code == 200
    connection_id = create_response.json()["id"]

    response = client.get(f"/api/v2/private/data-connections/{connection_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == connection_id
    assert data["name"] == sample_postgres_data_connection["name"]
    assert data["description"] == sample_postgres_data_connection["description"]
    assert data["engine"] == sample_postgres_data_connection["engine"]


def test_get_data_connection_not_found(client: TestClient):
    """Test getting a non-existent data connection returns 500 (storage error)."""
    non_existent_id = str(uuid.uuid4())
    response = client.get(f"/api/v2/private/data-connections/{non_existent_id}")

    assert response.status_code == 500
    error_data = response.json()
    assert "Failed to get data connection" in error_data["error"]["message"]


def test_get_data_connection_with_storage_error(
    client: TestClient, sample_postgres_data_connection: dict, storage
):
    """Test getting a data connection when storage operation fails."""
    create_response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )
    connection_id = create_response.json()["id"]

    with patch.object(storage, "get_data_connection", side_effect=Exception("Storage error")):
        response = client.get(f"/api/v2/private/data-connections/{connection_id}")

    assert response.status_code == 500
    error_data = response.json()
    assert "Failed to get data connection" in error_data["error"]["message"]


def test_update_data_connection(client: TestClient, sample_postgres_data_connection: dict):
    """Test updating a data connection."""
    create_response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )
    assert create_response.status_code == 200
    connection_id = create_response.json()["id"]

    updated_payload = {
        "name": "updated-postgres-connection",
        "description": "Updated PostgreSQL connection",
        "engine": "postgres",
        "configuration": {
            "host": "updated-host",
            "port": 5432,
            "database": "updateddb",
            "user": "updateduser",
            "password": "updatedpass",
            "schema": "public",
            "sslmode": "disable",
        },
    }

    response = client.put(f"/api/v2/private/data-connections/{connection_id}", json=updated_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "updated-postgres-connection"
    assert data["description"] == "Updated PostgreSQL connection"
    assert data["configuration"]["host"] == "updated-host"
    assert data["configuration"]["database"] == "updateddb"


def test_update_data_connection_with_storage_error(
    client: TestClient, sample_postgres_data_connection: dict, storage
):
    """Test updating a data connection when storage operation fails."""
    create_response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )
    connection_id = create_response.json()["id"]

    updated_payload = {
        "name": "updated-connection",
        "description": "Updated connection",
        "engine": "postgres",
        "configuration": sample_postgres_data_connection["configuration"],
    }

    with patch.object(storage, "update_data_connection", side_effect=Exception("Storage error")):
        response = client.put(
            f"/api/v2/private/data-connections/{connection_id}", json=updated_payload
        )

    assert response.status_code == 500
    error_data = response.json()
    assert "Failed to update data connection" in error_data["error"]["message"]


def test_delete_data_connection(client: TestClient, sample_postgres_data_connection: dict):
    """Test deleting a data connection."""
    create_response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )
    assert create_response.status_code == 200
    connection_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/v2/private/data-connections/{connection_id}")
    assert delete_response.status_code == 200

    get_response = client.get(f"/api/v2/private/data-connections/{connection_id}")
    assert get_response.status_code == 500


def test_delete_data_connection_with_storage_error(
    client: TestClient, sample_postgres_data_connection: dict, storage
):
    """Test deleting a data connection when storage operation fails."""
    create_response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )
    connection_id = create_response.json()["id"]

    with patch.object(storage, "delete_data_connection", side_effect=Exception("Storage error")):
        response = client.delete(f"/api/v2/private/data-connections/{connection_id}")

    assert response.status_code == 500
    error_data = response.json()
    assert "Failed to delete data connection" in error_data["error"]["message"]


def test_data_connection_validation_error(client: TestClient):
    """Test creating a data connection with invalid data returns 422."""
    invalid_payload = {
        "name": "test-connection",
        "description": "Test connection",
        "engine": "invalid-engine",
        "configuration": {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
        },
    }

    response = client.post("/api/v2/private/data-connections/", json=invalid_payload)
    assert response.status_code == 422


def test_data_connection_response_format(client: TestClient, sample_postgres_data_connection: dict):
    """Test the format of data connection responses."""
    create_response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )
    assert create_response.status_code == 200
    created_data = create_response.json()

    expected_fields = ["id", "name", "description", "engine", "configuration"]
    for field in expected_fields:
        assert field in created_data

    assert created_data["name"] == sample_postgres_data_connection["name"]
    assert created_data["description"] == sample_postgres_data_connection["description"]
    assert created_data["engine"] == sample_postgres_data_connection["engine"]
    assert created_data["configuration"] == sample_postgres_data_connection["configuration"]

    connection_id = created_data["id"]

    get_response = client.get(f"/api/v2/private/data-connections/{connection_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()

    for field in expected_fields:
        assert field in get_data

    assert get_data["id"] == connection_id
    assert get_data["name"] == sample_postgres_data_connection["name"]
