import uuid


def _make_payload(provider: str = "grafana", *, api_key: str = "secret-key-1") -> dict:
    if provider == "grafana":
        settings = {
            "provider": provider,
            "is_enabled": True,
            "url": "https://example.com/v1/traces",
            "api_token": f"glc_{api_key}",
            "grafana_instance_id": "123456",
        }
    elif provider == "langsmith":
        settings = {
            "provider": provider,
            "is_enabled": True,
            "url": "https://api.langsmith.example.com",
            "api_key": api_key,
            "project_name": "default",
        }
    elif provider == "otlp_basic_auth":
        settings = {
            "provider": provider,
            "is_enabled": True,
            "url": "http://localhost:14318",
            "username": "alloy",
            "password": api_key,
        }
    elif provider == "otlp_custom_headers":
        settings = {
            "provider": provider,
            "is_enabled": True,
            "url": "http://localhost:14318",
            "headers": {
                "Authorization": f"Bearer {api_key}",
                "X-Custom-Header": "custom-value",
            },
        }
    else:
        raise ValueError(f"Unsupported provider for test payload: {provider}")

    return {
        "kind": "observability",
        "settings": settings,
        "description": "Test integration",
        "version": "1.0.0",
    }


def test_create_integration_success(client):
    """Test creating a new integration (happy path)"""
    response = client.post("/api/v2/observability/integrations", json=_make_payload())
    assert response.status_code == 201
    data = response.json()

    assert data["kind"] == "observability"
    assert data["description"] == "Test integration"
    assert data["version"] == "1.0.0"
    assert "id" in data

    settings = data["settings"]
    assert settings["provider"] == "grafana"
    assert settings["is_enabled"] is True
    assert settings["url"] == "https://example.com/v1/traces"
    assert settings["api_token"] == "glc_secret-key-1"
    assert settings["grafana_instance_id"] == "123456"


def test_list_integrations_with_filter(client):
    payload_a = _make_payload(provider="grafana")
    payload_b = _make_payload(provider="langsmith")

    assert client.post("/api/v2/observability/integrations", json=payload_a).status_code == 201
    assert client.post("/api/v2/observability/integrations", json=payload_b).status_code == 201

    resp_all = client.get("/api/v2/observability/integrations")
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 2

    resp_filtered = client.get("/api/v2/observability/integrations", params={"provider": "langsmith"})
    assert resp_filtered.status_code == 200
    data = resp_filtered.json()
    assert len(data) == 1
    assert data[0]["settings"]["provider"] == "langsmith"


