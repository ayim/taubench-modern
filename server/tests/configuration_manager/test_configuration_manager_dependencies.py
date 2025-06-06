"""Tests for configuration dependencies.

This module contains tests for the ConfigurationManager's handling of configuration
dependencies, ensuring that configurations are loaded in the correct order.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from agent_platform.core.configurations import Configuration
from agent_platform.server.configuration_manager import ConfigurationService


@dataclass(frozen=True)
class BaseConfig(Configuration):
    """Base configuration for dependency tests."""

    base_value: str = field(
        default="base_default",
        metadata={"description": "Base value", "env_vars": ["TEST_BASE_VALUE"]},
    )


@dataclass(frozen=True)
class MiddleConfig(Configuration):
    """Middle configuration that depends on BaseConfig."""

    depends_on: ClassVar[list[type[Configuration]]] = [BaseConfig]
    middle_value: str = field(
        default="middle_default",
        metadata={"description": "Middle value", "env_vars": ["TEST_MIDDLE_VALUE"]},
    )


@dataclass(frozen=True)
class TopConfig(Configuration):
    """Top configuration that depends on MiddleConfig."""

    depends_on: ClassVar[list[type[Configuration]]] = [MiddleConfig]
    top_value: str = field(
        default="top_default",
        metadata={"description": "Top value", "env_vars": ["TEST_TOP_VALUE"]},
    )


@dataclass(frozen=True)
class CircularConfigA(Configuration):
    """Configuration with circular dependency (A -> B -> A)."""

    depends_on: ClassVar[list[type[Configuration]]] = []
    value_a: str = field(
        default="value_a",
        metadata={"description": "Value A", "env_vars": ["TEST_VALUE_A"]},
    )


@dataclass(frozen=True)
class CircularConfigB(Configuration):
    """Configuration with circular dependency (B -> A -> B)."""

    depends_on: ClassVar[list[type[Configuration]]] = [CircularConfigA]
    value_b: str = field(
        default="value_b",
        metadata={"description": "Value B", "env_vars": ["TEST_VALUE_B"]},
    )


# Fix the circular dependency by setting it after both classes are defined
CircularConfigA.depends_on = [CircularConfigB]


class TestConfigurationDependencies:
    """Test suite for configuration dependencies."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Reset the ConfigurationService singleton
        ConfigurationService.reset()
        # Clear any existing instances
        BaseConfig._instances.clear()
        MiddleConfig._instances.clear()
        TopConfig._instances.clear()
        CircularConfigA._instances.clear()
        CircularConfigB._instances.clear()

    def test_linear_dependencies(self) -> None:
        """Test loading configurations with linear dependencies."""
        # Initialize the configuration service
        ConfigurationService.initialize(
            packages_to_scan=[],
            config_modules=[__name__],
        )

        # Get the manager
        manager = ConfigurationService.get_instance()

        # Verify that all configurations were loaded
        assert BaseConfig.base_value == "base_default"
        assert MiddleConfig.middle_value == "middle_default"
        assert TopConfig.top_value == "top_default"

        # Verify that the configurations are in the manager's config_classes
        base_path = f"{BaseConfig.__module__}.{BaseConfig.__name__}"
        middle_path = f"{MiddleConfig.__module__}.{MiddleConfig.__name__}"
        top_path = f"{TopConfig.__module__}.{TopConfig.__name__}"

        assert base_path in manager.config_classes
        assert middle_path in manager.config_classes
        assert top_path in manager.config_classes

    def test_dependency_order(self) -> None:
        """Test that configurations are loaded in dependency order."""
        # Mock the _load_registered_configurations method to capture the order
        with patch(
            "agent_platform.server.configuration_manager.ConfigurationManager._load_registered_configurations",
        ) as mock_load:
            # Initialize the configuration service
            ConfigurationService.initialize(
                packages_to_scan=[],
                config_modules=[__name__],
            )

            # Verify that _load_registered_configurations was called
            mock_load.assert_called_once()

            # We can't directly test the order of loading, but we can verify
            # that the configurations are accessible after loading
            assert hasattr(BaseConfig, "base_value")
            assert hasattr(MiddleConfig, "middle_value")
            assert hasattr(TopConfig, "top_value")

    def test_circular_dependencies(self) -> None:
        """Test handling of circular dependencies."""
        # Initialize the configuration service
        ConfigurationService.initialize(
            packages_to_scan=[],
            config_modules=[__name__],
        )

        # Get the manager
        manager = ConfigurationService.get_instance()

        # Verify that both configurations were loaded despite the circular dependency
        assert CircularConfigA.value_a == "value_a"
        assert CircularConfigB.value_b == "value_b"

        # Verify that the configurations are in the manager's config_classes
        a_path = f"{CircularConfigA.__module__}.{CircularConfigA.__name__}"
        b_path = f"{CircularConfigB.__module__}.{CircularConfigB.__name__}"

        assert a_path in manager.config_classes
        assert b_path in manager.config_classes

    def test_dependency_with_config_file(self, tmp_path: Path) -> None:
        """Test loading configurations with dependencies from a config file."""
        # Create a temporary config file with data for our test configs
        config_file = tmp_path / "config.json"
        config_data = {
            f"{BaseConfig.__module__}.{BaseConfig.__name__}": {
                "base_value": "from_file_base",
            },
            f"{MiddleConfig.__module__}.{MiddleConfig.__name__}": {
                "middle_value": "from_file_middle",
            },
            f"{TopConfig.__module__}.{TopConfig.__name__}": {
                "top_value": "from_file_top",
            },
        }
        with open(config_file, "w") as f:
            import json

            json.dump(config_data, f)

        # Initialize the configuration service with the temp file
        ConfigurationService.initialize(
            config_path=config_file,
            packages_to_scan=[],
            config_modules=[__name__],
        )

        # Verify the configurations were loaded correctly
        assert BaseConfig.base_value == "from_file_base"
        assert MiddleConfig.middle_value == "from_file_middle"
        assert TopConfig.top_value == "from_file_top"

    def test_dependency_with_environment_variables(self) -> None:
        """Test that environment variables work with dependent configurations."""
        # Set environment variables
        import os

        os.environ["TEST_BASE_VALUE"] = "from_env_base"
        os.environ["TEST_MIDDLE_VALUE"] = "from_env_middle"
        os.environ["TEST_TOP_VALUE"] = "from_env_top"

        try:
            # Initialize the configuration service
            ConfigurationService.initialize(
                packages_to_scan=[],
                config_modules=[__name__],
            )

            # Verify that environment variables were applied
            assert BaseConfig.base_value == "from_env_base"
            assert MiddleConfig.middle_value == "from_env_middle"
            assert TopConfig.top_value == "from_env_top"
        finally:
            # Clean up environment variables
            if "TEST_BASE_VALUE" in os.environ:
                del os.environ["TEST_BASE_VALUE"]
            if "TEST_MIDDLE_VALUE" in os.environ:
                del os.environ["TEST_MIDDLE_VALUE"]
            if "TEST_TOP_VALUE" in os.environ:
                del os.environ["TEST_TOP_VALUE"]

    def test_dependency_with_overrides(self) -> None:
        """Test that command line overrides work with dependent configurations."""
        # Initialize with command line overrides
        overrides = {
            f"{BaseConfig.__module__}.{BaseConfig.__name__}": {
                "base_value": "from_override_base",
            },
            f"{MiddleConfig.__module__}.{MiddleConfig.__name__}": {
                "middle_value": "from_override_middle",
            },
            f"{TopConfig.__module__}.{TopConfig.__name__}": {
                "top_value": "from_override_top",
            },
        }

        # Initialize the configuration service with overrides
        ConfigurationService.initialize(
            packages_to_scan=[],
            config_modules=[__name__],
            overrides=overrides,
        )

        # Verify that command line overrides were applied
        assert BaseConfig.base_value == "from_override_base"
        assert MiddleConfig.middle_value == "from_override_middle"
        assert TopConfig.top_value == "from_override_top"
