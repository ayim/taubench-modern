from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from agent_platform.core.configurations import Configuration
from agent_platform.server.cli import configurations
from agent_platform.server.configuration_manager import ConfigurationService

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _clean_config_state():
    """Clean configuration state before and after each test.

    This fixture:
    1. Filters out test-only Configuration classes from the registry
    2. Clears configuration instances
    3. Restores the original state after the test
    """
    from agent_platform.core.configurations.base import ConfigMeta

    # Save original registry
    original_registry = ConfigMeta._concrete_configs.copy()

    # Filter out test configurations (those defined in test modules)
    production_configs = {
        path: cls
        for path, cls in original_registry.items()
        if not any(
            test_marker in path
            for test_marker in [
                "test_",  # test_configuration_manager.TestConfig
                "test_base",  # platforms.test_base.MockPlatformConfigs
                "Mock",  # Any Mock classes
            ]
        )
    }

    # Replace registry with only production configs
    ConfigMeta._concrete_configs.clear()
    ConfigMeta._concrete_configs.update(production_configs)

    # Clear configuration instances
    ConfigurationService.reset()
    Configuration._instances.clear()

    yield

    # Restore original state
    ConfigMeta._concrete_configs.clear()
    ConfigMeta._concrete_configs.update(original_registry)
    ConfigurationService.reset()
    Configuration._instances.clear()


def test_default_configuration_regression(tmp_path: "Path", file_regression) -> None:
    """Test that the default configuration remains stable across changes.

    This regression test captures the complete default configuration to ensure
    that when configuration classes are moved or refactored, developers must
    explicitly update the baseline, making them more deliberate about changes.

    Note: This test lives in its own directory (server/tests/regression/) to
    avoid pytest collecting test configuration classes from other test modules,
    which would pollute the baseline.
    """
    # Patch _apply_environment_variables to prevent env vars from affecting defaults
    # This ensures the baseline is the same in local dev and CI environments
    with patch.object(
        ConfigurationService.get_instance().__class__,
        "_apply_environment_variables",
        lambda self: None,
    ):
        config_path = tmp_path / "config.yaml"
        manager = ConfigurationService.initialize(config_path=config_path)
        configurations.load_full_config(load_trusted_architectures=False)

        # Get config and sort it before generating YAML to ensure deterministic output
        complete_config = manager.get_complete_config(include_fields_with_no_init=False)
        sorted_config = dict(sorted(complete_config.items()))

        # Temporarily replace get_complete_config to return sorted config
        original_method = manager.get_complete_config
        manager.get_complete_config = lambda **kwargs: sorted_config  # pyright: ignore[reportAttributeAccessIssue]

        try:
            export_path = tmp_path / "default_config.yaml"
            configurations.print_config(
                should_exit=False,
                export_path=export_path,
            )
        finally:
            manager.get_complete_config = original_method

        content = export_path.read_text()
        # Normalize the temp path so the test is deterministic
        content = content.replace(str(config_path), "<tmp-config-path>")

    file_regression.check(
        content,
        basename="default_configuration",
        extension=".yaml",
    )
