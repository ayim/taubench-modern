from dataclasses import dataclass, field
from typing import Self


@dataclass(frozen=True)
class AgentArchitecture:
    """Agent architecture definition."""

    name: str = field(metadata={"description": "The name of the agent architecture."})
    """The name of the agent architecture."""

    version: str = field(metadata={"description": "The version of the agent architecture."})
    """The version of the agent architecture."""

    def copy(self) -> Self:
        """Returns a deep copy of the agent architecture."""
        return AgentArchitecture(
            name=self.name,
            version=self.version,
        )

    def to_json_dict(self) -> dict:
        """Serializes the cognitive architecture to a dictionary. Useful for JSON serialization."""
        return {
            "name": self.name,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentArchitecture":
        """Create a agent architecture from a dictionary."""
        return cls(**data)
