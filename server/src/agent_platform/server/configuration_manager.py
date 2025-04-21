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

### Initializing the configuration system:

```python
from agent_platform.server.configuration_manager import ConfigurationService

# Initialize with defaults
ConfigurationService.initialize()

# Or with custom settings
ConfigurationService.initialize(
    config_path="/custom/path/config.json",
    packages_to_scan=["agent_platform.server", "agent_server_types_v2"],
    overrides={"some.path.Config": {"setting": "value"}}
)
```

### Accessing configuration values:

```python
from agent_platform.server.constants import SystemPaths, SystemConfig
from agent_platform.server.configuration_manager import ConfigurationService

# Get the manager
manager = ConfigurationService.get_instance()

# Get a configuration class and update it
paths = SystemPaths.default()
paths.data_dir = Path("/new/path")
manager.update_configuration(SystemPaths, paths)
```

### FastAPI dependency injection:

```python
from fastapi import Depends
from agent_platform.server.configuration_manager import ConfigurationManagerDependency

@app.get("/config")
def get_config(config_manager: ConfigurationManagerDependency):
    # Use the config manager
    return config_manager.get_complete_config()
```
"""

import importlib
import json
import pkgutil
from collections.abc import Callable, Sequence
from dataclasses import Field, fields
from pathlib import Path
from typing import Annotated, Any, ClassVar, TypeVar

import structlog
import yaml
from fastapi import Depends

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.parsers import parse_field_value
from agent_platform.server.constants import default_config_path
from agent_platform.server.env_vars import get_env_var

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

T = TypeVar("T", bound=Configuration)

CustomParser = Callable[[str], Any]


class ConfigurationManager:
    """Manages configuration loading and access throughout the system.

    The configuration system now follows a clear precedence order:
    1. Command line arguments (highest priority, specified through overrides)
    2. Environment variables (set in environment or through env_vars.py)
    3. Configuration file values (from the JSON configuration file)
    4. Default values (hardcoded in the configuration classes)

    This ensures that command line arguments can override environment variables,
    which can override configuration file values, which can override defaults.
    Each configuration source is applied in order, with higher priority sources
    taking precedence over lower priority ones.
    """

    def __init__(
        self,
        config_path: Path | None = None,
        packages_to_scan: Sequence[str] | None = None,
        config_modules: Sequence[str] | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file or directory. If a directory is
                provided, all YAML (.yaml, .yml) and JSON (.json) files in that
                directory will be loaded and merged. If None, uses default path.
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

        # Apply environment variable overrides
        self._apply_environment_variables()

        # Apply command line overrides
        self._apply_overrides()

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

    def _sort_configurations_by_dependencies(
        self,
        config_classes: dict[str, type[Configuration]],
    ) -> list[str]:
        """Sort configuration classes based on their dependencies.

        Performs a topological sort to ensure dependencies are loaded before
        the configurations that depend on them.

        Args:
            config_classes: Dictionary mapping configuration paths to
                configuration classes

        Returns:
            List of configuration paths sorted by dependency order
        """
        # Build a dependency graph for topological sorting
        dependency_graph: dict[str, set[str]] = {}
        for config_path, config_class in config_classes.items():
            # Add the node to the graph if it doesn't exist
            if config_path not in dependency_graph:
                dependency_graph[config_path] = set()

            # Add dependencies to the graph
            for dependency in getattr(config_class, "depends_on", []):
                # Get the path for the dependency class
                dependency_path = self._get_config_path(dependency)

                # Add the dependency to this class's dependencies
                dependency_graph[config_path].add(dependency_path)

                # Ensure the dependency exists in the graph
                if dependency_path not in dependency_graph:
                    dependency_graph[dependency_path] = set()

        # Perform topological sort (Kahn's algorithm)
        sorted_paths = []

        # Find nodes with no dependencies (roots)
        roots = [node for node, deps in dependency_graph.items() if not deps]

        # Process all roots
        while roots:
            # Remove a root from the roots list
            root = roots.pop(0)
            sorted_paths.append(root)

            # Check all nodes that might depend on this one
            for node, deps in list(dependency_graph.items()):
                if root in deps:
                    # Remove the processed dependency
                    dependency_graph[node].remove(root)

                    # If this node now has no dependencies, add it to roots
                    if not dependency_graph[node]:
                        roots.append(node)

        # Check for circular dependencies
        if any(deps for deps in dependency_graph.values()):
            logger.warning(
                "Circular dependencies detected in configuration classes. "
                "Some configurations may not be properly initialized.",
            )

        return sorted_paths

    def _load_registered_configurations(self) -> None:
        """Load all registered concrete configuration classes.

        This uses the Configuration registry to get all concrete configuration classes.
        This method sorts configurations by dependencies to ensure that dependencies
        are loaded before the configurations that depend on them.
        """
        # Get all concrete configuration classes from the Configuration registry
        config_classes = Configuration.get_concrete_configs()

        # Sort configurations by dependencies
        sorted_paths = self._sort_configurations_by_dependencies(config_classes)

        # Load configurations in dependency order
        for config_path in sorted_paths:
            if config_path in config_classes and config_path not in self.config_classes:
                self._load_configuration(config_classes[config_path])

        # Load any remaining configurations not covered by the dependency resolution
        for config_path, config_class in config_classes.items():
            if config_path not in self.config_classes:
                self._load_configuration(config_class)

    def _load_config_data(self) -> dict[str, dict[str, Any]]:
        """Load configuration data from file or directory.

        If the config path is a directory, loads and merges all YAML/JSON files
        found in that directory. If it's a file, loads that specific file.

        Returns:
            Dictionary containing configuration data from the file(s).
        """
        config_data: dict[str, dict[str, Any]] = {}

        # Check if path exists
        if not self._main_config_file.exists():
            return config_data

        # If the path is a directory, process all config files
        if self._main_config_file.is_dir():
            yaml_extensions = {".yaml", ".yml"}
            json_extensions = {".json"}
            config_files = [
                f
                for f in self._main_config_file.iterdir()
                if f.is_file()
                and f.suffix.lower() in yaml_extensions.union(json_extensions)
            ]

            for config_file in config_files:
                try:
                    with config_file.open() as f:
                        file_extension = config_file.suffix.lower()
                        file_data: dict[str, dict[str, Any]] = {}

                        if file_extension in yaml_extensions:
                            file_data = yaml.safe_load(f) or {}
                        elif file_extension in json_extensions:
                            file_data = json.load(f)

                        # Merge the file data into the combined config data
                        self._deep_merge_configs(config_data, file_data)

                    logger.debug(f"Loaded configuration from {config_file}")
                except Exception as e:
                    logger.error(
                        f"Failed to load configuration from {config_file}: {e}",
                    )
                    # Continue with other files
        else:
            # Load from single file
            try:
                with self._main_config_file.open() as f:
                    # Determine whether to load as YAML or JSON based on file extension
                    file_extension = self._main_config_file.suffix.lower()
                    if file_extension in (".yaml", ".yml"):
                        config_data = yaml.safe_load(f) or {}
                    else:
                        config_data = json.load(f)
                logger.debug(f"Loaded configuration from {self._main_config_file}")
            except Exception as e:
                logger.error(
                    f"Failed to load configuration from {self._main_config_file}: {e}",
                )
                # Continue with empty config_data

        return config_data

    def _deep_merge_configs(
        self,
        target: dict[str, Any],
        source: dict[str, Any],
    ) -> None:
        """Deep merge source dict into target dict.

        Args:
            target: Target dictionary to merge into (modified in-place)
            source: Source dictionary to merge from
        """
        for key, value in source.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                # If both target and source have a dict at this key, recurse
                self._deep_merge_configs(target[key], value)
            else:
                # Otherwise, override/set the value in target
                target[key] = value

    def _apply_overrides(self) -> None:
        """Apply command line overrides to configuration data.

        Command line overrides have the highest precedence and are applied after
        both the configuration file and environment variables.
        """
        # Track changes to configurations for logging
        changes_applied = {}

        # Apply overrides to config data
        for config_path, attrs in self.overrides.items():
            if config_path not in self._config_data:
                self._config_data[config_path] = {}

            # Update the config data with overrides
            self._config_data[config_path].update(attrs)

            # Create and set a new instance with the overridden values if this is a
            # registered class
            if config_path in self.config_classes:
                config_class = self.config_classes[config_path]
                try:
                    instance = config_class.from_dict(self._config_data[config_path])
                    config_class.set_instance(instance)
                    changes_applied[config_class.__name__] = list(attrs.keys())
                except Exception as e:
                    logger.error(
                        f"Failed to apply command line overrides to "
                        f"{config_class.__name__}: {e}",
                    )

        # Log a summary of changes if any were applied
        if changes_applied:
            changes_applied_str = ", ".join(
                f"{cls}({', '.join(fields)})" for cls, fields in changes_applied.items()
            )
            logger.info(
                f"Applied command line overrides to: {changes_applied_str}",
            )

    @property
    def config_path(self) -> Path:
        """Get the path to the configuration file."""
        return self._main_config_file

    @property
    def config_data(self) -> dict[str, dict[str, Any]]:
        """Get the configuration data."""
        return self._config_data

    def get_complete_config(
        self,
        include_fields_with_no_init: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """Get the complete configuration data including all defaults.

        This includes all registered configuration classes with their current values,
        which may be either from the configuration file or defaults.

        Args:
            include_fields_with_no_init: If True, include fields that have not been
                that are configured to not be included in a Configurations init method.

        Returns:
            Dictionary containing all configuration values with their defaults.
        """
        complete_config: dict[str, dict[str, Any]] = {}

        for config_path, config_class in self.config_classes.items():
            # Get the current instance which has either values from
            # config file or defaults
            instance = config_class._instances.get(
                config_class,
                config_class.get_default_instance(),
            )
            # Add the config values to the complete configuration
            config_data = instance.to_dict(include_fields_with_no_init)

            complete_config[config_path] = config_data

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
        2. Check if configuration exists in the main configuration file data
        3. If it exists, create an instance from the saved data
        4. If not, create a default instance
        """
        config_path = self._get_config_path(config_class)
        self.config_classes[config_path] = config_class

        try:
            # Check if configuration exists in the main configuration file data
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
                instance = config_class.get_default_instance()
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
            instance = config_class.get_default_instance()
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
            # Clear and reload configuration data from file
            self._config_data = self._load_config_data()

            # Import packages (which trigger metaclass registration)
            self._import_packages()

            # Load registered configurations
            self._load_registered_configurations()

            # Apply environment variables after loading from file
            self._apply_environment_variables()

            # Apply command line overrides (highest precedence)
            self._apply_overrides()
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

    def _parse_field_env_vars(self, field: Field) -> Any:
        """Parse environment variables for a field.

        Args:
            field: The field to parse environment variables for

        Returns:
            The parsed value of the field
        """
        env_vars = field.metadata["env_vars"] if "env_vars" in field.metadata else []
        if len(env_vars) > 0:
            env_var_value = get_env_var(env_vars)
            if env_var_value is not None:
                # Parse using the appropriate parser for the field type
                try:
                    return parse_field_value(field, env_var_value)
                except Exception as e:
                    logger.error(
                        f"Failed to parse environment variable for "
                        f"field {field.name}: {e}",
                    )
                    # Fall back to using the raw value
                    return env_var_value

    def _apply_environment_variables(self) -> None:
        """Apply environment variables as overrides to configurations.

        This method dynamically processes all registered configuration classes and
        applies environment variables based on the metadata defined in each field.

        Each configuration field can define an "env_vars" list in its metadata,
        which contains environment variable names in order of precedence. The first
        variable that is set will be used.

        Example field definition:
            db_type: str = field(
                default="sqlite",
                metadata={
                    "description": "Database type",
                    "env_vars": ["SEMA4AI_AGENT_SERVER_DB_TYPE", "DB_TYPE"],
                }
            )

        The method applies environment variables with the following precedence:
        1. Command line overrides (already in self.overrides)
        2. Environment variables (applied here)
        3. Configuration file (already loaded)
        4. Default values (used when creating instances)
        """
        # Track changes to configurations for logging
        changes_applied = {}

        # Process each registered configuration class
        for config_path, config_class in self.config_classes.items():
            # Skip if no fields (unlikely but possible)
            class_fields = fields(config_class)
            if not class_fields:
                continue

            # Get or create the config data entry
            if config_path not in self._config_data:
                self._config_data[config_path] = {}

            env_overrides = {}

            # Check each field for env_vars metadata
            for field in class_fields:
                parsed_value = self._parse_field_env_vars(field)
                if parsed_value is not None:
                    env_overrides[field.name] = parsed_value

            # Apply the overrides if we have any
            if env_overrides:
                self._config_data[config_path].update(env_overrides)
                changes_applied[config_class.__name__] = list(env_overrides.keys())

                # Create a new instance with the updated values
                try:
                    instance = config_class.from_dict(self._config_data[config_path])
                    config_class.set_instance(instance)
                except Exception as e:
                    logger.error(
                        f"Failed to apply environment variable overrides to "
                        f"{config_class.__name__}: {e}",
                    )

        # Log a summary of changes if any were applied
        if changes_applied:
            changes_applied_str = ", ".join(
                f"{cls}({', '.join(fields)})" for cls, fields in changes_applied.items()
            )
            logger.info(
                f"Applied environment variable overrides to: {changes_applied_str}",
            )