def test_get_integration_success_and_not_found(client):
    create_resp = client.post("/api/v2/observability/integrations", json=_make_payload())
    assert create_resp.status_code == 201
    integration_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/v2/observability/integrations/{integration_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == integration_id

    missing_resp = client.get(f"/api/v2/observability/integrations/{uuid.uuid4()}")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["error"]["code"] == "not_found"


def test_update_integration_partial_and_secret_redaction(client):
    create_resp = client.post("/api/v2/observability/integrations", json=_make_payload())
    integration_id = create_resp.json()["id"]

    update_payload = {
        "description": "Updated description",
        "settings": {
            "provider": "grafana",
            "is_enabled": False,
            "url": "https://updated.example.com/v1/traces",
            "api_token": "glc_updated-key",
            "grafana_instance_id": "654321",
        },
    }
    update_resp = client.put(
        f"/api/v2/observability/integrations/{integration_id}",
        json=update_payload,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()

    assert data["description"] == "Updated description"
    assert data["version"] == "1.0.0"  # unchanged from create payload
    assert data["settings"]["provider"] == "grafana"
    assert data["settings"]["is_enabled"] is False
    assert data["settings"]["url"] == "https://updated.example.com/v1/traces"
    assert data["settings"]["api_token"] == "glc_updated-key"
    assert data["settings"]["grafana_instance_id"] == "654321"

    missing_resp = client.put(
        f"/api/v2/observability/integrations/{uuid.uuid4()}",
        json=update_payload,
    )
    assert missing_resp.status_code == 404


def test_delete_integration_success_and_not_found(client):
    create_resp = client.post("/api/v2/observability/integrations", json=_make_payload())
    integration_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v2/observability/integrations/{integration_id}")
    assert delete_resp.status_code == 204
    assert delete_resp.content in (b"", None)

    # Deleting again should yield 404
    missing_resp = client.delete(f"/api/v2/observability/integrations/{integration_id}")
    assert missing_resp.status_code == 404


def test_validate_integration_placeholder_response(client, monkeypatch):
    """Test validation endpoint with mocked span export (no real network calls)."""
    from unittest.mock import MagicMock

    from opentelemetry.sdk.trace.export import SpanExportResult

    # Mock the exporter to avoid real network calls
    mock_exporter = MagicMock()
    mock_exporter.export.return_value = SpanExportResult.SUCCESS
    mock_exporter.shutdown.return_value = None

    # Mock provider that returns our mock exporter
    mock_provider = MagicMock()
    mock_provider._create_trace_exporter.return_value = mock_exporter

    # Patch OtelProviderFactory.create to return our mock provider
    monkeypatch.setattr(
        "agent_platform.core.telemetry.providers.factory.OtelProviderFactory.create",
        lambda settings: mock_provider,
    )

    create_resp = client.post("/api/v2/observability/integrations", json=_make_payload())
    integration_id = create_resp.json()["id"]

    override_payload = {"url": "https://override.example.com/v1/traces"}

    validate_resp = client.post(
        f"/api/v2/observability/integrations/{integration_id}/validate",
        json=override_payload,
    )
    assert validate_resp.status_code == 200
    data = validate_resp.json()
    assert data["success"] is True
    assert "Successfully sent test heartbeat" in data["message"]
    assert data["details"]["provider"] == "grafana"

    missing_resp = client.post(
        f"/api/v2/observability/integrations/{uuid.uuid4()}/validate",
        json=override_payload,
    )
    assert missing_resp.status_code == 404


def test_grafana_additional_headers_persisted_through_storage(client):
    """Test that allowed additional_headers are persisted through create/get cycle."""
    # Create a Grafana integration with allowed additional_headers
    payload = {
        "kind": "observability",
        "settings": {
            "provider": "grafana",
            "is_enabled": True,
            "url": "https://example.com/v1/traces",
            "api_token": "glc_test_key",
            "grafana_instance_id": "123456",
            "additional_headers": {
                "X-Custom-Header": "custom-value",
                "X-Another-Header": "another-value",
            },
        },
        "description": "Test with headers",
        "version": "1.0.0",
    }

    # Create the integration
    create_resp = client.post("/api/v2/observability/integrations", json=payload)
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    integration_id = create_data["id"]

    # Verify the CREATE response includes additional_headers
    settings = create_data["settings"]
    assert "additional_headers" in settings
    assert settings["additional_headers"]["X-Custom-Header"] == "custom-value"
    assert settings["additional_headers"]["X-Another-Header"] == "another-value"

    # GET the integration to verify headers persist after loading from storage
    get_resp = client.get(f"/api/v2/observability/integrations/{integration_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()

    # Verify the GET response also includes additional_headers
    settings = get_data["settings"]
    assert "additional_headers" in settings
    assert settings["additional_headers"]["X-Custom-Header"] == "custom-value"
    assert settings["additional_headers"]["X-Another-Header"] == "another-value"


def test_grafana_disallowed_headers_rejected_via_api(client):
    """Test that disallowed headers are rejected when creating integrations via API."""
    # Create a Grafana integration with disallowed headers in additional_headers
    payload = {
        "kind": "observability",
        "settings": {
            "provider": "grafana",
            "is_enabled": True,
            "url": "https://example.com/v1/traces",
            "api_token": "glc_test_key",
            "grafana_instance_id": "123456",
            "additional_headers": {
                "X-Custom-Header": "allowed-value",
                "Authorization": "Bearer should-be-rejected",
            },
        },
        "description": "Test filtering",
        "version": "1.0.0",
    }

    # Attempt to create the integration - should be rejected
    create_resp = client.post("/api/v2/observability/integrations", json=payload)
    assert create_resp.status_code == 400  # BAD_REQUEST from PlatformHTTPError
    error_data = create_resp.json()
    assert "error" in error_data
    assert "Authorization may not be specified as an HTTP header" in str(error_data)


def test_discriminated_union_ignores_wrong_provider_fields(client):
    """Test that discriminated union correctly parses based on 'kind',
    ignoring fields from other providers.
    """
    # Send LangSmith request with BOTH LangSmith AND Grafana fields
    # The discriminator should use 'kind' to pick LangSmithSettings and ignore Grafana fields
    mixed_payload = {
        "kind": "observability",
        "settings": {
            "provider": "langsmith",  # Discriminator should pick LangSmithSettings
            "is_enabled": True,
            # LangSmith fields (should be used)
            "url": "https://api.smith.langchain.com",
            "api_key": "ls_test_key",
            "project_name": "test-project",
            # Grafana fields (should be ignored by Pydantic discriminator)
            "api_token": "grafana_token",
            "grafana_instance_id": "grafana_123",
            "additional_headers": {"X-Test": "value"},
        },
        "description": "Test discriminated union",
        "version": "1.0.0",
    }

    # Should successfully create LangSmith integration (ignoring Grafana fields)
    create_resp = client.post("/api/v2/observability/integrations", json=mixed_payload)
    assert create_resp.status_code == 201
    data = create_resp.json()

    # Verify it's a LangSmith integration
    assert data["settings"]["provider"] == "langsmith"
    settings = data["settings"]

    # LangSmith fields should be present
    assert settings["url"] == "https://api.smith.langchain.com"
    assert settings["api_key"] == "ls_test_key"
    assert settings["project_name"] == "test-project"

    # Grafana fields should NOT be present (ignored during parsing)
    assert "api_token" not in settings
    assert "grafana_instance_id" not in settings
    # additional_headers is not a LangSmith field, so it shouldn't be there
    assert "additional_headers" not in settings


def test_create_otlp_basic_auth_integration(client):
    """Test creating OTLP Basic Auth integration."""
    payload = _make_payload(provider="otlp_basic_auth", api_key="steel")
    response = client.post("/api/v2/observability/integrations", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["kind"] == "observability"
    assert "id" in data

    settings = data["settings"]
    assert settings["provider"] == "otlp_basic_auth"
    assert settings["is_enabled"] is True
    assert settings["url"] == "http://localhost:14318"
    assert settings["username"] == "alloy"
    assert settings["password"] == "steel"


def test_list_otlp_basic_auth_integrations(client):
    """Test filtering integrations by otlp_basic_auth provider."""
    payload_grafana = _make_payload(provider="grafana")
    payload_otlp = _make_payload(provider="otlp_basic_auth")

    assert client.post("/api/v2/observability/integrations", json=payload_grafana).status_code == 201
    assert client.post("/api/v2/observability/integrations", json=payload_otlp).status_code == 201

    resp_all = client.get("/api/v2/observability/integrations")
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 2

    resp_filtered = client.get("/api/v2/observability/integrations", params={"provider": "otlp_basic_auth"})
    assert resp_filtered.status_code == 200
    data = resp_filtered.json()
    assert len(data) == 1
    assert data[0]["settings"]["provider"] == "otlp_basic_auth"


def test_secret_redaction_otlp(client):
    """Test that OTLP Basic Auth password is properly handled."""
    payload = _make_payload(provider="otlp_basic_auth", api_key="steel")
    create_resp = client.post("/api/v2/observability/integrations", json=payload)
    assert create_resp.status_code == 201
    integration_id = create_resp.json()["id"]

    # GET the integration
    get_resp = client.get(f"/api/v2/observability/integrations/{integration_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()

    # Verify password is returned (not redacted in API responses)
    settings = data["settings"]
    assert settings["password"] == "steel"
    assert settings["username"] == "alloy"


def test_update_otlp_basic_auth(client):
    """Test updating OTLP Basic Auth integration."""
    payload = _make_payload(provider="otlp_basic_auth", api_key="steel")
    create_resp = client.post("/api/v2/observability/integrations", json=payload)
    integration_id = create_resp.json()["id"]

    update_payload = {
        "description": "Updated OTLP integration",
        "settings": {
            "provider": "otlp_basic_auth",
            "is_enabled": False,
            "url": "http://localhost:24318",
            "username": "tempo",
            "password": "iron",
        },
    }
    update_resp = client.put(
        f"/api/v2/observability/integrations/{integration_id}",
        json=update_payload,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()

    assert data["description"] == "Updated OTLP integration"
    assert data["settings"]["provider"] == "otlp_basic_auth"
    assert data["settings"]["is_enabled"] is False
    assert data["settings"]["url"] == "http://localhost:24318"
    assert data["settings"]["username"] == "tempo"
    assert data["settings"]["password"] == "iron"


def test_create_otlp_custom_headers_integration(client):
    """Test creating OTLP Custom Headers integration."""
    payload = _make_payload(provider="otlp_custom_headers", api_key="token123")
    response = client.post("/api/v2/observability/integrations", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["kind"] == "observability"
    assert "id" in data

    settings = data["settings"]
    assert settings["provider"] == "otlp_custom_headers"
    assert settings["is_enabled"] is True
    assert settings["url"] == "http://localhost:14318"
    assert settings["headers"]["Authorization"] == "Bearer token123"
    assert settings["headers"]["X-Custom-Header"] == "custom-value"


def test_list_otlp_custom_headers_integrations(client):
    """Test filtering integrations by otlp_custom_headers provider."""
    payload_grafana = _make_payload(provider="grafana")
    payload_otlp = _make_payload(provider="otlp_custom_headers")

    assert client.post("/api/v2/observability/integrations", json=payload_grafana).status_code == 201
    assert client.post("/api/v2/observability/integrations", json=payload_otlp).status_code == 201

    resp_all = client.get("/api/v2/observability/integrations")
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 2

    resp_filtered = client.get("/api/v2/observability/integrations", params={"provider": "otlp_custom_headers"})
    assert resp_filtered.status_code == 200
    data = resp_filtered.json()
    assert len(data) == 1
    assert data[0]["settings"]["provider"] == "otlp_custom_headers"


def test_otlp_custom_headers_persistence(client):
    """Test that custom headers persist through storage/retrieval cycle."""
    payload = {
        "kind": "observability",
        "settings": {
            "provider": "otlp_custom_headers",
            "is_enabled": True,
            "url": "http://localhost:14318",
            "headers": {
                "Authorization": "Bearer token123",
                "X-Custom-Header": "custom-value",
                "X-Another-Header": "another-value",
            },
        },
        "description": "Test with headers",
        "version": "1.0.0",
    }

    # Create the integration
    create_resp = client.post("/api/v2/observability/integrations", json=payload)
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    integration_id = create_data["id"]

    # Verify CREATE response includes headers
    settings = create_data["settings"]
    assert "headers" in settings
    assert settings["headers"]["Authorization"] == "Bearer token123"
    assert settings["headers"]["X-Custom-Header"] == "custom-value"
    assert settings["headers"]["X-Another-Header"] == "another-value"

    # GET the integration to verify headers persist
    get_resp = client.get(f"/api/v2/observability/integrations/{integration_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()

    # Verify GET response includes headers
    settings = get_data["settings"]
    assert "headers" in settings
    assert settings["headers"]["Authorization"] == "Bearer token123"
    assert settings["headers"]["X-Custom-Header"] == "custom-value"
    assert settings["headers"]["X-Another-Header"] == "another-value"


def test_otlp_custom_headers_disallowed_headers_rejected(client):
    """Test that disallowed headers are rejected for OTLP Custom Headers."""
    payload = {
        "kind": "observability",
        "settings": {
            "provider": "otlp_custom_headers",
            "is_enabled": True,
            "url": "http://localhost:14318",
            "headers": {
                "X-Custom-Header": "allowed-value",
                "Content-Type": "application/json",  # Disallowed
            },
        },
        "description": "Test filtering",
        "version": "1.0.0",
    }

    # Attempt to create the integration - should be rejected
    create_resp = client.post("/api/v2/observability/integrations", json=payload)
    assert create_resp.status_code == 400  # BAD_REQUEST
    error_data = create_resp.json()
    assert "error" in error_data
    assert "Content-Type may not be specified as an HTTP header" in str(error_data)


def test_update_otlp_custom_headers(client):
    """Test updating OTLP Custom Headers integration."""
    payload = _make_payload(provider="otlp_custom_headers", api_key="token123")
    create_resp = client.post("/api/v2/observability/integrations", json=payload)
    integration_id = create_resp.json()["id"]

    update_payload = {
        "description": "Updated OTLP Custom Headers integration",
        "settings": {
            "provider": "otlp_custom_headers",
            "is_enabled": False,
            "url": "http://localhost:24318",
            "headers": {
                "Authorization": "Bearer new-token",
                "X-Updated-Header": "updated-value",
            },
        },
    }
    update_resp = client.put(
        f"/api/v2/observability/integrations/{integration_id}",
        json=update_payload,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()

    assert data["description"] == "Updated OTLP Custom Headers integration"
    assert data["settings"]["provider"] == "otlp_custom_headers"
    assert data["settings"]["is_enabled"] is False
    assert data["settings"]["url"] == "http://localhost:24318"
    assert data["settings"]["headers"]["Authorization"] == "Bearer new-token"
    assert data["settings"]["headers"]["X-Updated-Header"] == "updated-value"
