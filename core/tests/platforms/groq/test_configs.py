"""Unit tests for the OpenAI platform configs."""

from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.groq.configs import (
    GroqModelMap,
    GroqPlatformConfigs,
)


class TestGroqModelMap:
    """Tests for the GroqModelMap."""

    def test_basic(self) -> None:
        """Test that model aliases are correctly resolved."""
        model_map = GroqModelMap()

        # LLMs that support tools
        for alias in ["llama-3.3"]:
            assert alias in model_map.model_aliases
            assert alias in GroqModelMap.distinct_llm_model_ids_with_tool_input()

            assert GroqModelMap.models_to_type[alias] == "llm"

            assert alias in model_map.models_to_input_modalities
            assert "text" in model_map.models_to_input_modalities[alias]
            assert "tools" in model_map.models_to_input_modalities[alias]

            assert alias in model_map.models_to_output_modalities
            assert "text" in model_map.models_to_input_modalities[alias]


class TestGroqPlatformConfigs:
    """Tests for the Groq platform configs."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    def test_initialization(self) -> None:
        """Test that the configs initialize with the expected values."""
        configs = GroqPlatformConfigs()

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
