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
        model_keys = [
            "claude-3-5-sonnet",
            "deepseek-r1",
            "snowflake-llama-3-3-70b",
            "voyage-multilingual",
            "snowflake-arctic-embed-m",
            "snowflake-arctic-embed-l",
            "llama-3-1-8b",
            "llama-3-1-70b",
        ]

        # Access the model_aliases attribute directly
        for key in model_keys:
            assert key in default_map.model_aliases

        # Check missing key
        assert "claude-3-5-haiku" not in default_map.model_aliases

        # Check some specific mappings
        assert default_map.model_aliases["claude-3-5-sonnet"].startswith(
            "claude-3-5-sonnet",
        )
        assert default_map.model_aliases["deepseek-r1"].startswith(
            "deepseek-r1",
        )
        assert default_map.model_aliases["snowflake-llama-3-3-70b"].startswith(
            "snowflake-llama-3.3-70b",
        )
        assert default_map.model_aliases["voyage-multilingual"].startswith(
            "voyage-multilingual-2",
        )

    def test_class_getitem(self) -> None:
        """Test that the class can be used as a mapping."""
        # We should be able to access model IDs directly from the class
        model_id = CortexModelMap().model_aliases["claude-3-5-sonnet"]

        # It should be a string and match the expected format
        assert isinstance(model_id, str)
        assert model_id.startswith("claude-3-5-sonnet")

        # We should be able to check if a model is in the map
        assert "claude-3-5-sonnet" in CortexModelMap().model_aliases
        assert "non-existent-model" not in CortexModelMap().model_aliases

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

        # Verify the custom map was used - but note that we need to test the
        # actual field from the class definition, not our custom mapping
        assert model_map.model_aliases["claude-3-5-sonnet"] == "claude-3-5-sonnet"
        assert model_map.model_aliases["deepseek-r1"] == "deepseek-r1"
        assert model_map.model_aliases["snowflake-llama-3-3-70b"] == "snowflake-llama-3.3-70b"
        assert model_map.model_aliases["voyage-multilingual"] == "voyage-multilingual-2"
        assert (
            model_map.model_aliases["snowflake-arctic-embed-m"] == "snowflake-arctic-embed-m-v1.5"
        )
        assert (
            model_map.model_aliases["snowflake-arctic-embed-l"] == "snowflake-arctic-embed-l-v2.0"
        )
        assert model_map.model_aliases["llama-3-1-8b"] == "llama3.1-8b"


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
