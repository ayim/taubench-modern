"""Unit tests for the Google platform configs."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.google.configs import (
    GoogleModelMap,
    GooglePlatformConfigs,
)


class TestGoogleModelMap:
    """Tests for the Google model map."""

    def test_default(self) -> None:
        """Test that the default model map contains the expected mappings."""
        # Create an instance and check its mapping
        default_map = GoogleModelMap()

        # Check that the default map contains mappings for key models
        assert "gemini-1.5-pro" in default_map.model_aliases
        assert "models/text-embedding-004" in default_map.model_aliases

        # Check that model IDs map correctly
        assert default_map.model_aliases["gemini-1.5-pro"] == "gemini-1.5-pro"
        assert default_map.model_aliases["models/text-embedding-004"] == "models/text-embedding-004"

    def test_class_getitem(self) -> None:
        """Test that the class can be used as a mapping."""
        # We should be able to access model IDs directly from the class
        model_id = GoogleModelMap().model_aliases["gemini-1.5-pro"]

        # It should be a string and match the expected format
        assert isinstance(model_id, str)
        assert model_id == "gemini-1.5-pro"

        # We should be able to check if a model is in the map
        assert "gemini-1.5-pro" in GoogleModelMap().model_aliases
        assert "non-existent-model" not in GoogleModelMap().model_aliases

    def test_supported_models(self) -> None:
        """Test getting supported models."""
        supported = GoogleModelMap.supported_models()
        assert isinstance(supported, list)
        assert len(supported) > 0
        assert "gemini-1.5-pro" in supported
        assert "models/text-embedding-004" in supported


class TestGooglePlatformConfigs:
    """Tests for the Google platform configs."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    def test_initialization(self) -> None:
        """Test that the configs initialize with the expected values."""
        configs = GooglePlatformConfigs()

        # Check that supported_models_by_provider is populated
        assert len(configs.supported_models_by_provider) > 0
        first_provider = next(iter(configs.supported_models_by_provider.keys()))
        assert len(configs.supported_models_by_provider[first_provider]) > 0

        # Check that default_platform_provider is dict and has at least the
        # llm and embedding keys
        assert isinstance(configs.default_platform_provider, dict)
        assert "llm" in configs.default_platform_provider
        assert "embedding" in configs.default_platform_provider

        # Check that default_model_type is set
        assert isinstance(configs.default_model_type, str)
        assert configs.default_model_type == "llm"

        # Check that default_quality_tier is dict and has at least the
        # llm and embedding keys
        assert isinstance(configs.default_quality_tier, dict)
        assert "llm" in configs.default_quality_tier
        assert "embedding" in configs.default_quality_tier
