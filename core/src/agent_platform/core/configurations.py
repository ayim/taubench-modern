"""Configuration classes support default values and loading from JSON."""

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, TypeVar, cast

T = TypeVar("T", bound="Configuration")


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
            and attrs.get("__module__") == "agent_platform.core.configurations"
        ):
            return super_cls

        # Determine if this is an abstract base class or a concrete configuration
        # A class is abstract if it's explicitly marked as such or is one of our
        # known base classes like MapConfiguration
        is_abstract = attrs.get("__abstract__", False)

        # MapConfiguration is explicitly marked as abstract
        if (
            name == "MapConfiguration"
            and attrs.get("__module__") == "agent_platform.core.configurations"
        ):
            is_abstract = True

        # If not abstract, register this as a concrete configuration class
        if not is_abstract:
            # Generate full path for the configuration class
            full_path = f"{super_cls.__module__}.{super_cls.__name__}"
            cls._concrete_configs[full_path] = super_cls

        return super_cls

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
        try:
            return cls.__class_getitem__(name)
        except (KeyError, AttributeError) as e:
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

    This class provides common functionality for JSON-based configurations including:
    - Loading from JSON files
    - Default value support
    - Validation
    - Serialization
    - Type checking
    - Class-level singleton access

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

    Example:
        @dataclass(frozen=True)
        class MyConfig(Configuration):
            name: str
            count: int = 10  # Default value

            @classmethod
            def default(cls) -> "MyConfig":
                return cls(name="default")

    ### Initialization

    The singleton instance is set during application startup by the
    ConfigurationManager. You should not create instances directly,
    but rather use the class-level accessors after initialization.

    Example:
        # During startup
        manager = ConfigurationManager()
        manager._load_configuration(MyConfig)  # Sets up singleton

        # During application use
        value = MyConfig["count"]  # Uses singleton instance

    ### Updating Configurations

    When you need to update a configuration, use the ConfigurationManager to ensure
    the singleton is updated properly:

        manager = get_configuration_manager()
        new_config = MyConfig(name="new", count=20)
        manager.update_configuration(MyConfig, new_config)

    ## JSON Support

    The class also provides JSON serialization support:

    Example:
        # Create from defaults
        config = MyConfig.default()

        # Load from JSON file
        # config.json: {"name": "test", "count": 20}
        config = MyConfig.from_json("config.json")

        # Save to JSON
        config.to_json("new_config.json")
    """

    # Optional class variable for configuration file path
    config_path: ClassVar[Path | None] = None
    # Dictionary to store singleton instances for each Configuration subclass
    _instances: ClassVar[dict[type["Configuration"], "Configuration"]] = {}

    @classmethod
    def __class_getitem__(cls: type[T], key: str) -> Any:
        """Get configuration value by key at class level.

        Uses a cached singleton instance initialized with defaults.
        """
        if cls not in cls._instances:
            cls._instances[cls] = cls.default()
        return getattr(cls._instances[cls], key)

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
    def from_json(cls: type[T], json_path: Path | str) -> T:
        """Load configuration from a JSON file.

        Args:
            json_path: Path to JSON configuration file.

        Returns:
            Configuration instance with values from JSON.

        Raises:
            FileNotFoundError: If JSON file doesn't exist.
            ValueError: If JSON is missing required fields or has invalid values.
            TypeError: If JSON values don't match expected types.
        """
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"Config file not found: {json_path}")

        with json_path.open() as f:
            config_dict = json.load(f)

        # Get all fields defined in the dataclass
        config_fields = {f.name: f for f in fields(cls)}

        # Filter and validate the loaded config against defined fields
        validated_config = {}
        for key, value in config_dict.items():
            if key not in config_fields:
                continue

            field = config_fields[key]
            # TODO: revisit if these casts are always valid...
            field_as_type = cast(type[Any], field.type)
            if not isinstance(value, field_as_type) and value is not None:
                raise TypeError(
                    f"Invalid type for {key}: expected {field_as_type.__name__}, "
                    f"got {type(value).__name__}",
                )
            validated_config[key] = value

        return cls(**validated_config)

    @classmethod
    def from_dict(cls: type[T], config_dict: dict[str, Any]) -> T:  # noqa: C901
        """Load configuration from a dictionary.

        Args:
            config_dict: Dictionary containing configuration values.

        Returns:
            Configuration instance with values from dictionary.

        Raises:
            TypeError: If dictionary values don't match expected types.
        """
        # Get all fields defined in the dataclass
        config_fields = {f.name: f for f in fields(cls)}

        # Filter and validate the loaded config against defined fields
        validated_config = {}
        for key, value in config_dict.items():
            if key not in config_fields:
                continue

            field = config_fields[key]
            # Skip fields that should not be passed to __init__
            if field.init is False:
                continue

            field_type = field.type

            try:
                # Special handling for Path objects - convert strings to Path
                if field_type == Path and isinstance(value, str):
                    validated_config[key] = Path(value)
                    continue

                # Handle Literal types specially by checking field_type signature
                if hasattr(field_type, "__args__") and "Literal" in str(field_type):
                    # For Literal types, just check if the
                    # value is one of the allowed values
                    allowed_values = cast(type[Any], field_type).__args__
                    if value not in allowed_values and value is not None:
                        raise TypeError(
                            f"Invalid value for {key}: got {value}, "
                            f"expected one of {allowed_values}",
                        )
                    validated_config[key] = value
                    continue

                # Skip advanced type checking for other
                # subscripted generics (List[x], Dict[x,y], etc.)
                # as they can't be used with isinstance()
                if hasattr(field_type, "__origin__"):
                    # For subscripted generics, just use the
                    # container type (list, dict, etc)
                    container_type = cast(type[Any], field_type).__origin__
                    if not isinstance(value, container_type) and value is not None:
                        raise TypeError(
                            f"Invalid type for {key}: expected container type "
                            f"{container_type.__name__}, got {type(value).__name__}",
                        )
                    validated_config[key] = value
                    continue

                # Regular type checking
                field_as_type = cast(type[Any], field_type)
                if not isinstance(value, field_as_type) and value is not None:
                    raise TypeError(
                        f"Invalid type for {key}: expected {field_as_type.__name__}, "
                        f"got {type(value).__name__}",
                    )
                validated_config[key] = value
            except Exception as e:
                # Add more context to the error
                raise TypeError(
                    f"Error processing field '{key}' with value {value}: {e!s}",
                ) from e

        return cls(**validated_config)

    @classmethod
    def default(cls: type[T]) -> T:
        """Get default configuration instance.

        Returns:
            Configuration instance with default values.
        """
        return cls()

    def to_json(self, json_path: Path | str | None = None) -> None:
        """Save configuration to a JSON file.

        Args:
            json_path: Path to save JSON file. If None, uses class's config_path.

        Raises:
            ValueError: If no json_path provided and no config_path set.
        """
        if json_path is None:
            if self.config_path is None:
                raise ValueError("No json_path provided and no config_path set")
            json_path = self.config_path

        json_path = Path(json_path)
        with json_path.open("w") as f:
            json.dump(asdict(self), f, indent=2)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration.
        """
        return asdict(self)

    # Tests will fail without this, as you don't guarantee that this
    # class generates an __init__ method and, as such, subclasses may
    # not generate their __init__ method with kwargs correctly... this
    # get's a bit down in the weeds on dataclass machinery, but suffice
    # it to say that we need at least an empty __post_init__ here.
    def __post_init__(self) -> None:
        """Post-initialization hook for validation or other processing."""
        pass


