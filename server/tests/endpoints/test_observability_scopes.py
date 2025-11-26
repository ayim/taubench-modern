"""Tests for observability integration scope REST API endpoints.

Note: These tests focus on the API contract for global scopes.
Agent scope functionality is comprehensively tested in the storage layer tests
(test_integration_scopes.py), which properly set up agent fixtures.
"""

from agent_platform.server.api.private_v2.observability.models import (
    IntegrationScopeResponse,
)


def _create_test_integration(client) -> str:
    """Helper to create a test integration via API and return its ID."""
    payload = {
        "settings": {
            "provider": "grafana",
            "url": "https://example.com/v1/traces",
            "api_token": "glc_test-key",
            "grafana_instance_id": "123456",
            "is_enabled": True,
        },
        "description": "Test integration for scopes",
        "version": "1.0.0",
    }
    response = client.post("/api/v2/observability/integrations", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_set_global_scope(client):
    """Test setting an integration to global scope via API."""
    integration_id = _create_test_integration(client)

    response = client.post(
        f"/api/v2/observability/integrations/{integration_id}/scopes",
        json={"scope": "global", "agent_id": None},
    )
    assert response.status_code == 201
    scope = IntegrationScopeResponse.model_validate(response.json())
    assert scope.scope == "global"
    assert scope.agent_id is None
    assert scope.integration_id == integration_id


def test_list_integration_scopes(client):
    """Test listing scope assignments via API."""
    integration_id = _create_test_integration(client)

    # Assign a scope
    client.post(
        f"/api/v2/observability/integrations/{integration_id}/scopes",
        json={"scope": "global", "agent_id": None},
    )

    # List scopes
    response = client.get(f"/api/v2/observability/integrations/{integration_id}/scopes")
    assert response.status_code == 200
    scopes = [IntegrationScopeResponse.model_validate(s) for s in response.json()]
    assert len(scopes) == 1
    assert scopes[0].scope == "global"


def test_delete_global_scope(client):
    """Test deleting a global scope assignment via API."""
    integration_id = _create_test_integration(client)

    # Set a global scope
    client.post(
        f"/api/v2/observability/integrations/{integration_id}/scopes",
        json={"scope": "global", "agent_id": None},
    )

    # Delete global scope with explicit scope parameter
    response = client.delete(
        f"/api/v2/observability/integrations/{integration_id}/scopes",
        params={"scope": "global", "agent_id": None},
    )
    assert response.status_code == 204

    # Verify it's gone
    response = client.get(f"/api/v2/observability/integrations/{integration_id}/scopes")
    scopes = response.json()
    assert len(scopes) == 0
