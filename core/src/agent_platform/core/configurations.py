"""Configuration classes support default values and loading from JSON."""

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, TypeVar

T = TypeVar("T", bound="Configuration")


@dataclass(frozen=True)
class Configuration:
    """Base class for all configurations.

    This class provides common functionality for JSON-based configurations including:
    - Loading from JSON files
    - Default value support
    - Validation
    - Serialization
    - Type checking
    - Class-level singleton access

    Example:
        @dataclass(frozen=True)
        class MyConfig(Configuration):
            name: str
            count: int = 10  # Default value

            @classmethod
            def default(cls) -> "MyConfig":
                return cls(name="default")

        # Create from defaults
        config = MyConfig.default()

        # Load from JSON file
        # config.json: {"name": "test", "count": 20}
        config = MyConfig.from_json("config.json")

        # Save to JSON
        config.to_json("new_config.json")

        # Use as a dictionary (instance level)
        config["count"]  # 20

        # Use as a dictionary (class level, uses cached singleton)
        MyConfig["count"]  # 10 (default)
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
            if not isinstance(value, field.type) and value is not None:
                raise TypeError(
                    f"Invalid type for {key}: expected {field.type.__name__}, "
                    f"got {type(value).__name__}",
                )
            validated_config[key] = value

        return cls(**validated_config)

    @classmethod
    def from_dict(cls: type[T], config_dict: dict[str, Any]) -> T:
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
            if not isinstance(value, field.type) and value is not None:
                raise TypeError(
                    f"Invalid type for {key}: expected {field.type.__name__}, "
                    f"got {type(value).__name__}",
                )
            validated_config[key] = value

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


class MapConfiguration(Configuration):
    """A configuration that is made up of only one mapping.

    This class provides helper access methods to allow direct
    subscript access to the underlying mapping.
    """

    mapping: dict[str, Any] = field(
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

    def items(self) -> Iterator[tuple[str, Any]]:
        """Get the items of the mapping."""
        return self.mapping.items()

    def keys(self) -> Iterator[str]:
        """Get the keys of the mapping."""
        return self.mapping.keys()

    def values(self) -> Iterator[Any]:
        """Get the values of the mapping."""
        return self.mapping.values()

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
