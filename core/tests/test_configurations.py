"""Unit tests for the configurations module."""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest

from agent_platform.core.configurations import Configuration, MapConfiguration


class TestConfiguration:
    """Test suite for the Configuration class."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig()
        assert config.name == "default"
        assert config.count == 10

    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom values."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig(name="custom", count=20)
        assert config.name == "custom"
        assert config.count == 20

    def test_getitem(self) -> None:
        """Test __getitem__ method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig()
        assert config["name"] == "default"
        assert config["count"] == 10

    def test_class_getitem(self) -> None:
        """Test __class_getitem__ method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        assert SampleConfig["name"] == "default"
        assert SampleConfig["count"] == 10

    def test_set_instance(self) -> None:
        """Test set_instance method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig(name="custom", count=20)
        SampleConfig.set_instance(config)

        assert SampleConfig["name"] == "custom"
        assert SampleConfig["count"] == 20

    def test_from_json(self) -> None:
        """Test from_json method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "from_json", "count": 30}, f)

        try:
            config = SampleConfig.from_json(f.name)
            assert config.name == "from_json"
            assert config.count == 30
        finally:
            Path(f.name).unlink()

    def test_from_json_missing_file(self) -> None:
        """Test from_json method with missing file."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        with pytest.raises(FileNotFoundError):
            SampleConfig.from_json("nonexistent.json")

    def test_from_json_invalid_type(self) -> None:
        """Test from_json method with invalid type."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "from_json", "count": "not an int"}, f)

        try:
            with pytest.raises(TypeError):
                SampleConfig.from_json(f.name)
        finally:
            Path(f.name).unlink()

    def test_from_dict(self) -> None:
        """Test from_dict method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig.from_dict({"name": "model_validate", "count": 40})
        assert config.name == "model_validate"
        assert config.count == 40

    def test_from_dict_invalid_type(self) -> None:
        """Test from_dict method with invalid type."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        with pytest.raises(TypeError):
            SampleConfig.from_dict(
                {"name": "model_validate", "count": "not an int"},
            )

    def test_default(self) -> None:
        """Test default method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

            @classmethod
            def default(cls) -> "SampleConfig":
                # Return a SampleConfig with a custom name
                return cls(name="custom_default")

        config = SampleConfig.default()
        assert config.name == "custom_default"
        assert config.count == 10

    def test_to_json(self) -> None:
        """Test to_json method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig(name="to_json", count=50)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            pass

        try:
            config.to_json(f.name)

            with open(f.name) as f:
                data = json.load(f)

            assert data == {"name": "to_json", "count": 50}
        finally:
            Path(f.name).unlink()

    def test_to_json_with_config_path(self) -> None:
        """Test to_json method with config_path."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            pass

        try:
            config = SampleConfig(name="to_json_config_path", count=60)
            SampleConfig.config_path = Path(f.name)

            config.to_json()

            with open(f.name) as f:
                data = json.load(f)

            assert data == {"name": "to_json_config_path", "count": 60}
        finally:
            Path(f.name).unlink()
            SampleConfig.config_path = None

    def test_to_json_no_path(self) -> None:
        """Test to_json method with no path."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig()

        with pytest.raises(
            ValueError, match="No json_path provided and no config_path set",
        ):
            config.to_json()

    def test_to_dict(self) -> None:
        """Test to_dict method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig(name="to_dict", count=70)
        data = config.to_dict()

        assert data == {"name": "to_dict", "count": 70}


