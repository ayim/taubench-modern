"""Unit tests for the AzureOpenAI platform configs."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.azure.configs import (
    AzureOpenAIModelMap,
    AzureOpenAIPlatformConfigs,
)


class TestAzureOpenAIModelMap:
    """Tests for the AzureOpenAI model map."""

    def test_default(self) -> None:
        """Test that the default model map contains the expected mappings."""
        # Check that the default map contains mappings for key models
        assert "gpt-4o" in AzureOpenAIModelMap.model_aliases
        assert "gpt-4-turbo" in AzureOpenAIModelMap.model_aliases
        assert "gpt-3.5-turbo" in AzureOpenAIModelMap.model_aliases

        # Check that model IDs map correctly - they now map directly
        # without version suffixes
        assert AzureOpenAIModelMap.model_aliases["gpt-4o"] == "gpt-4o"
        assert AzureOpenAIModelMap.model_aliases["gpt-4-turbo"] == "gpt-4-turbo"
        assert AzureOpenAIModelMap.model_aliases["gpt-3.5-turbo"] == "gpt-35-turbo"

    def test_model_aliases(self) -> None:
        """Test accessing model aliases directly."""
        # We should be able to access model IDs directly from the model_aliases dict
        model_id = AzureOpenAIModelMap.model_aliases["gpt-4o"]

        # It should be a string and match the expected format
        assert isinstance(model_id, str)
        assert model_id == "gpt-4o"

        # We should be able to check if a model is in the map
        assert "gpt-4o" in AzureOpenAIModelMap.model_aliases
        assert "non-existent-model" not in AzureOpenAIModelMap.model_aliases

    def test_supported_models(self) -> None:
        """Test getting supported models."""
        supported = list(AzureOpenAIModelMap.model_aliases.keys())
        assert isinstance(supported, list)
        assert len(supported) > 0
        assert "gpt-4o" in supported
        assert "gpt-4-turbo" in supported
        assert "gpt-3.5-turbo" in supported


class TestAzureOpenAIPlatformConfigs:
    """Tests for the AzureOpenAI platform configs."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    def test_initialization(self) -> None:
        """Test that the configs initialize with the expected values."""
        # Check that supported_models_by_provider is populated
        assert len(AzureOpenAIPlatformConfigs.supported_models_by_provider) > 0
        first_provider = next(
            iter(AzureOpenAIPlatformConfigs.supported_models_by_provider.keys()),
        )
        assert len(AzureOpenAIPlatformConfigs.supported_models_by_provider[first_provider]) > 0

        # Check that default_platform_provider is dict and has at least the
        # llm and embedding keys
        assert isinstance(AzureOpenAIPlatformConfigs.default_platform_provider, dict)
        assert "llm" in AzureOpenAIPlatformConfigs.default_platform_provider
        assert "embedding" in AzureOpenAIPlatformConfigs.default_platform_provider

        # Check that default_model_type is set
        assert isinstance(AzureOpenAIPlatformConfigs.default_model_type, str)
        assert AzureOpenAIPlatformConfigs.default_model_type == "llm"

        # Check that default_quality_tier is dict and has at least the
        # llm and embedding keys
        assert isinstance(AzureOpenAIPlatformConfigs.default_quality_tier, dict)
        assert "llm" in AzureOpenAIPlatformConfigs.default_quality_tier
        assert "embedding" in AzureOpenAIPlatformConfigs.default_quality_tier
