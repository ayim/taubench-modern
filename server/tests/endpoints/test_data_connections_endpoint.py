import uuid
from pathlib import Path
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


@pytest.fixture
def sample_postgres_data_connection_with_tag():
    """Sample PostgreSQL data connection payload with tag for API requests."""
    return {
        "name": "test-postgres-connection-tagged",
        "description": "Test PostgreSQL connection with tag",
        "engine": "postgres",
        "tags": ["production"],
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
def sample_postgres_data_connection_with_whitespaces_in_connection_details():
    """Sample postges data connection payload with whitespaces in connection details."""
    return {
        "name": "test-postgres-connection-whitespaces",
        "description": "Test postgres connection with whitespaces in details",
        "engine": "postgres",
        "tags": ["production"],
        "configuration": {
            "host": " localhost ",
            "port": 5432,
            "database": " testdb ",
            "user": " testuser ",
            "password": " testpass ",
            "schema": " public ",
            "sslmode": "require",
        },
    }


@pytest.fixture
def sample_snowflake_data_connection_with_whitespaces_in_connection_details():
    """Sample snowflake data connection payload with whitespaces in connection details."""
    return {
        "name": "test-snowflake-connection-whitespaces",
        "description": "Test snowflake connection with whitespaces in details",
        "engine": "snowflake",
        "tags": ["production"],
        "configuration": {
            "user": " myuser ",
            "account": " myaccount ",
            "private_key_path": " /path/to/private_key ",
            "warehouse": " warehouse_name ",
            "database": " database_name ",
            "schema": " public ",
            "credential_type": "custom-key-pair",
            "private_key_passphrase": " mypassphrase ",
        },
    }


@pytest.fixture
def sample_sqlite_data_connection(tmp_path: Path):
    """Sample SQLite data connection payload for API requests."""
    import sqlite3

    db_file = tmp_path / "sample_sqlite_data_connection.db"

    # Create the sqlite database
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE user_and_country (user_id INTEGER, country TEXT)")
    conn.execute("INSERT INTO user_and_country (user_id, country) VALUES (1, 'England')")
    conn.execute("INSERT INTO user_and_country (user_id, country) VALUES (2, 'France')")
    conn.execute("INSERT INTO user_and_country (user_id, country) VALUES (3, 'Germany')")

    conn.execute("CREATE TABLE user_and_city (user_id INTEGER, city TEXT)")
    conn.execute("INSERT INTO user_and_city (user_id, city) VALUES (1, 'London')")
    conn.execute("INSERT INTO user_and_city (user_id, city) VALUES (2, 'Paris')")
    conn.execute("INSERT INTO user_and_city (user_id, city) VALUES (3, 'Berlin')")

    conn.commit()
    conn.close()

    return {
        "name": "sample-sqlite-connection",
        "description": "Test SQLite connection",
        "engine": "sqlite",
        "configuration": {
            "db_file": str(db_file),
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
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


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
    assert data["id"] == connection_id
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


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

    expected_fields = ["id", "name", "description", "engine", "configuration", "tags"]
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


def test_create_data_connection_with_tag(
    client: TestClient, sample_postgres_data_connection_with_tag: dict
):
    """Test creating a data connection with tag via API."""
    response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection_with_tag
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == sample_postgres_data_connection_with_tag["name"]
    assert data["description"] == sample_postgres_data_connection_with_tag["description"]
    assert data["engine"] == sample_postgres_data_connection_with_tag["engine"]
    assert data["tags"] == sample_postgres_data_connection_with_tag["tags"]
    assert data["configuration"] == sample_postgres_data_connection_with_tag["configuration"]
    assert "id" in data
    assert data["id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_create_data_connection_without_tag_has_empty_tag(
    client: TestClient, sample_postgres_data_connection: dict
):
    """Test creating a data connection without tag has empty tag field."""
    response = client.post(
        "/api/v2/private/data-connections/", json=sample_postgres_data_connection
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == []


def test_inspect_data_connection_success(client: TestClient, sample_sqlite_data_connection: dict):
    """Test inspecting a data connection successfully."""
    # Create a data connection first
    create_response = client.post(
        "/api/v2/private/data-connections/", json=sample_sqlite_data_connection
    )
    assert create_response.status_code == 200
    connection_id = create_response.json()["id"]

    response = client.post(
        f"/api/v2/private/data-connections/{connection_id}/inspect",
        json={"tables_to_inspect": None},
    )

    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    assert {"user_and_country", "user_and_city"} == {table["name"] for table in data["tables"]}
    coutry_table = next(table for table in data["tables"] if table["name"] == "user_and_country")
    city_table = next(table for table in data["tables"] if table["name"] == "user_and_city")
    assert {"user_id", "country"} == {column["name"] for column in coutry_table["columns"]}
    assert {"user_id", "city"} == {column["name"] for column in city_table["columns"]}


def test_create_postgres_data_connection_with_sanitized_connection_details(
    client: TestClient,
    sample_postgres_data_connection_with_whitespaces_in_connection_details: dict,
):
    """Test creating a postgres data connection with sanitized the connection details."""
    response = client.post(
        "/api/v2/private/data-connections/",
        json=sample_postgres_data_connection_with_whitespaces_in_connection_details,
    )

    assert response.status_code == 200
    data = response.json()
    sample = sample_postgres_data_connection_with_whitespaces_in_connection_details
    assert data["name"] == sample["name"]
    assert data["description"] == sample["description"]
    assert data["engine"] == sample["engine"]
    assert data["tags"] == sample["tags"]
    assert data["configuration"]["host"] == sample["configuration"]["host"].strip()
    assert data["configuration"]["user"] == sample["configuration"]["user"].strip()
    assert data["configuration"]["password"] == sample["configuration"]["password"]
    assert data["configuration"]["schema"] == sample["configuration"]["schema"].strip()
    assert "id" in data
    assert data["id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_create_snowflake_data_connection_with_sanitized_connection_details(
    client: TestClient,
    sample_snowflake_data_connection_with_whitespaces_in_connection_details: dict,
):
    """Test creating a snowflake data connection with sanitized connection details."""
    response = client.post(
        "/api/v2/private/data-connections/",
        json=sample_snowflake_data_connection_with_whitespaces_in_connection_details,
    )

    assert response.status_code == 200
    data = response.json()
    sample = sample_snowflake_data_connection_with_whitespaces_in_connection_details
    assert data["name"] == sample["name"]
    assert data["description"] == sample["description"]
    assert data["engine"] == sample["engine"]
    assert data["tags"] == sample["tags"]
    assert data["configuration"]["user"] == sample["configuration"]["user"].strip()
    assert data["configuration"]["account"] == sample["configuration"]["account"].strip()
    assert data["configuration"]["private_key_path"] == (
        sample["configuration"]["private_key_path"].strip()
    )
    assert data["configuration"]["warehouse"] == sample["configuration"]["warehouse"].strip()
    assert data["configuration"]["database"] == sample["configuration"]["database"].strip()
    assert data["configuration"]["credential_type"] == (
        sample["configuration"]["credential_type"].strip()
    )
    assert data["configuration"]["database"] == sample["configuration"]["database"].strip()
    assert data["configuration"]["schema"] == sample["configuration"]["schema"].strip()
    assert (
        data["configuration"]["private_key_passphrase"]
        == (sample["configuration"]["private_key_passphrase"])
    )
    assert "id" in data
    assert data["id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
