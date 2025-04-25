"""Configuration classes support default values and loading from JSON."""

import dataclasses
from dataclasses import Field, asdict, dataclass, fields
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Required,
    TypedDict,
    TypeVar,
)

import structlog

from agent_platform.core.configurations.parsers import Parser, parse_field_value
from agent_platform.core.configurations.representers import Representer

T = TypeVar("T", bound="Configuration")

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class FieldMetadata(TypedDict, total=False):
    """Metadata for a field in a configuration class."""

    description: Required[str]
    """The description of the field."""
    env_vars: list[str]
    """The environment variables that can be used to set the field, the first
    one found will be used. You can use glob patterns to match multiple
    environment variables.
    """
    parser: type[Parser]
    """The parser to use for the field, this is used when the field is loaded
    from the command line, configuration file or environment variable."""
    representer: type[Representer]
    """The representer to use for the field, this is used to represent the field
    in a YAML-based configuration file."""


class ConfigMeta(type):
    """Metaclass for Configuration classes to enable class attribute access.

    This metaclass intercepts attribute access on Configuration classes
    to retrieve values from the singleton instance. It also automatically marks
    classes as abstract or concrete for configuration management.
    """

    # Registry of concrete configuration classes
    _concrete_configs: ClassVar[dict[str, type]] = {}

    def __new__(cls, name, bases, attrs):
        # Create the class instance
        super_cls = super().__new__(cls, name, bases, attrs)

        # Skip the base Configuration class itself
        if (
            name == "Configuration"
            and attrs.get("__module__") == "agent_platform.core.configurations.base"
        ):
            return super_cls

        # Determine if this is an abstract base class or a concrete configuration
        # A class is abstract if it's explicitly marked as such or is one of our
        # known base classes like MapConfiguration
        is_abstract = attrs.get("_abstract", False)

        # If not abstract, register this as a concrete configuration class
        if not is_abstract:
            # Generate full path for the configuration class
            full_path = f"{super_cls.__module__}.{super_cls.__name__}"
            cls._concrete_configs[full_path] = super_cls

        return super_cls

    def __getattribute__(cls, name: str) -> Any:
        """Intercepts all attribute access at the class level.

        For dataclass fields, returns values from the singleton instance.
        For normal class attributes, uses standard attribute lookup.

        Args:
            name: The attribute name to get

        Returns:
            The attribute value, either from the class or singleton instance
        """
        # Always allow access to special attributes and methods directly
        if name.startswith("__") and name.endswith("__"):
            return super().__getattribute__(name)

        # We need to use super().__getattribute__ to access our own attributes
        # to avoid infinite recursion
        try:
            # Access _instances through super() to avoid recursion
            instances = super().__getattribute__("_instances")

            # Check if this class has an instance in the registry
            if cls in instances and dataclasses.is_dataclass(cls):
                # Use direct dataclasses.fields instead of calling fields(cls)
                # which would trigger another __getattribute__ call
                field_names = [f.name for f in dataclasses.fields(cls)]

                if name in field_names:
                    # Get the value from the singleton instance
                    instance = instances[cls]
                    return object.__getattribute__(instance, name)
            else:
                # No instance exists yet, try to create a default instance
                try:
                    # Get the default method
                    default_method = super().__getattribute__("get_default_instance")
                    # Create a default instance
                    default_instance = default_method()
                    # Check if the attribute is a field on the default instance
                    assert dataclasses.is_dataclass(cls)
                    field_names = [f.name for f in dataclasses.fields(cls)]
                    if name in field_names:
                        return getattr(default_instance, name)
                except (AssertionError, TypeError, ValueError, AttributeError):
                    # Failed to create default instance or get field
                    pass
        except (TypeError, ValueError, AttributeError):
            # Not a dataclass, error getting fields, or no instance
            # Fall back to normal behavior
            pass

        # Default to normal attribute lookup for non-field attributes
        return super().__getattribute__(name)

    def __getattr__(cls, name: str) -> Any:
        """Get configuration value by attribute name at class level.

        Enables direct attribute access like MyConfig.name instead of MyConfig["name"].

        Args:
            name: The attribute name to get

        Returns:
            The value of the attribute from the singleton instance

        Raises:
            AttributeError: If the attribute doesn't exist
        """
        # Access _instances through super() to avoid recursion
        try:
            instances = super().__getattribute__("_instances")

            # Check if this class has an instance in the registry
            if cls in instances:
                # Get the value from the singleton instance
                instance = instances[cls]
                return getattr(instance, name)
        except (AttributeError, KeyError):
            # No instances or no instance for this class
            pass

        # If no instance exists, try to get the attribute directly from the class
        try:
            return super().__getattribute__(name)
        except AttributeError as e:
            # Attribute doesn't exist on the class either
            raise AttributeError(f"{cls.__name__} has no attribute '{name}'") from e

    @classmethod
    def get_concrete_configs(cls) -> dict[str, type]:
        """Get all registered concrete configuration classes.

        Returns:
            Dictionary mapping configuration paths to their class objects.
        """
        return cls._concrete_configs


