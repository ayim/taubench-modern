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
        assert "gpt-4o" in default_map
        assert "gpt-4-turbo" in default_map
        assert "gpt-3.5-turbo" in default_map

        # Check that model IDs map correctly
        assert default_map["gpt-4o"].startswith("gpt-4o-")
        assert default_map["gpt-4-turbo"].startswith("gpt-4-turbo-")
        assert default_map["gpt-3.5-turbo"].startswith("gpt-3.5-turbo-")

    def test_class_getitem(self) -> None:
        """Test that the class can be used as a mapping."""
        # We should be able to access model IDs directly from the class
        model_id = OpenAIModelMap()["gpt-4o"]

        # It should be a string and match the expected format
        assert isinstance(model_id, str)
        assert model_id.startswith("gpt-4o-")

        # We should be able to check if a model is in the map
        assert "gpt-4o" in OpenAIModelMap()
        assert "non-existent-model" not in OpenAIModelMap()

    def test_supported_models(self) -> None:
        """Test getting supported models."""
        supported = OpenAIModelMap.supported_models()
        assert isinstance(supported, list)
        assert len(supported) > 0
        assert "gpt-4o" in supported
        assert "gpt-4-turbo" in supported
        assert "gpt-3.5-turbo" in supported


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
