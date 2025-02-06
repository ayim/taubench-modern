from dataclasses import dataclass, field
from datetime import datetime
from re import match as re_match
from uuid import UUID


@dataclass(frozen=True)
class User:
    _parsed_sub: dict[str, str] | None = field(default=None, init=False, repr=False)
    """The parsed sub of the user."""
    user_id: str = field(metadata={"description": "The user's unique identifier."})
    """The user's unique identifier."""
    sub: str = field(metadata={"description": "The user's sub (from a JWT token)."})
    """The user's sub (from a JWT token)."""
    created_at: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "The date and time the user was created."},
    )
    """The date and time the user was created."""

    def __post_init__(self):
        """Parse the sub of the user."""
        # Dataclass is frozen, so we need to use special syntax to set the _parsed_sub field
        object.__setattr__(self, "_parsed_sub", self._parse_sub(self.sub))

    def _parse_sub(self, sub: str) -> dict[str, str] | None:
        """Parse the sub of the user."""
        pattern = r"^tenant:([^:]+)(?::(?P<type>user|system):(?P<id>[^:]+))?$"
        match = re_match(pattern, sub)

        if not match:
            return {"tenant": None, "user": None, "system": None}

        result = {"tenant": match.group(1), "user": None, "system": None}
        if match.group("type"):
            result[match.group("type")] = match.group("id")

        return result

    @property
    def cr_tenant_id(self) -> str | None:
        """Control Room Tenant ID"""
        return self._parsed_sub["tenant"]

    @property
    def cr_user_id(self) -> str | None:
        """Control Room User ID"""
        return self._parsed_sub["user"]

    @property
    def cr_system_id(self) -> str | None:
        """Control Room System ID"""
        return self._parsed_sub["system"]

    def to_json_dict(self) -> dict:
        """Convert the user to a dictionary."""
        return {
            "user_id": self.user_id,
            "sub": self.sub,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Create a User from a dictionary."""
        data = data.copy()
        if "user_id" in data and isinstance(data["user_id"], UUID):
            data["user_id"] = str(data["user_id"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)
