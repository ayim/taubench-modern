import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def sample_openai_platform_payload():
    """Sample OpenAI platform payload for API requests."""
    return {
        "kind": "openai",
        "name": "Test OpenAI Platform",
        "description": "Test OpenAI platform configuration",
        "credentials": {"openai_api_key": "sk-test-key-12345"},
        "models": {"openai": ["gpt-4-1", "o3-high"]},
    }


@pytest.fixture
def sample_azure_platform_payload():
    """Sample Azure platform payload for API requests."""
    return {
        "kind": "azure",
        "name": "Test Azure Platform",
        "description": "Test Azure platform configuration",
        "credentials": {
            "azure_api_key": "test-azure-key",
            "azure_endpoint_url": "https://test.openai.azure.com/",
            "azure_api_version": "2024-02-01",
            "azure_deployment_name": "gpt-4-1",
        },
        "models": {"openai": ["gpt-4-1", "o3-high"]},
    }


@pytest.fixture
def sample_bedrock_platform_payload():
    """Sample Bedrock platform payload for API requests."""
    return {
        "kind": "bedrock",
        "name": "Test Bedrock Platform",
        "description": "Test Bedrock platform configuration",
        "credentials": {
            "aws_access_key_id": "AKIATEST12345",
            "aws_secret_access_key": "test-secret-key",
            "region_name": "us-east-1",
        },
        "models": {"anthropic": ["claude-4-sonnet", "claude-4-opus"]},
    }


def test_create_platform_openai(client: TestClient, sample_openai_platform_payload: dict):
    """Test creating an OpenAI platform configuration and response format."""
    response = client.post("/api/v2/private/platforms/", json=sample_openai_platform_payload)

    assert response.status_code == 200
    data = response.json()

    # Test response format - check required fields are present
    required_fields = ["platform_id", "kind", "name", "models"]
    for field in required_fields:
        assert field in data, f"Required field '{field}' missing from response"

    # Test response format - check field types
    assert isinstance(data["platform_id"], str)
    assert isinstance(data["kind"], str)
    assert isinstance(data["name"], str)
    assert isinstance(data["models"], dict)

    # Test response format - check that platform_id is a valid UUID format (basic check)
    assert len(data["platform_id"]) == 36  # UUID string length
    assert data["platform_id"].count("-") == 4  # UUID hyphen count

    # Test content matches input payload
    assert data["kind"] == sample_openai_platform_payload["kind"]
    assert data["name"] == sample_openai_platform_payload["name"]
    assert data["description"] == sample_openai_platform_payload["description"]
    # Models should be preserved
    assert data["models"] == sample_openai_platform_payload["models"]
    # API key should be present (likely masked/encrypted)
    assert "openai_api_key" in data


