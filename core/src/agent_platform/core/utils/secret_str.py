from dataclasses import dataclass, field
from typing import Any


@dataclass
class SecretString:
    """Representation of a secret string, to be used in dataclasses.

    This implementation is good for preventing accidental secret disclosure via
    logs or printouts. That alone is a big win. Nevertheless in Python, true
    memory security is basically not guaranteed. (And, we'll likely be unwrapping
    this in many places, so we'll need to be careful.)"""

    value: str = field(metadata={"description": "The secret string value."})
    """The secret string value."""

    def __post_init__(self):
        """Validate the value after initialization."""
        if self.value is None:
            raise ValueError("SecretString value cannot be None")
        if not isinstance(self.value, str):
            raise TypeError(
                f"SecretString value must be str, not {type(self.value).__name__}",
            )

    def get_secret_value(self) -> str:
        """Gets the secret value from the SecretString."""
        return self.value

    def __len__(self) -> int:
        """Gets the length of the secret string."""
        return len(self.value)

    def __str__(self) -> str:
        """Gets a representation of the secret string."""
        return "**********"

    def __repr__(self) -> str:
        """Gets a representation of the secret string."""
        return "SecretString('**********')"

    def __eq__(self, other: Any) -> bool:
        """Compare this SecretString with another value."""
        if isinstance(other, SecretString):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __bool__(self) -> bool:
        """Return True if the secret string has a value, False otherwise."""
        return bool(self.value)

    @classmethod
    def from_value(cls, value: str | dict) -> "SecretString":
        """Create a SecretString from a string or dict. This is necessary because dataclasses that
        contain SecretString, such as PlatformParameters, don't automatically convert dicts to
        SecretString when deserializing from API JSON request bodies.

        Arguments:
            value: A string or dict with a "value" key.

        Returns:
            A SecretString instance.
        """
        if isinstance(value, dict) and "value" in value:
            return cls(value["value"])
        return cls(str(value))

    @classmethod
    def serialize(cls, value: Any, raw: bool = False) -> str:
        """Serialize a value to a string, handling SecretString objects.

        Arguments:
            value: The value to serialize.
            raw: Whether to return the raw value or the masked value.

        Returns:
            The serialized value.
        """
        if isinstance(value, SecretString):
            return value.get_secret_value() if raw else str(value)
        return value
