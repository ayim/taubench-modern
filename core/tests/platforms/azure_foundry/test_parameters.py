"""Tests for Azure Foundry platform parameters.

These tests verify field name consistency between frontend and backend,
which is critical for preventing field name drift.
"""

from agent_platform.core.platforms.azure_foundry.parameters import (
    AzureFoundryPlatformParameters,
)


class TestAzureFoundryFieldNameConsistency:
    """Tests for field name consistency - CRITICAL for frontend/backend sync."""

    def test_field_names_match_frontend(self) -> None:
        """These field names must match what frontend sends.

        CRITICAL: If any of these assertions fail, frontend/backend field names
        are out of sync. Frontend sends these exact field names in the credentials
        object (see llmSchemas.ts).
        """
        params = AzureFoundryPlatformParameters(
            endpoint_url="https://test-resource.services.ai.azure.com/v1/messages",
            api_key="test-api-key",
            deployment_name="claude-4-5-sonnet",
            model="claude-4-5-sonnet",
        )
        dumped = params.model_dump()

        # These field names must match frontend form schema in llmSchemas.ts
        assert "endpoint_url" in dumped
        assert "api_key" in dumped
        assert "deployment_name" in dumped
        assert "model" in dumped

        # Verify the values are correctly stored
        assert dumped["endpoint_url"] == "https://test-resource.services.ai.azure.com/v1/messages"
        assert dumped["api_key"] == "test-api-key"
        assert dumped["deployment_name"] == "claude-4-5-sonnet"
        assert dumped["model"] == "claude-4-5-sonnet"

    def test_kind_is_azure_foundry(self) -> None:
        """Verify the platform kind is correctly set."""
        params = AzureFoundryPlatformParameters(
            endpoint_url="https://test.services.ai.azure.com/v1/messages",
            api_key="key",
        )
        assert params.kind == "azure_foundry"
        dumped = params.model_dump()
        assert dumped["kind"] == "azure_foundry"

    def test_get_base_url_strips_suffix(self) -> None:
        """Verify get_base_url strips /v1/messages suffix."""
        params = AzureFoundryPlatformParameters(
            endpoint_url="https://my-resource.services.ai.azure.com/v1/messages",
            api_key="key",
        )
        assert params.get_base_url() == "https://my-resource.services.ai.azure.com"

    def test_get_base_url_no_suffix(self) -> None:
        """Verify get_base_url returns URL as-is when no /v1/messages suffix."""
        params = AzureFoundryPlatformParameters(
            endpoint_url="https://my-resource.services.ai.azure.com",
            api_key="key",
        )
        assert params.get_base_url() == "https://my-resource.services.ai.azure.com"

    def test_get_base_url_none(self) -> None:
        """Verify get_base_url returns None when endpoint_url is None."""
        params = AzureFoundryPlatformParameters(api_key="key")
        assert params.get_base_url() is None

    def test_model_sets_models_allowlist(self) -> None:
        """Verify that providing model sets the models allowlist."""
        params = AzureFoundryPlatformParameters(
            api_key="key",
            model="claude-4-5-opus",
        )
        assert params.models == {"anthropic": ["claude-4-5-opus"]}

    def test_backward_compat_model_validate(self) -> None:
        """Verify model_validate maps old azure_foundry_* field names."""
        params = AzureFoundryPlatformParameters.model_validate(
            {
                "azure_foundry_resource_name": "old-resource",
                "azure_foundry_api_key": "old-key",
                "azure_foundry_deployment_name": "old-deployment",
                "azure_foundry_api_version": "2025-01-01",
            }
        )
        assert params.endpoint_url == "old-resource"
        assert params.api_key == "old-key"
        assert params.deployment_name == "old-deployment"