class TestMapConfiguration:
    """Test suite for the MapConfiguration class."""

    def test_map_functionality(self) -> None:
        """Test all MapConfiguration functionality in one test to
        avoid issues with class singletons."""

        # Create a concrete MapConfiguration subclass
        @dataclass(frozen=True)
        class SampleMap(MapConfiguration):
            # Explicitly define mapping to override the parent
            mapping: ClassVar[dict[str, Any]] = {
                "key1": "value1",
                "key2": 2,
            }

        # Test __getitem__
        map_instance = SampleMap()
        assert map_instance["key1"] == "value1"
        assert map_instance["key2"] == 2

        # Test __contains__
        assert "key1" in map_instance
        assert "key3" not in map_instance

        # Test __iter__
        keys = list(map_instance)
        assert len(keys) == 2
        assert "key1" in keys
        assert "key2" in keys

        # Test __len__
        assert len(map_instance) == 2

        # Test items
        items = dict(map_instance.items())
        assert items == {"key1": "value1", "key2": 2}

        # Test keys
        keys = list(map_instance.keys())
        assert len(keys) == 2
        assert "key1" in keys
        assert "key2" in keys

        # Test values
        values = list(map_instance.values())
        assert len(values) == 2
        assert "value1" in values
        assert 2 in values

    def test_dict_access_methods(self) -> None:
        """Test additional dictionary access methods with custom mapping."""

        # Create with custom mapping
        @dataclass(frozen=True)
        class CustomMap(MapConfiguration):
            mapping: ClassVar[dict[str, Any]] = {
                "name": "test",
                "count": 42,
                "nested": {"a": 1, "b": 2},
            }

        config = CustomMap()

        # Basic access
        assert config["name"] == "test"
        assert config["count"] == 42
        assert config["nested"] == {"a": 1, "b": 2}

        # Can access nested dict
        nested = config["nested"]
        assert nested["a"] == 1
        assert nested["b"] == 2

    def test_setitem_operation(self) -> None:
        """Test the __setitem__ operation for MapConfiguration.

        Even though MapConfiguration is frozen, the mapping itself is mutable.
        """

        # Create a MapConfiguration with an empty mapping
        @dataclass(frozen=True)
        class TestMap(MapConfiguration):
            mapping: ClassVar[dict[str, Any]] = {}

        # Create an instance
        config = TestMap()

        # The instance itself is frozen, but the mapping is a mutable dict
        # So we can modify the mapping even though the instance is frozen
        config.mapping["key1"] = "value1"
        assert config["key1"] == "value1"

        # Test the __setitem__ method which modifies the mapping
        config["key2"] = "value2"
        assert config["key2"] == "value2"
        assert config.mapping["key2"] == "value2"

    def test_class_methods(self) -> None:
        """Test class-level methods for MapConfiguration."""

        # Create a MapConfiguration subclass
        @dataclass(frozen=True)
        class ClassMethodMap(MapConfiguration):
            mapping: ClassVar[dict[str, Any]] = {
                "key1": "value1",
                "key2": 2,
            }

        # Test class_items method
        items = dict(ClassMethodMap.class_items())
        assert items == {"key1": "value1", "key2": 2}

        # Create a new subclass with a different mapping
        @dataclass(frozen=True)
        class NewClassMethodMap(ClassMethodMap):
            mapping: ClassVar[dict[str, Any]] = {
                "key1": "new_value",
                "key3": 3,
            }

        # TODO: why would we ever do this?
        ClassMethodMap.set_instance(NewClassMethodMap())

        # Verify class methods now use the new instance
        assert ClassMethodMap["key1"] == "new_value"
        assert ClassMethodMap["key3"] == 3

        # Verify class_items reflects the new instance
        items = dict(ClassMethodMap.class_items())
        assert items == {"key1": "new_value", "key3": 3}


class TestRealWorldUsage:
    """Test suite for real-world usage examples."""

    def test_bedrock_model_map(self) -> None:
        """Test a real-world usage example with BedrockModelMap."""

        # Clean test slate for class-level singletons
        @dataclass(frozen=True)
        class BedrockModelMap(MapConfiguration):
            """A map of model names to Bedrock model IDs."""

            mapping: ClassVar[dict[str, str]] = {
                "claude-3-5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "claude-3-5-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
            }

        # Define a method that doesn't rely on class singletons
        def get_supported_models(model_map: BedrockModelMap) -> list[str]:
            """Get list of supported model names from a model map instance."""
            return list(model_map.class_keys())

        # Instance-level tests that don't rely on class singletons
        model_map = BedrockModelMap()

        # Test the helper method
        models = get_supported_models(model_map)
        assert len(models) == 2
        assert "claude-3-5-sonnet" in models
        assert "claude-3-5-haiku" in models

        # Test basic dict-like access
        assert (
            model_map["claude-3-5-sonnet"]
            == "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        assert (
            model_map["claude-3-5-haiku"] == "us.anthropic.claude-3-haiku-20240307-v1:0"
        )

        # Create a new instance with different mapping
        class CustomModelMap(BedrockModelMap):
            mapping: ClassVar[dict[str, str]] = {
                "claude-3-5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "claude-3-5-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
                "claude-3-opus": "us.anthropic.claude-3-opus-20240229-v1:0",
            }

        # Test the expanded map
        assert "claude-3-opus" in CustomModelMap()
        assert (
            CustomModelMap()["claude-3-opus"]
            == "us.anthropic.claude-3-opus-20240229-v1:0"
        )

        # Test the helper method with the expanded map
        expanded_models = get_supported_models(CustomModelMap())
        assert len(expanded_models) == 3
        assert "claude-3-opus" in expanded_models

    def test_bedrock_config_integration(self) -> None:
        """Test how different Bedrock configurations work together."""

        # Create a simple content limits configuration
        @dataclass(frozen=True)
        class BedrockContentLimits(Configuration):
            """Content limits for Bedrock platform."""

            MAX_IMAGE_COUNT: int = 20
            MAX_IMAGE_SIZE: int = 3_750_000

        # Create a model map
        @dataclass(frozen=True)
        class BedrockModelMap(MapConfiguration):
            """Map of model names to Bedrock model IDs."""

            mapping: ClassVar[dict[str, str]] = {
                "claude-3-5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "claude-3-5-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
            }

        # Test that both configurations can be used in tandem
        limits = BedrockContentLimits()
        model_map = BedrockModelMap()

        assert limits.MAX_IMAGE_COUNT == 20
        assert (
            model_map["claude-3-5-sonnet"]
            == "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        )

        # Test access via class methods
        assert BedrockContentLimits["MAX_IMAGE_SIZE"] == 3_750_000
        assert (
            BedrockModelMap["claude-3-5-haiku"]
            == "us.anthropic.claude-3-haiku-20240307-v1:0"
        )
