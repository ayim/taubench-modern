"""Unit tests for the OpenAI platform configs."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.configs import (
    OpenAIModelMap,
    OpenAIPlatformConfigs,
)


class TestOpenAIModelMap:
    """Tests for the OpenAI model map."""

    def test_default(self) -> None:
        """Test that the default model map contains the expected mappings."""
        # Create an instance and check its mapping
        default_map = OpenAIModelMap()

        # Check that the default map contains mappings for key models
        assert "gpt-4" in default_map
        assert "gpt-4-turbo" in default_map
        assert "gpt-3.5-turbo" in default_map

    def test_class_getitem(self) -> None:
        """Test that the class can be used as a mapping."""
        # We should be able to access model IDs directly from the class
        model_map = OpenAIModelMap()

        # It should be a string and match the expected format
        assert isinstance(model_map["gpt-4"], str)
        assert model_map["gpt-4"] == "gpt-4"

    def test_custom_map(self) -> None:
        """Test that we can create a custom map."""
        # Create a custom model map with specific parameters
        model_map = OpenAIModelMap()

        # Set a custom mapping
        model_map["test-model-id"] = "test-model-name"

        # Verify the custom mapping was set
        assert model_map["test-model-id"] == "test-model-name"


class TestOpenAIPlatformConfigs:
    """Tests for the OpenAI platform configs."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    def test_initialization(self) -> None:
        """Test that the configs initialize with the expected values."""
        configs = OpenAIPlatformConfigs()

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