@dataclass(frozen=True)
class Configuration(metaclass=ConfigMeta):
    """Base class for all configurations.

    This class provides comprehensive functionality for configuration management:
    - Loading from and converting to dictionaries
    - Default value support and initialization
    - Type validation and checking
    - Serialization and deserialization
    - Class-level singleton access
    - Field metadata support with descriptions
    - Type-specific parsing and representation

    ## Singleton Pattern

    The Configuration system uses a singleton pattern to ensure only
    one instance of each configuration exists. This is important because
    configurations are loaded once during startup and should remain
    consistent throughout the application's lifetime.

    ### Accessing Configurations

    After initialization, configurations can be accessed in two ways:
    1. Using class-level attribute access (recommended):
        value = MyConfig.count  # 10 (default)
        value = MyConfig.name   # "default"

    2. Using class-level subscription:
        value = MyConfig["count"]  # 10 (default)
        value = MyConfig["name"]   # "default"

    ### Configuration Instance Management

    The singleton instance is set during application startup by the
    ConfigurationManager. You should not create instances directly,
    but rather use the class-level accessors after initialization.

    To update a configuration, use the ConfigurationManager to ensure
    the singleton is updated properly:

        manager = ConfigurationService.get_instance()
        new_config = MyConfig(name="new", count=20)
        manager.update_configuration(MyConfig, new_config)

    ## Field Metadata

    Configuration fields can include metadata for enhanced functionality:
    - `description`: Documentation for the field's purpose
    - `env_vars`: Environment variables that can set this field value
    - `parser`: Custom parser for handling field value conversion
    - `representer`: Custom representer for serialization

    Example with field metadata:
        @dataclass(frozen=True)
        class MyConfig(Configuration):
            name: str = field(
                metadata={"description": "The name of the configuration"}
            )
            count: int = field(
                default=10,
                metadata={
                    "description": "Count value",
                    "env_vars": ["MY_COUNT", "LEGACY_COUNT"]
                }
            )

    ## Type Parsing and Representation

    The Configuration system supports intelligent parsing of values from strings
    and other formats through specialized parsers. This is useful when loading
    configuration from environment variables, CLI arguments, or config files.

    Similarly, custom representers control how configuration values are serialized
    when saving to files or displaying in UIs.

    ## Subclassing

    When creating your own configuration class:
    1. Inherit from Configuration
    2. Use @dataclass(frozen=True) decorator
    3. Define typed fields with optional defaults
    4. Implement classmethod default() if custom defaults are needed

    Example:
        @dataclass(frozen=True)
        class MyConfig(Configuration):
            name: str
            count: int = 10  # Default value

            @classmethod
            def get_default_instance(cls) -> "MyConfig":
                return cls(name="default")
    """

    # Indicates that the class is abstract in relation to the configuration system and
    # should not be loaded as a configuration itself.
    _abstract = True
    # Optional class variable for configuration file path
    config_path: ClassVar[Path | None] = None
    # Dictionary to store singleton instances for each Configuration subclass
    _instances: ClassVar[dict[type["Configuration"], "Configuration"]] = {}
    # Optional class variable to specify other configs that this config depends on
    depends_on: ClassVar[list[type["Configuration"]]] = []
    """Specifies dependencies between configuration classes.

    This class variable defines which other configuration classes must be loaded
    before this one. The ConfigurationManager uses this information to:
    1. Build a dependency graph of all configuration classes
    2. Perform a topological sort to determine the correct loading order
    3. Load configurations in dependency order to ensure dependencies are available

    Example:
        @dataclass(frozen=True)
        class MyConfig(Configuration):
            depends_on: ClassVar[list[type["Configuration"]]] = [
                SystemPaths,
                SystemConfig,
            ]

            # This config will only be loaded after SystemPaths and SystemConfig
            # are fully initialized, ensuring their values are available
            data_path: Path = field(
                default=SystemPaths.data_dir / "my_data"
            )

    The dependency system helps manage complex configuration relationships where
    one configuration may need values from another during initialization or in
    its __post_init__ method.
    """

    @classmethod
    def get_concrete_configs(cls) -> dict[str, type["Configuration"]]:
        """Get all registered concrete configuration classes.

        Returns:
            Dictionary mapping configuration paths to their class objects.
        """
        return ConfigMeta.get_concrete_configs()

    @classmethod
    def set_instance(cls: type[T], instance: T) -> None:
        """Set the singleton instance for this class.

        Args:
            instance: The instance to set as the singleton
        """
        cls._instances[cls] = instance

    def __getitem__(self, key: str) -> Any:
        """Get configuration value by key."""
        return getattr(self, key)

    @classmethod
    def from_dict(cls: type[T], config_dict: dict[str, Any]) -> T:
        """Load configuration from a dictionary.

        This method will parse the values of the dictionary using the field's metadata
        if those values are strings.

        Args:
            config_dict: Dictionary containing configuration values.

        Returns:
            Configuration instance with values from dictionary.

        Raises:
            TypeError: If dictionary values don't match expected types.
        """
        # Get all fields defined in the dataclass
        config_fields = {f.name: f for f in fields(cls)}

        # Filter and process the loaded config values
        validated_config = {}
        for key, value in config_dict.items():
            if key not in config_fields:
                continue

            field = config_fields[key]
            # Skip fields that should not be passed to __init__
            if field.init is False:
                continue

            try:
                # Parse the value using the appropriate parser
                parsed_value = parse_field_value(field, value)
                validated_config[key] = parsed_value
            except Exception as e:
                # Add more context to the error
                raise TypeError(
                    f"Error processing field '{key}' with value {value}: {e!s}",
                ) from e

        return cls(**validated_config)

    @classmethod
    def get_default_instance(cls: type[T]) -> T:
        """Get the default configuration instance.

        Returns:
            Configuration instance with default values.
        """
        return cls()

    def to_dict(self, include_fields_with_no_init: bool = True) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Args:
            include_fields_with_no_init: If True, include fields that have not been
                that are configured to not be included in a Configurations init method.

        Returns:
            Dictionary representation of configuration.
        """
        if include_fields_with_no_init:
            return asdict(self)
        else:
            out_dict = asdict(self)
            for field in self.get_fields():
                if field.init is False:
                    out_dict.pop(field.name)
            return out_dict

    @classmethod
    def get_fields(cls) -> tuple[Field, ...]:
        """Get all fields in the configuration.

        Returns:
            List of fields in the configuration.
        """
        return fields(cls)

    @classmethod
    def get_field_descriptions(cls) -> dict[str, str]:
        """Get the descriptions of all fields.

        Returns:
            Dictionary mapping field names to their descriptions.
        """
        descriptions = {}
        for f in fields(cls):
            if "description" in f.metadata:
                descriptions[f.name] = f.metadata["description"]
            elif f.init is False:
                descriptions[f.name] = "Not configurable"
        return descriptions

    @classmethod
    def get_field_description(cls, field_name: str) -> str | None:
        """Get the description of a specific field.

        Args:
            field_name: The name of the field to get the description for.

        Returns:
            The description of the field, or None if no description is available.
        """
        for f in fields(cls):
            if f.name == field_name and "description" in f.metadata:
                return f.metadata["description"]
        return None

    @classmethod
    def get_field_env_vars(cls, field_name: str) -> list[str]:
        """Get the environment variables that can set the value of a field.

        Args:
            field_name: The name of the field to get the environment variables for.

        Returns:
            List of environment variables that can set the value of the field.
        """
        for f in fields(cls):
            if f.name == field_name and "env_vars" in f.metadata:
                return f.metadata["env_vars"]
        return []
