"""Tests for Azure Foundry client.

These tests verify critical SDK mapping and platform-specific behavior.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.platforms.azure_foundry.client import AzureFoundryClient
from agent_platform.core.platforms.azure_foundry.parameters import (
    AzureFoundryPlatformParameters,
)


@pytest.fixture
def azure_foundry_parameters() -> AzureFoundryPlatformParameters:
    return AzureFoundryPlatformParameters(
        endpoint_url="https://test-resource.services.ai.azure.com/v1/messages",
        api_key="test-api-key",
        deployment_name="claude-4-5-sonnet",
    )


class TestAzureFoundryClientSdkMapping:
    """Tests to verify our field names map correctly to SDK arguments."""

    @pytest.mark.asyncio
    async def test_sdk_args_mapping(
        self,
        azure_foundry_parameters: AzureFoundryPlatformParameters,
    ) -> None:
        """Verify our field names map to SDK's expected args.

        CRITICAL: This catches field name drift between our params and SDK.
        We use endpoint_url but SDK expects 'base_url' (via get_base_url()).
        """
        client = AzureFoundryClient(parameters=azure_foundry_parameters)

        with patch("anthropic.AsyncAnthropicFoundry") as mock_sdk:
            mock_instance = MagicMock()
            mock_sdk.return_value = mock_instance

            await client._get_client()

            mock_sdk.assert_called_once_with(
                api_key="test-api-key",
                base_url="https://test-resource.services.ai.azure.com",
            )

    @pytest.mark.asyncio
    async def test_missing_endpoint_url_raises_error(self) -> None:
        """Verify error when endpoint URL is missing."""
        params = AzureFoundryPlatformParameters(
            endpoint_url=None,
            api_key="test-key",
        )
        client = AzureFoundryClient(parameters=params)

        with pytest.raises(PlatformHTTPError) as exc_info:
            await client._get_client()

        assert exc_info.value.response.code == "bad_request"
        assert "endpoint url" in exc_info.value.response.message.lower()


class TestAzureFoundryEmbeddings:
    """Tests for embeddings functionality."""

    @pytest.mark.asyncio
    async def test_embeddings_not_supported(
        self,
        azure_foundry_parameters: AzureFoundryPlatformParameters,
    ) -> None:
        """Verify embeddings raise NotImplementedError for Anthropic models."""
        client = AzureFoundryClient(parameters=azure_foundry_parameters)

        with pytest.raises(NotImplementedError, match="not supported"):
            await client.create_embeddings(["test text"], "claude-4-5-sonnet")