class ConfigurationService:
    """Service for configuration manager using a singleton pattern.

    This service provides access to the global configuration manager instance.
    Client code should use this service to access configurations instead of the
    deprecated global functions.

    Examples:
        Initialize the configuration system:
        ```python
        from agent_platform.server.configuration_manager import ConfigurationService

        # Initialize with defaults
        ConfigurationService.initialize()

        # Or with custom settings
        ConfigurationService.initialize(
            config_path="/custom/path/config.json",
            packages_to_scan=["agent_platform.server"],
            overrides={"some.path.Config": {"setting": "value"}}
        )
        ```

        Access and update configurations:
        ```python
        from agent_platform.server.constants import SystemPaths
        from agent_platform.server.configuration_manager import ConfigurationService

        # Get the manager
        manager = ConfigurationService.get_instance()

        # Access a configuration
        paths = SystemPaths.default()

        # Update a configuration
        paths.data_dir = Path("/new/path")
        manager.update_configuration(SystemPaths, paths)
        ```
    """

    _instance: ClassVar[ConfigurationManager | None] = None

    @classmethod
    def initialize(
        cls,
        config_path: Path | str | None = None,
        packages_to_scan: Sequence[str] | None = None,
        config_modules: Sequence[str] | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> ConfigurationManager:
        """Initialize the configuration manager with the given settings.

        This method is the recommended way to set up the configuration system.
        It creates a new configuration manager instance or reinitializes the
        existing one with the provided settings.

        Args:
            config_path: Path to the configuration file or directory.
            packages_to_scan: List of package names to scan for Configuration classes.
            config_modules: List of specific module paths to load configurations from.
            overrides: Dictionary of overrides to apply to configurations.

        Returns:
            The initialized configuration manager instance.
        """
        return cls.get_instance(
            config_path=config_path,
            packages_to_scan=packages_to_scan,
            config_modules=config_modules,
            overrides=overrides,
            reinitialize=True,
        )

    @classmethod
    def get_instance(
        cls,
        config_path: Path | str | None = None,
        packages_to_scan: Sequence[str] | None = None,
        config_modules: Sequence[str] | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
        *,
        reinitialize: bool = False,
    ) -> ConfigurationManager:
        """Get the singleton instance of the configuration manager.

        If the instance doesn't exist yet, it will be created with the provided
        settings or defaults. If it already exists, the settings will only be
        applied if reinitialize is True.

        For explicit initialization with new settings, use the initialize() method.

        Args:
            config_path: Path to the configuration file or directory.
            packages_to_scan: List of package names to scan for Configuration classes.
            config_modules: List of specific module paths to load configurations from.
            overrides: Dictionary of overrides to apply to configurations.
            reinitialize: If True, forces reinitialization even if already initialized.

        Returns:
            The configuration manager instance.
        """
        if isinstance(config_path, str):
            config_path = Path(config_path)

        if cls._instance is None or reinitialize:
            cls._instance = ConfigurationManager(
                config_path,
                packages_to_scan,
                config_modules,
                overrides,
            )
        elif any(
            param is not None
            for param in [config_path, packages_to_scan, config_modules, overrides]
        ):
            # Manager already exists and parameters were provided,
            # update its configuration
            logger.info(
                "Configuration manager already initialized, updating configuration",
            )

            # Update overrides and reload configurations
            new_overrides = cls._instance.overrides.copy()
            if overrides:
                for override_config_path, override_attrs in overrides.items():
                    if override_config_path not in new_overrides:
                        new_overrides[override_config_path] = {}
                    new_overrides[override_config_path].update(override_attrs)

            cls._instance.reload(
                packages_to_scan=packages_to_scan,
                config_modules=config_modules,
                overrides=new_overrides,
            )

        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the configuration manager instance (for testing)."""
        cls._instance = None

    @classmethod
    def set_for_testing(cls, manager: ConfigurationManager) -> None:
        """Set a custom configuration manager implementation (for testing).

        Args:
            manager: The configuration manager implementation to use.
        """
        cls._instance = manager


# Legacy functions for backward compatibility
# These are deprecated and might be removed in a future version
# New code should use ConfigurationService directly


def init_configurations(
    config_path: Path | str | None = None,
    packages_to_scan: Sequence[str] | None = None,
    config_modules: Sequence[str] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
    *,
    reinitialize: bool = False,
) -> None:
    """Initialize the configuration system.

    Deprecated: Use ConfigurationService.initialize() instead.

    Args:
        config_path: Path to the configuration file or directory.
        packages_to_scan: List of package names to scan for Configuration classes.
        config_modules: List of specific module paths to load configurations from.
        overrides: Dictionary of overrides to apply to configurations.
        reinitialize: If True, forces reinitialization even if already initialized.

    Should be called during server startup.
    """
    logger.warning(
        "The init_configurations function is deprecated. "
        "Use ConfigurationService.initialize() instead.",
    )
    if reinitialize:
        ConfigurationService.initialize(
            config_path,
            packages_to_scan,
            config_modules,
            overrides,
        )
    else:
        ConfigurationService.get_instance(
            config_path,
            packages_to_scan,
            config_modules,
            overrides,
        )


def get_configuration_manager() -> ConfigurationManager:
    """Get the global configuration manager instance.

    Deprecated: Use ConfigurationService.get_instance() instead.

    Returns:
        The global configuration manager instance.

    Raises:
        RuntimeError: If the configuration manager has not been initialized.
    """
    logger.warning(
        "The get_configuration_manager function is deprecated. "
        "Use ConfigurationService.get_instance() instead.",
    )
    instance = ConfigurationService._instance

    if instance is None:
        # Instead of raising an error, initialize with defaults as a fallback
        logger.warning(
            "Configuration manager not initialized. Initializing with defaults. "
            "This is unexpected and may indicate a problem with the startup sequence.",
        )
        instance = ConfigurationService.get_instance()

    if instance is None:
        # If initialization with defaults also failed, then raise an error
        raise RuntimeError(
            "Configuration manager initialization failed. This is a critical error.",
        )

    return instance


def get_configuration_manager_dependency() -> ConfigurationManager:
    """FastAPI dependency to provide the configuration manager.

    Returns:
        The configuration manager instance.
    """
    return ConfigurationService.get_instance()


ConfigurationManagerDependency = Annotated[
    ConfigurationManager,
    Depends(get_configuration_manager_dependency),
]
