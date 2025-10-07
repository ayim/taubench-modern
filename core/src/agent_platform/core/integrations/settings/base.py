"""Base integration settings class."""

from dataclasses import dataclass
from typing import Any

from agent_platform.core.utils.dataclass_meta import TolerantDataclass


@dataclass(frozen=True)
class IntegrationSettings(TolerantDataclass):
    """Base class for integration settings."""

    def model_dump(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        raise NotImplementedError("Subclasses must implement model_dump")

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "IntegrationSettings":
        """Create settings from dictionary."""
        raise NotImplementedError("Subclasses must implement model_validate")

    def model_dump_json(self) -> str:
        """Convert settings to JSON string."""
        import json

        return json.dumps(self.model_dump())

    @classmethod
    def model_validate_json(cls, json_str: str) -> "IntegrationSettings":
        """Create settings from JSON string."""
        import json

        return cls.model_validate(json.loads(json_str))
