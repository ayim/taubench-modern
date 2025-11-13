import uuid


def _make_payload(provider: str = "grafana", *, api_key: str = "secret-key-1") -> dict:
    if provider == "grafana":
        provider_settings = {
            "url": "https://example.com/v1/traces",
            "api_key": api_key,
            "custom_attributes": {"environment": "test"},
        }
    elif provider == "langsmith":
        provider_settings = {
            "url": "https://api.langsmith.example.com",
            "api_key": api_key,
            "project_name": "default",
        }
    else:
        raise ValueError(f"Unsupported provider for test payload: {provider}")

    return {
        "kind": "observability",
        "settings": {
            "kind": provider,
            "is_enabled": True,
            "provider_settings": provider_settings,
        },
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
    assert settings["kind"] == "grafana"
    assert settings["is_enabled"] is True
    assert settings["provider_settings"]["url"] == "https://example.com/v1/traces"
    assert settings["provider_settings"]["custom_attributes"] == {"environment": "test"}
    assert settings["provider_settings"]["api_key"] == "**********"


def test_list_integrations_with_filter(client):
    payload_a = _make_payload(provider="grafana")
    payload_b = _make_payload(provider="langsmith")

    assert client.post("/api/v2/observability/integrations", json=payload_a).status_code == 201
    assert client.post("/api/v2/observability/integrations", json=payload_b).status_code == 201

    resp_all = client.get("/api/v2/observability/integrations")
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 2

    resp_filtered = client.get(
        "/api/v2/observability/integrations", params={"provider": "langsmith"}
    )
    assert resp_filtered.status_code == 200
    data = resp_filtered.json()
    assert len(data) == 1
    assert data[0]["settings"]["kind"] == "langsmith"


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
            "kind": "grafana",
            "is_enabled": False,
            "provider_settings": {
                "url": "https://updated.example.com/v1/traces",
                "api_key": "updated-key",
                "custom_attributes": {"service": "demo"},
            },
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
    assert data["settings"]["kind"] == "grafana"
    assert data["settings"]["is_enabled"] is False
    assert data["settings"]["provider_settings"]["url"] == "https://updated.example.com/v1/traces"
    assert data["settings"]["provider_settings"]["custom_attributes"] == {"service": "demo"}
    assert data["settings"]["provider_settings"]["api_key"] == "**********"

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


def test_validate_integration_placeholder_response(client):
    create_resp = client.post("/api/v2/observability/integrations", json=_make_payload())
    integration_id = create_resp.json()["id"]

    override_payload = {"url": "https://override.example.com/v1/traces"}

    validate_resp = client.post(
        f"/api/v2/observability/integrations/{integration_id}/validate",
        json=override_payload,
    )
    assert validate_resp.status_code == 200
    data = validate_resp.json()
    assert data["success"] is False
    assert "Validation logic not implemented yet." in data["message"]
    assert data["details"]["kind"] == "grafana"
    assert data["details"]["override"] == override_payload

    missing_resp = client.post(
        f"/api/v2/observability/integrations/{uuid.uuid4()}/validate",
        json=override_payload,
    )
    assert missing_resp.status_code == 404