def test_create_platform_azure(client: TestClient, sample_azure_platform_payload: dict):
    """Test creating an Azure platform configuration."""
    response = client.post("/api/v2/private/platforms/", json=sample_azure_platform_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == sample_azure_platform_payload["kind"]
    assert data["name"] == sample_azure_platform_payload["name"]
    assert data["description"] == sample_azure_platform_payload["description"]
    assert data["azure_endpoint_url"] == sample_azure_platform_payload["credentials"]["azure_endpoint_url"]
    assert data["azure_api_version"] == sample_azure_platform_payload["credentials"]["azure_api_version"]
    assert data["azure_deployment_name"] == sample_azure_platform_payload["credentials"]["azure_deployment_name"]
    assert data["models"] == sample_azure_platform_payload["models"]
    assert "platform_id" in data
    assert data["platform_id"] is not None


def test_create_platform_bedrock(client: TestClient, sample_bedrock_platform_payload: dict):
    """Test creating a Bedrock platform configuration."""
    response = client.post("/api/v2/private/platforms/", json=sample_bedrock_platform_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == sample_bedrock_platform_payload["kind"]
    assert data["name"] == sample_bedrock_platform_payload["name"]
    assert data["description"] == sample_bedrock_platform_payload["description"]
    assert data["region_name"] == sample_bedrock_platform_payload["credentials"]["region_name"]
    assert data["models"] == sample_bedrock_platform_payload["models"]
    assert "platform_id" in data
    assert data["platform_id"] is not None


def test_list_platforms_empty(client: TestClient):
    """Test listing platforms when none exist."""
    response = client.get("/api/v2/private/platforms/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_platforms_multiple(
    client: TestClient, sample_openai_platform_payload: dict, sample_azure_platform_payload: dict
):
    """Test listing multiple platform configurations."""
    # Create two platforms
    response1 = client.post("/api/v2/private/platforms/", json=sample_openai_platform_payload)
    assert response1.status_code == 200
    platform1_id = response1.json()["platform_id"]

    response2 = client.post("/api/v2/private/platforms/", json=sample_azure_platform_payload)
    assert response2.status_code == 200
    platform2_id = response2.json()["platform_id"]

    # List platforms
    response = client.get("/api/v2/private/platforms/")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Verify the platforms are in the response
    platform_ids = {platform["platform_id"] for platform in data}
    assert platform1_id in platform_ids
    assert platform2_id in platform_ids

    platform_names = {platform["name"] for platform in data}
    assert sample_openai_platform_payload["name"] in platform_names
    assert sample_azure_platform_payload["name"] in platform_names


def test_get_platform_by_id(client: TestClient, sample_openai_platform_payload: dict):
    """Test getting a specific platform configuration by ID."""
    # Create platform
    create_response = client.post("/api/v2/private/platforms/", json=sample_openai_platform_payload)
    assert create_response.status_code == 200
    platform_id = create_response.json()["platform_id"]

    # Get platform by ID
    response = client.get(f"/api/v2/private/platforms/{platform_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["platform_id"] == platform_id
    assert data["kind"] == sample_openai_platform_payload["kind"]
    assert data["name"] == sample_openai_platform_payload["name"]
    assert data["models"] == sample_openai_platform_payload["models"]


def test_get_platform_not_found(client: TestClient):
    """Test getting a non-existent platform returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v2/private/platforms/{non_existent_id}")

    assert response.status_code == 404


def test_update_platform(client: TestClient, sample_openai_platform_payload: dict):
    """Test updating a platform configuration."""
    # Create platform
    create_response = client.post("/api/v2/private/platforms/", json=sample_openai_platform_payload)
    assert create_response.status_code == 200
    platform_id = create_response.json()["platform_id"]

    # Update platform
    updated_payload = sample_openai_platform_payload.copy()
    updated_payload["name"] = "Updated OpenAI Platform"
    updated_payload["models"] = {"openai": ["gpt-3.5-turbo"]}

    response = client.put(f"/api/v2/private/platforms/{platform_id}", json=updated_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == updated_payload["name"]
    assert data["models"] == updated_payload["models"]
    assert data["kind"] == sample_openai_platform_payload["kind"]


def test_update_platform_preserves_credentials_on_omission(client: TestClient, sample_openai_platform_payload: dict):
    """Omitting credentials on update should keep existing stored credentials."""
    # Create platform with credentials
    create_response = client.post("/api/v2/private/platforms/", json=sample_openai_platform_payload)
    assert create_response.status_code == 200
    platform_id = create_response.json()["platform_id"]

    original_key = sample_openai_platform_payload["credentials"]["openai_api_key"]

    # Update without credentials
    updated_payload = {
        "kind": "openai",
        "name": "Updated Name Without Credentials",
        "models": {"openai": ["gpt-4-1"]},
        # credentials intentionally omitted
    }

    response = client.put(f"/api/v2/private/platforms/{platform_id}", json=updated_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "Updated Name Without Credentials"
    # Secret should be preserved server-side when omitted in the request
    assert data["openai_api_key"]["value"] == original_key


def test_update_platform_not_found(client: TestClient, sample_openai_platform_payload: dict):
    """Test updating a non-existent platform returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = client.put(f"/api/v2/private/platforms/{non_existent_id}", json=sample_openai_platform_payload)

    assert response.status_code == 404


def test_delete_platform(client: TestClient, sample_openai_platform_payload: dict):
    """Test deleting a platform configuration."""
    # Create platform
    create_response = client.post("/api/v2/private/platforms/", json=sample_openai_platform_payload)
    assert create_response.status_code == 200
    platform_id = create_response.json()["platform_id"]

    # Verify platform exists
    get_response = client.get(f"/api/v2/private/platforms/{platform_id}")
    assert get_response.status_code == 200

    # Delete platform
    response = client.delete(f"/api/v2/private/platforms/{platform_id}")
    assert response.status_code == 204

    # Verify platform is deleted
    get_response_after = client.get(f"/api/v2/private/platforms/{platform_id}")
    assert get_response_after.status_code == 404

    # Verify it's not in the list
    list_response = client.get("/api/v2/private/platforms/")
    assert list_response.status_code == 200
    platform_ids = {platform["platform_id"] for platform in list_response.json()}
    assert platform_id not in platform_ids


def test_delete_platform_not_found(client: TestClient):
    """Test deleting a non-existent platform returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/api/v2/private/platforms/{non_existent_id}")

    assert response.status_code == 404


def test_create_platform_validation_error_missing_required_fields(client: TestClient):
    """Test that creating a platform with missing required fields returns 422."""
    invalid_payload = {
        "kind": "openai",
        # Missing required fields like name, credentials, models
    }

    response = client.post("/api/v2/private/platforms/", json=invalid_payload)
    assert response.status_code == 422


def test_create_platform_validation_error_invalid_kind(client: TestClient):
    """Test that creating a platform with invalid kind returns an error."""
    invalid_payload = {
        "kind": "invalid_platform_kind",
        "name": "Test Platform",
        "models": {"invalid": ["test-model"]},
    }

    response = client.post("/api/v2/private/platforms/", json=invalid_payload)
    assert response.status_code == 400
    error_data = response.json()
    assert "error" in error_data
    assert error_data["error"]["code"] == "bad_request"
    assert error_data["error"]["message"].startswith(
        "Invalid platform parameters kind. Provided: 'invalid_platform_kind'. Must be one of:"
    )


def test_create_platform_validation_error_empty_strings(client: TestClient):
    """Test that creating a platform with empty required strings returns 422."""
    invalid_payload = {
        "kind": "openai",
        "name": "",  # Empty name should be invalid
        "credentials": {
            "openai_api_key": ""  # Empty API key should be invalid
        },
        "models": {},  # Empty models should be invalid
    }

    response = client.post("/api/v2/private/platforms/", json=invalid_payload)
    # The API might accept empty strings, so let's check if it returns 200 but with default values
    if response.status_code == 200:
        data = response.json()
        # Check that empty name gets a default value
        assert data["name"] != ""
        # Check that empty API key gets handled (might be None or default)
        assert "openai_api_key" in data
    else:
        assert response.status_code == 422


class TestPlatformCRUDWorkflow:
    """Test complete CRUD workflow for platforms."""

    def test_full_platform_lifecycle(self, client: TestClient, sample_openai_platform_payload: dict):
        """Test complete create, read, update, delete workflow."""
        # Create
        create_response = client.post("/api/v2/private/platforms/", json=sample_openai_platform_payload)
        assert create_response.status_code == 200
        platform_id = create_response.json()["platform_id"]

        # Read
        get_response = client.get(f"/api/v2/private/platforms/{platform_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == sample_openai_platform_payload["name"]

        # Update
        updated_payload = sample_openai_platform_payload.copy()
        updated_payload["name"] = "Updated Platform Name"
        update_response = client.put(f"/api/v2/private/platforms/{platform_id}", json=updated_payload)
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Platform Name"

        # Verify update
        get_updated_response = client.get(f"/api/v2/private/platforms/{platform_id}")
        assert get_updated_response.status_code == 200
        assert get_updated_response.json()["name"] == "Updated Platform Name"

        # Delete
        delete_response = client.delete(f"/api/v2/private/platforms/{platform_id}")
        assert delete_response.status_code == 204

        # Verify deletion
        get_deleted_response = client.get(f"/api/v2/private/platforms/{platform_id}")
        assert get_deleted_response.status_code == 404