class MapConfiguration(Configuration):
    """A configuration that is made up of only one mapping.

    This class provides helper access methods to allow direct
    subscript access to the underlying mapping.
    """

    # Mark as an abstract base class, not a concrete configuration
    __abstract__ = True

    mapping: ClassVar[dict[str, Any]] = field(
        default_factory=dict,
    )
    """The mapping to access."""

    def __getitem__(self, key: str) -> Any:
        """Get value from the underlying mapping."""
        return self.mapping[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set value in the underlying mapping.

        Note: This will only work if the class is not frozen.
        """
        self.mapping[key] = value

    def __contains__(self, key: str) -> bool:
        """Check if the mapping contains a key."""
        return key in self.mapping

    def __iter__(self) -> Iterator[str]:
        """Iterate over the mapping keys."""
        return iter(self.mapping)

    def __len__(self) -> int:
        """Get the length of the mapping."""
        return len(self.mapping)

    def items(self) -> list[tuple[str, Any]]:
        """Get the items of the mapping."""
        return list(self.mapping.items())

    def keys(self) -> list[str]:
        """Get the keys of the mapping."""
        return list(self.mapping.keys())

    def values(self) -> list[Any]:
        """Get the values of the mapping."""
        return list(self.mapping.values())

    @classmethod
    def __class_getitem__(cls: type[T], key: str) -> Any:
        """Get configuration value by key at class level.

        Uses a cached singleton instance initialized with defaults.
        """
        _map = super().__class_getitem__("mapping")
        return _map[key]

    @classmethod
    def class_items(cls: type[T]) -> Iterator[tuple[str, Any]]:
        """Get the items of the mapping at class level.

        Uses a cached singleton instance initialized with defaults.
        """
        _map = super().__class_getitem__("mapping")
        return _map.items()

    @classmethod
    def class_keys(cls: type[T]) -> Iterator[str]:
        """Get the keys of the mapping at class level.

        Uses a cached singleton instance initialized with defaults.
        """
        _map = super().__class_getitem__("mapping")
        return _map.keys()

    @classmethod
    def class_values(cls: type[T]) -> Iterator[Any]:
        """Get the values of the mapping at class level.

        Uses a cached singleton instance initialized with defaults.
        """
        _map = super().__class_getitem__("mapping")
        return _map.values()

    @classmethod
    def __class_iter__(cls: type[T]) -> Iterator[tuple[str, Any]]:
        """Iterate over the mapping."""
        _map = super().__class_getitem__("mapping")
        return _map.items()

    @classmethod
    def __class_contains__(cls: type[T], key: str) -> bool:
        """Check if the mapping contains a key."""
        _map = super().__class_getitem__("mapping")
        return key in _map

    @classmethod
    def __class_len__(cls: type[T]) -> int:
        """Get the length of the mapping."""
        _map = super().__class_getitem__("mapping")
        return len(_map)
