from dataclasses import dataclass, field
from typing import Self

from agent_platform_core.actions.action_utils import (
    _get_spec_and_build_tool_definitions,
)
from agent_platform_core.tools.tool_definition import ToolDefinition
from agent_platform_core.utils import SecretString


@dataclass(frozen=True)
class ActionPackage:
    """Action package definition."""

    name: str = field(
        metadata={
            "description": "The name of the action package.",
        },
    )
    """The name of the action package."""

    organization: str = field(
        metadata={
            "description": "The organization of the action package.",
        },
    )
    """The organization of the action package."""

    version: str = field(
        metadata={
            "description": "The version of the action package.",
        },
    )
    """The version of the action package."""

    url: str | None = field(
        metadata={
            "description": "URL of the action server that hosts the action package.",
        },
        default=None,
    )
    """URL of the action server that hosts the action package."""

    api_key: SecretString | None = field(
        metadata={
            "description": "API Key of the action server that"
                " hosts the action package.",
        },
        default=None,
    )
    """API Key of the action server that hosts the action package."""

    allowed_actions: list[str] = field(
        metadata={
            "description": "Actions to enable in the action server that"
                " hosts the action package. An empty list"
                " implies all actions are enabled.",
        },
        default_factory=list,
    )
    """Actions to enable in the action server that hosts the action package.
    An empty list implies all actions are enabled."""

    def __post_init__(self):
        """Post-initialization hook."""
        if self.api_key is not None and isinstance(self.api_key, str):
            # Need to be careful setting in a frozen dataclass
            object.__setattr__(self, "api_key", SecretString(self.api_key))

    def copy(self) -> Self:
        """Returns a deep copy of the action package."""
        return ActionPackage(
            name=self.name,
            organization=self.organization,
            version=self.version,
            url=self.url,
            api_key=(
                SecretString(self.api_key.get_secret_value())
                if self.api_key is not None
                else None
            ),
            allowed_actions=self.allowed_actions,
        )

    def model_dump(self) -> dict:
        """Serializes the action package to a dictionary.
        Useful for JSON serialization."""
        return {
            "name": self.name,
            "organization": self.organization,
            "version": self.version,
            "url": self.url,
            "api_key": (
                self.api_key.get_secret_value() if self.api_key is not None else None
            ),
            "allowed_actions": self.allowed_actions,
        }

    async def to_tool_definitions(self) -> list[ToolDefinition]:
        """Converts the action package to a list of tool definitions."""
        return await _get_spec_and_build_tool_definitions(
            self.url,
            self.api_key.get_secret_value(),
            self.allowed_actions,
        )

    @classmethod
    def model_validate(cls, data: dict) -> "ActionPackage":
        """Deserializes the action package from a dictionary.
        Useful for JSON deserialization."""
        return cls(**data)
