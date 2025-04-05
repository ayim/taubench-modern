"""Configuration management for the agent server.

This module provides a centralized system for managing all configurations
used by the agent server. It automatically discovers, loads, and persists
Configuration subclasses across the application.

## Configuration File Structure

The configuration system uses a single JSON file (configurations.json) that
stores all configurations in a hierarchical structure. Each configuration class
is stored under a key that represents its full module path plus class name.

Example structure:
```json
{
  "agent_server_types_v2.models.provider.ModelProviders": {
    "mapping": {
      "openai": {
        "api_key": "sk-xxxx",
        "organization": "org-yyyy"
      }
    }
  },
  "agent_platform.server.constants.SystemPaths": {
    "data_dir": "/path/to/data",
    "log_dir": "/path/to/logs"
  },
  "agent_platform.server.constants.SystemConfig": {
    "db_type": "sqlite",
    "log_level": "INFO",
    "log_max_backup_files": 5,
    "log_file_size": 10485760
  }
}
```

## Configuration Classes

The system separates physical paths from general system configuration settings
for better organization:

### SystemPaths

Manages all file system paths used by the agent server:

```json
"agent_platform.server.constants.SystemPaths": {
  "data_dir": "/path/to/data",            // Base directory for data storage
  "log_dir": "/path/to/logs"              // Directory for log files
}
```

Note: The derived paths (vector_database_path, domain_database_path, log_file_path,
upload_dir, config_dir) are calculated automatically and don't need to be
specified in the JSON.

### SystemConfig

Manages general configuration settings:

```json
"agent_platform.server.constants.SystemConfig": {
  "db_type": "sqlite",                    // Database type (sqlite or postgres)
  "log_level": "INFO",                    // Log level (INFO, DEBUG, etc.)
  "log_max_backup_files": 5,              // Number of log rotation files
  "log_file_size": 10485760               // Max log file size in bytes
}
```

## Usage Examples

### Accessing configuration values:

```python
# Import the appropriate helpers
from agent_platform.server.constants import (
    SystemPaths, SystemConfig, get_path, get_config
)

# Access paths with type safety
data_dir = get_path("data_dir")
upload_dir = get_path("upload_dir")

# Access settings with type safety
db_type = get_config("db_type", str)
is_debug = get_config("debug_mode", bool)

# Or create fresh instances
paths = SystemPaths.default()
log_file = paths.log_file_path

config = SystemConfig.default()
log_level = config.log_level
```

### Updating configurations:

```python
from pathlib import Path
from agent_platform.server.constants import SystemPaths, SystemConfig
from agent_platform.server.configuration_manager import get_configuration_manager

# Get the configuration manager
manager = get_configuration_manager()

# Update path configurations
new_paths = SystemPaths(
    data_dir=Path("/custom/data"),
    log_dir=Path("/custom/logs"),
)
manager.update_configuration(SystemPaths, new_paths)

# Update general settings
new_config = SystemConfig(
    db_type="postgres",
    log_level="DEBUG",
    log_max_backup_files=10,
    log_file_size=20 * 1024 * 1024,  # 20MB
)
manager.update_configuration(SystemConfig, new_config)
```

### Manual Configuration

While the system can create default configurations automatically, you may want to
manually edit the configuration file for specific environments:

1. Initialize the application once to generate the default configurations.json
2. Edit the file at {DATA_DIR}/config/configurations.json
3. Restart the application to load your custom settings

Note: Path values in the JSON file are stored as strings and automatically converted
to Path objects when loaded.
"""

import importlib
import json
import pkgutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeVar

import structlog

from agent_platform.core.configurations import ConfigMeta, Configuration
from agent_platform.server.constants import default_config_path

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

T = TypeVar("T", bound=Configuration)


