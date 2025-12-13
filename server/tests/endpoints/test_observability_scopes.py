"""Tests for observability integration scope REST API endpoints.

Note: These tests focus on the API contract for global scopes.
Agent scope functionality is comprehensively tested in the storage layer tests
(test_integration_scopes.py), which properly set up agent fixtures.
"""

from agent_platform.server.api.private_v2.observability.models import (
    IntegrationScopeResponse,
)


def _create_test_integration(client, is_enabled: bool = True) -> str:
    """Helper to create a test integration via API and return its ID."""
    payload = {
        "settings": {
            "provider": "grafana",
            "url": "https://example.com/v1/traces",
            "api_token": "glc_test-key",
            "grafana_instance_id": "123456",
            "is_enabled": is_enabled,
        },
        "description": "Test integration for scopes",
        "version": "1.0.0",
    }
    response = client.post("/api/v2/observability/integrations", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


# =============================================================================
# Auto-assignment Tests
# =============================================================================


def test_integration_gets_global_scope_on_create(client):
    """Test that creating an integration auto-assigns global scope."""
    integration_id = _create_test_integration(client, is_enabled=True)

    # Verify global scope was auto-assigned
    response = client.get(f"/api/v2/observability/integrations/{integration_id}/scopes")
    assert response.status_code == 200
    scopes = [IntegrationScopeResponse.model_validate(s) for s in response.json()]
    assert len(scopes) == 1
    assert scopes[0].scope == "global"
    assert scopes[0].agent_id is None


def test_disabled_integration_also_gets_global_scope(client):
    """Test that even disabled integrations get global scope on create."""
    integration_id = _create_test_integration(client, is_enabled=False)

    # Verify global scope was auto-assigned even for disabled integration
    response = client.get(f"/api/v2/observability/integrations/{integration_id}/scopes")
    assert response.status_code == 200
    scopes = [IntegrationScopeResponse.model_validate(s) for s in response.json()]
    assert len(scopes) == 1
    assert scopes[0].scope == "global"


def test_update_does_not_duplicate_scope(client):
    """Test that updating an integration doesn't duplicate the global scope."""
    integration_id = _create_test_integration(client, is_enabled=True)

    # Verify initial global scope
    response = client.get(f"/api/v2/observability/integrations/{integration_id}/scopes")
    assert len(response.json()) == 1

    # Update the integration
    update_payload = {
        "settings": {
            "provider": "grafana",
            "url": "https://example.com/v1/traces",
            "api_token": "glc_updated-key",
            "grafana_instance_id": "123456",
            "is_enabled": True,
        },
        "version": "2.0.0",
    }
    response = client.put(f"/api/v2/observability/integrations/{integration_id}", json=update_payload)
    assert response.status_code == 200

    # Verify still only one scope (no duplicate added)
    response = client.get(f"/api/v2/observability/integrations/{integration_id}/scopes")
    scopes = response.json()
    assert len(scopes) == 1


# =============================================================================
# Manual Scope Management Tests
# =============================================================================


def test_set_global_scope_idempotent(client):
    """Test that setting global scope is idempotent (can be called multiple times)."""
    # Create integration (already has global scope from auto-assignment)
    integration_id = _create_test_integration(client, is_enabled=True)

    # Try to set global scope again
    response = client.post(
        f"/api/v2/observability/integrations/{integration_id}/scopes",
        json={"scope": "global", "agent_id": None},
    )
    assert response.status_code == 201
    scope = IntegrationScopeResponse.model_validate(response.json())
    assert scope.scope == "global"

    # Still only one global scope
    response = client.get(f"/api/v2/observability/integrations/{integration_id}/scopes")
    scopes = response.json()
    assert len(scopes) == 1


def test_delete_global_scope(client):
    """Test deleting a global scope assignment via API."""
    integration_id = _create_test_integration(client, is_enabled=True)

    # Verify global scope exists from auto-assignment
    response = client.get(f"/api/v2/observability/integrations/{integration_id}/scopes")
    assert len(response.json()) == 1

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
