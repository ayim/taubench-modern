from typing import ClassVar
from unittest.mock import MagicMock

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.cortex.configs import (
    CortexModelMap,
    CortexPlatformConfigs,
)


class TestCortexModelMap:
    """Tests for the Cortex model map."""

    def test_default(self) -> None:
        """Test that the default model map contains the expected mappings."""
        # Create an instance and check its mapping
        default_map = CortexModelMap()

        # Check that the default map contains mappings for key models
        # (And does not contain any likely mistakes)
        assert "claude-3-5-sonnet" in default_map
        assert "deepseek-r1" in default_map
        assert "snowflake-llama-3-3-70b" in default_map
        assert "voyage-multilingual" in default_map
        assert "snowflake-arctic-embed-m" in default_map
        assert "snowflake-arctic-embed-l" in default_map
        assert "llama-3-1-8b" in default_map
        assert "llama-3-1-70b" in default_map

        assert "claude-3-5-haiku" not in default_map

        # Check some specific mappings
        assert default_map["claude-3-5-sonnet"].startswith(
            "claude-3-5-sonnet",
        )
        assert default_map["deepseek-r1"].startswith(
            "deepseek-r1",
        )
        assert default_map["snowflake-llama-3-3-70b"].startswith(
            "snowflake-llama-3.3-70b",
        )
        assert default_map["voyage-multilingual"].startswith(
            "voyage-multilingual-2",
        )

    def test_class_getitem(self) -> None:
        """Test that the class can be used as a mapping."""
        # We should be able to access model IDs directly from the class
        model_id = CortexModelMap()["claude-3-5-sonnet"]

        # It should be a string and match the expected format
        assert isinstance(model_id, str)
        assert model_id.startswith("claude-3-5-sonnet")

        # We should be able to check if a model is in the map
        assert "claude-3-5-sonnet" in CortexModelMap()
        assert "non-existent-model" not in CortexModelMap()

    def test_custom_map(self) -> None:
        """Test that we can create a custom map."""
        class CustomModelMap(CortexModelMap):
            mapping: ClassVar[dict[str, str]] = {
                "claude-3-5-sonnet": "test-model-id",
                "deepseek-r1": "test-model-id",
                "snowflake-llama-3-3-70b": "test-model-id",
                "voyage-multilingual": "test-model-id",
                "snowflake-arctic-embed-m": "test-model-id",
                "snowflake-arctic-embed-l": "test-model-id",
                "llama-3-1-8b": "test-model-id",
            }

        # Create a custom map instance
        model_map = CustomModelMap()

        # Verify the custom map was used
        assert model_map["claude-3-5-sonnet"] == "test-model-id"
        assert model_map["deepseek-r1"] == "test-model-id"
        assert model_map["snowflake-llama-3-3-70b"] == "test-model-id"
        assert model_map["voyage-multilingual"] == "test-model-id"
        assert model_map["snowflake-arctic-embed-m"] == "test-model-id"
        assert model_map["snowflake-arctic-embed-l"] == "test-model-id"
        assert model_map["llama-3-1-8b"] == "test-model-id"


class TestCortexPlatformConfigs:
    """Tests for the Cortex platform configs."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    def test_initialization(self) -> None:
        """Test that the configs initialize with the expected values."""
        configs = CortexPlatformConfigs()

        # Check that supported_models_by_provider is populated
        assert len(configs.supported_models_by_provider) > 0
        first_provider = next(iter(configs.supported_models_by_provider.keys()))
        assert len(configs.supported_models_by_provider[first_provider]) > 0

        # Check that default_platform_provider is dict and has at least the
        # llm and embedding keys
        assert isinstance(configs.default_platform_provider, dict)
        assert "llm" in configs.default_platform_provider
        assert "embedding" in configs.default_platform_provider

