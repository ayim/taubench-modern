"""Unit tests for the configurations module."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import pytest

from agent_platform.core.configurations import Configuration


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

    def test_class_attribute_access(self) -> None:
        """Test class-level attribute access."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        # First set the instance
        config = SampleConfig()
        SampleConfig.set_instance(config)

        # Then test class attribute access
        assert SampleConfig.name == "default"
        assert SampleConfig.count == 10

    def test_set_instance(self) -> None:
        """Test set_instance method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig(name="custom", count=20)
        SampleConfig.set_instance(config)

        assert SampleConfig.name == "custom"
        assert SampleConfig.count == 20

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
            def get_default_instance(cls) -> "SampleConfig":
                # Return a SampleConfig with a custom name
                return cls(name="custom_default")

        config = SampleConfig.get_default_instance()
        assert config.name == "custom_default"
        assert config.count == 10

    def test_to_dict(self) -> None:
        """Test to_dict method."""

        @dataclass(frozen=True)
        class SampleConfig(Configuration):
            name: str = "default"
            count: int = 10

        config = SampleConfig(name="to_dict", count=70)
        data = config.to_dict()

        assert data == {"name": "to_dict", "count": 70}

    def test_field_metadata_description(self) -> None:
        """Test field metadata with descriptions."""

        @dataclass(frozen=True)
        class ConfigWithDescriptions(Configuration):
            name: str = field(
                default="default",
                metadata={"description": "The name of the configuration"},
            )
            count: int = field(
                default=10,
                metadata={"description": "Count value"},
            )

        # Test getting all field descriptions
        descriptions = ConfigWithDescriptions.get_field_descriptions()
        assert descriptions == {
            "name": "The name of the configuration",
            "count": "Count value",
        }

        # Test getting a specific field description
        assert (
            ConfigWithDescriptions.get_field_description("name") == "The name of the configuration"
        )
        assert ConfigWithDescriptions.get_field_description("count") == "Count value"
        assert ConfigWithDescriptions.get_field_description("nonexistent") is None

    def test_field_metadata_env_vars(self) -> None:
        """Test field metadata with environment variables."""

        @dataclass(frozen=True)
        class ConfigWithEnvVars(Configuration):
            name: str = field(
                default="default",
                metadata={"description": "Name", "env_vars": ["CONFIG_NAME", "NAME"]},
            )
            count: int = field(
                default=10,
                metadata={"description": "Count", "env_vars": ["CONFIG_COUNT"]},
            )

        # Test getting environment variables for a field
        assert ConfigWithEnvVars.get_field_env_vars("name") == ["CONFIG_NAME", "NAME"]
        assert ConfigWithEnvVars.get_field_env_vars("count") == ["CONFIG_COUNT"]
        assert ConfigWithEnvVars.get_field_env_vars("nonexistent") == []

    def test_to_dict_with_init_false(self) -> None:
        """Test to_dict method with fields that have init=False."""

        @dataclass(frozen=True)
        class ConfigWithNoInit(Configuration):
            name: str = "default"
            count: int = 10
            derived: str = field(default="derived", init=False)

        config = ConfigWithNoInit()

        # Test to_dict with all fields
        data = config.to_dict()
        assert data == {"name": "default", "count": 10, "derived": "derived"}

        # Test to_dict excluding fields with init=False
        data = config.to_dict(include_fields_with_no_init=False)
        assert data == {"name": "default", "count": 10}

    def test_get_concrete_configs(self) -> None:
        """Test get_concrete_configs class method."""

        @dataclass(frozen=True)
        class ConcreteConfig1(Configuration):
            value: int = 1

        @dataclass(frozen=True)
        class ConcreteConfig2(Configuration):
            value: int = 2

        # Get all concrete configurations
        concrete_configs = Configuration.get_concrete_configs()

        # Check if our test configs are in the returned dictionary
        # We use the full path of the configuration class as the key
        config1_path = f"{ConcreteConfig1.__module__}.{ConcreteConfig1.__name__}"
        config2_path = f"{ConcreteConfig2.__module__}.{ConcreteConfig2.__name__}"

        assert config1_path in concrete_configs
        assert config2_path in concrete_configs
        assert concrete_configs[config1_path] is ConcreteConfig1
        assert concrete_configs[config2_path] is ConcreteConfig2

    def test_configuration_dependencies(self) -> None:
        """Test configuration dependencies."""

        @dataclass(frozen=True)
        class BaseConfig(Configuration):
            base_value: str = "base"

        @dataclass(frozen=True)
        class DependentConfig(Configuration):
            depends_on: ClassVar[list[type[Configuration]]] = [BaseConfig]
            dependent_value: str = "dependent"

        # Test that dependencies are correctly defined
        assert DependentConfig.depends_on == [BaseConfig]

        # Set up instances and verify they work together
        base_config = BaseConfig(base_value="custom_base")
        BaseConfig.set_instance(base_config)

        dependent_config = DependentConfig(dependent_value="custom_dependent")
        DependentConfig.set_instance(dependent_config)

        # Verify class-level access for both configurations
        assert BaseConfig.base_value == "custom_base"
        assert DependentConfig.dependent_value == "custom_dependent"


class TestRealWorldUsage:
    """Test suite for real-world usage examples."""

    def test_bedrock_content_limits(self) -> None:
        """Test a real-world usage of a simple configuration."""

        @dataclass(frozen=True)
        class BedrockContentLimits(Configuration):
            """Content limits for Bedrock platform."""

            MAX_IMAGE_COUNT: int = 20
            MAX_IMAGE_SIZE: int = 3_750_000

        # Test basic access
        limits = BedrockContentLimits()
        assert limits.MAX_IMAGE_COUNT == 20
        assert limits.MAX_IMAGE_SIZE == 3_750_000

        # Test instance override
        custom_limits = BedrockContentLimits(
            MAX_IMAGE_COUNT=10,
            MAX_IMAGE_SIZE=1_000_000,
        )
        assert custom_limits.MAX_IMAGE_COUNT == 10
        assert custom_limits.MAX_IMAGE_SIZE == 1_000_000

        # Test class-level access after setting instance
        BedrockContentLimits.set_instance(custom_limits)
        assert BedrockContentLimits.MAX_IMAGE_COUNT == 10
        assert BedrockContentLimits.MAX_IMAGE_SIZE == 1_000_000

    def test_complex_configuration_with_paths(self) -> None:
        """Test a more complex configuration with path handling."""

        @dataclass(frozen=True)
        class SystemPaths(Configuration):
            """System paths configuration."""

            data_dir: Path = field(
                default=Path("/path/to/data"),
                metadata={"description": "Base directory for data storage"},
            )
            log_dir: Path = field(
                default=Path("/path/to/logs"),
                metadata={"description": "Directory for log files"},
            )

        @dataclass(frozen=True)
        class AppConfig(Configuration):
            """Application configuration that depends on SystemPaths."""

            depends_on: ClassVar[list[type[Configuration]]] = [SystemPaths]

            app_name: str = "agent-platform"
            version: str = "1.0.0"
            debug: bool = False

        # Test basic configurations
        paths = SystemPaths()
        app_config = AppConfig()

        assert paths.data_dir == Path("/path/to/data")
        assert paths.log_dir == Path("/path/to/logs")
        assert app_config.app_name == "agent-platform"
        assert app_config.version == "1.0.0"
        assert app_config.debug is False

        # Test custom paths
        custom_paths = SystemPaths(
            data_dir=Path("/custom/data"),
            log_dir=Path("/custom/logs"),
        )

        # Test to_dict with Path objects
        paths_dict = custom_paths.to_dict()
        assert paths_dict["data_dir"] == Path("/custom/data")
        assert paths_dict["log_dir"] == Path("/custom/logs")