class ConfigurationManager:
    """Manages configuration loading and access throughout the system."""

    def __init__(
        self,
        config_path: Path | None = None,
        packages_to_scan: Sequence[str] | None = None,
        config_modules: Sequence[str] | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file. If None, uses default path.
            packages_to_scan: List of package names to recursively scan for
                Configuration classes. This is the preferred way to load
                configurations.
            config_modules: List of specific module paths to load configurations
                from. Only used if packages_to_scan is None.
            overrides: Dictionary of overrides to apply to configurations.
                Format: {config_path: {attr_name: value}}
        """
        self._config_path = config_path or default_config_path()
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_classes: dict[str, type[Configuration]] = {}
        self.packages_to_scan = packages_to_scan or []
        self.config_modules = config_modules
        self.overrides = overrides or {}

        # Main configuration file
        self._main_config_file = self._config_path

        # Initial load of configuration data
        self._load()

    def _load(self) -> None:
        """Load and initialize all configurations.

        This method:
        1. Loads the configuration file data
        2. Ensures all packages are imported to trigger class registration
        3. Gets the concrete configuration classes from the registry
        4. Applies file-based and override-based configurations
        """
        # Clear existing configuration classes
        self.config_classes.clear()

        # Load configuration data from file
        self._config_data = self._load_config_data()

        # Import the specified packages to ensure the Configuration metaclass
        # can register all the concrete configuration classes
        self._import_packages()

        # Now get all concrete configuration classes from the metaclass registry
        self._load_registered_configurations()

        # Log initialization status
        config_file_exists = self._main_config_file.exists()
        logger.info(
            f"Loaded configurations from {'file' if config_file_exists else 'defaults'}"
            f"{f', config_file={self._main_config_file}' if config_file_exists else ''}"
            f", packages_scanned={self.packages_to_scan}"
            f", config_modules={self.config_modules}"
            f", num_configs={len(self.config_classes)}",
        )

    def _import_packages(self) -> None:
        """Import packages to ensure configuration classes are registered.

        This triggers the metaclass registration for all Configuration subclasses.
        """
        # Import all specified packages
        if self.packages_to_scan:
            for package_name in self.packages_to_scan:
                try:
                    importlib.import_module(package_name)
                    # Also import all submodules to ensure all classes are registered
                    self._import_submodules(package_name)
                    logger.debug(f"Imported package {package_name}")
                except ImportError as e:
                    logger.warning(f"Failed to import package {package_name}: {e}")

        # Import specific modules if specified
        if self.config_modules:
            for module_path in self.config_modules:
                try:
                    importlib.import_module(module_path)
                    logger.debug(f"Imported module {module_path}")
                except ImportError as e:
                    logger.warning(f"Failed to import module {module_path}: {e}")

    def _import_submodules(self, package_name: str) -> None:
        """Recursively import all submodules of a package.

        Args:
            package_name: The name of the package
        """
        try:
            package = importlib.import_module(package_name)
            package_path = getattr(package, "__path__", None)

            if not package_path:
                return  # Not a package

            for _, name, is_pkg in pkgutil.iter_modules(package_path):
                full_name = f"{package_name}.{name}"
                try:
                    importlib.import_module(full_name)
                    if is_pkg:
                        # Recursively import subpackages
                        self._import_submodules(full_name)
                except ImportError:
                    pass  # Skip modules that can't be imported
        except ImportError:
            pass  # Skip packages that can't be imported

    def _load_registered_configurations(self) -> None:
        """Load all registered concrete configuration classes.

        This uses the metaclass registry to get all concrete configuration classes.
        """
        # Get all concrete configuration classes from the metaclass registry
        for config_path, config_class in ConfigMeta.get_concrete_configs().items():
            if config_path not in self.config_classes:
                self._load_configuration(config_class)

    def _load_config_data(self) -> dict[str, dict[str, Any]]:
        """Load configuration data from file and apply overrides.

        Returns:
            Dictionary containing configuration data with overrides applied.
        """
        config_data: dict[str, dict[str, Any]] = {}

        # Load from file if it exists
        if self._main_config_file.exists():
            with self._main_config_file.open() as f:
                config_data = json.load(f)

        # Apply overrides to config data
        for config_path, attrs in self.overrides.items():
            if config_path not in config_data:
                config_data[config_path] = {}
            config_data[config_path].update(attrs)

        return config_data

    @property
    def config_path(self) -> Path:
        """Get the path to the configuration file."""
        return self._main_config_file

    @property
    def config_data(self) -> dict[str, dict[str, Any]]:
        """Get the configuration data."""
        return self._config_data

    def get_complete_config(self) -> dict[str, dict[str, Any]]:
        """Get the complete configuration data including all defaults.

        This includes all registered configuration classes with their current values,
        which may be either from the configuration file or defaults.

        Returns:
            Dictionary containing all configuration values with their defaults.
        """
        complete_config: dict[str, dict[str, Any]] = {}

        for config_path, config_class in self.config_classes.items():
            # Get the current instance which has either values from
            # config file or defaults
            instance = config_class._instances.get(config_class, config_class.default())
            # Add the config values to the complete configuration
            complete_config[config_path] = instance.to_dict()

        return complete_config

    def _get_config_path(self, config_class: type[T]) -> str:
        """Generate a configuration path for a class.

        Args:
            config_class: The configuration class

        Returns:
            String representing the path to this configuration in the JSON structure
        """
        module_parts = config_class.__module__.split(".")
        class_name = config_class.__name__

        # Create a path like "agent_server_types_v2.models.provider.ModelProviders"
        return f"{'.'.join(module_parts)}.{class_name}"

    def _load_configuration(self, config_class: type[Configuration]) -> None:
        """Load a specific configuration class.

        This will:
        1. Register the configuration class
        2. Check if configuration exists in the main JSON file
        3. If it exists, create an instance from the saved data
        4. If not, create a default instance
        """
        config_path = self._get_config_path(config_class)
        self.config_classes[config_path] = config_class

        try:
            # Check if configuration exists in the main JSON
            if config_path in self._config_data:
                # Create instance from saved data
                instance = config_class.from_dict(self._config_data[config_path])
                # Set the instance as the singleton
                config_class.set_instance(instance)
                logger.debug(
                    f"Loaded configuration from file: {config_class.__name__} "
                    f"at {config_path}",
                )
            else:
                # Create default config
                instance = config_class.default()
                # Set the instance as the singleton
                config_class.set_instance(instance)
                logger.debug(
                    f"Using default configuration (no entry in file): "
                    f"{config_class.__name__} at {config_path}",
                )
        except Exception as e:
            logger.error(
                f"Failed to load configuration: {config_class.__name__} "
                f"at {config_path}: {e!s}",
            )
            # Still create a default instance
            instance = config_class.default()
            config_class.set_instance(instance)

    def reload(
        self,
        packages_to_scan: Sequence[str] | None = None,
        config_modules: Sequence[str] | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Reload all configurations with optional new settings.

        Args:
            packages_to_scan: List of package names to scan. If None, uses existing.
            config_modules: List of specific module paths. If None, uses existing.
            overrides: Dictionary of overrides. If None, uses existing.
        """
        # Update settings if provided
        if packages_to_scan is not None:
            self.packages_to_scan = packages_to_scan
        if config_modules is not None:
            self.config_modules = config_modules
        if overrides is not None:
            self.overrides = overrides

        # Reload everything
        try:
            self._load()
        except Exception as e:
            logger.warning(
                f"Configuration loading error: {e!s}. Using defaults. "
                "Please refer to documentation.",
            )

    def update_configuration(self, config_class: type[T], new_instance: T) -> None:
        """Update a specific configuration with new values.

        Args:
            config_class: The configuration class to update
            new_instance: The new instance with updated values
        """
        config_path = self._get_config_path(config_class)
        # Update the singleton instance
        config_class.set_instance(new_instance)
        # Also update the config data for persistence
        self._config_data[config_path] = new_instance.to_dict()
        logger.warning(
            f"Updated configuration: {config_class.__name__} at {config_path}",
        )


# Global instance
_manager: ConfigurationManager | None = None


def init_configurations(
    config_path: Path | str | None = None,
    packages_to_scan: Sequence[str] | None = None,
    config_modules: Sequence[str] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
    *,
    reinitialize: bool = False,
) -> None:
    """Initialize the configuration system.

    Args:
        config_path: Path to the configuration file. If None, uses default.
        packages_to_scan: List of package names to recursively scan for Configuration
            classes. This is the preferred way to load configurations.
        config_modules: List of specific module paths to load configurations from.
            Only used if packages_to_scan is None.
        overrides: Dictionary of overrides to apply to configurations.
            Format: {config_path: {attr_name: value}}
        reinitialize: If True, forces reinitialization even if already initialized.
            Primarily used for testing.

    Should be called during server startup.
    """
    global _manager  # noqa: PLW0603

    if _manager is None or reinitialize:
        # Create a new manager if none exists or reinitialize is requested
        if isinstance(config_path, str):
            config_path = Path(config_path)
        _manager = ConfigurationManager(
            config_path,
            packages_to_scan,
            config_modules,
            overrides,
        )
    else:
        # Manager already exists, update its configuration
        logger.info("Configuration manager already initialized, updating configuration")

        # Update overrides and reload configurations
        new_overrides = _manager.overrides.copy()
        if overrides:
            for override_config_path, override_attrs in overrides.items():
                if override_config_path not in new_overrides:
                    new_overrides[override_config_path] = {}
                new_overrides[override_config_path].update(override_attrs)

        _manager.reload(
            packages_to_scan=packages_to_scan,
            config_modules=config_modules,
            overrides=new_overrides,
        )


def get_configuration_manager() -> ConfigurationManager:
    """Get the global configuration manager instance.

    Returns:
        ConfigurationManager: The global configuration manager instance.

    Raises:
        RuntimeError: If the configuration manager has not been initialized.
    """
    if _manager is None:
        # Instead of raising an error, initialize with defaults as a fallback
        logger.warning(
            "Configuration manager not initialized. Initializing with defaults. "
            "This is unexpected and may indicate a problem with the startup sequence.",
        )
        init_configurations()

    if _manager is None:
        # If initialization with defaults also failed, then raise an error
        raise RuntimeError(
            "Configuration manager initialization failed. This is a critical error.",
        )

    return _manager
