from unittest.mock import MagicMock

import pytest

from agent_server_types_v2.kernel import Kernel
from agent_server_types_v2.models.model import Models
from agent_server_types_v2.platforms.bedrock.configs import (
    BedrockModelMap,
    BedrockPlatformConfigs,
)


class TestBedrockModelMap:
    """Tests for the Bedrock model map."""

    def test_default(self) -> None:
        """Test that the default model map contains the expected mappings."""
        # Create an instance and check its mapping
        default_map = BedrockModelMap()

        # Check that the default map contains mappings for key models
        assert Models.ANTHROPIC_CLAUDE_3_5_SONNET.name in default_map
        assert Models.ANTHROPIC_CLAUDE_3_5_HAIKU.name in default_map

        # Check some specific mappings
        assert default_map[Models.ANTHROPIC_CLAUDE_3_5_SONNET.name].startswith(
            "us.anthropic.claude-3-5-sonnet",
        )
        assert default_map[Models.ANTHROPIC_CLAUDE_3_5_HAIKU.name].startswith(
            "us.anthropic.claude-3-haiku",
        )

    def test_class_getitem(self) -> None:
        """Test that the class can be used as a mapping."""
        # We should be able to access model IDs directly from the class
        model_id = BedrockModelMap()["claude-3-5-sonnet"]

        # It should be a string and match the expected format
        assert isinstance(model_id, str)
        assert model_id.startswith("us.anthropic.claude-3-5-sonnet")

        # We should be able to check if a model is in the map
        assert "claude-3-5-sonnet" in BedrockModelMap()
        assert "non-existent-model" not in BedrockModelMap()

    def test_custom_map(self) -> None:
        """Test that we can create a custom map."""
        custom_map = {
            Models.ANTHROPIC_CLAUDE_3_5_SONNET.name: "test-model-id",
        }

        # Create a custom map instance
        model_map = BedrockModelMap(mapping=custom_map)

        # Verify the custom map was used
        assert model_map[Models.ANTHROPIC_CLAUDE_3_5_SONNET.name] == "test-model-id"


class TestBedrockPlatformConfigs:
    """Tests for the Bedrock platform configs."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    def test_initialization(self) -> None:
        """Test that the configs initialize with the expected values."""
        configs = BedrockPlatformConfigs()

        # Check that supported_models_by_provider is populated
        assert len(configs.supported_models_by_provider) > 0
        first_provider = next(iter(configs.supported_models_by_provider.keys()))
        assert len(configs.supported_models_by_provider[first_provider]) > 0

        # Check that default_platform_provider is dict and has at least the
        # llm and embedding keys
        assert isinstance(configs.default_platform_provider, dict)
        assert "llm" in configs.default_platform_provider
        assert "embedding" in configs.default_platform_provider

