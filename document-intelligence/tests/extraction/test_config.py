from sema4ai_docint.extraction.reducto.config import ReductoConfig


class TestReductoConfig:
    """Test cases for the ReductoConfig class with embedded configuration."""

    def test_load_config_success(self):
        """Test successful loading of embedded configuration."""
        config = ReductoConfig.load_config()

        assert isinstance(config, dict)
        assert len(config) == 0

    def test_load_config_returns_copy(self):
        """Test that load_config returns a copy to prevent modification of internal state."""
        config1 = ReductoConfig.load_config()
        config2 = ReductoConfig.load_config()

        # Should be equal but not the same object
        assert config1 == config2
        assert config1 is not config2

        # Modifying one should not affect the other
        config1["new_key"] = "new_value"
        assert "new_key" not in config2

    def test_config_immutability(self):
        """Test that modifying the returned config doesn't affect future calls."""
        # Get config and modify it
        config1 = ReductoConfig.load_config()
        config1["new_section"] = {"test": "value"}

        # Get fresh config and verify original values are preserved
        config2 = ReductoConfig.load_config()
        assert "new_section" not in config2
        assert len(config2) == 0
