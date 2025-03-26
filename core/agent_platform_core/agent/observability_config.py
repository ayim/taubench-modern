from dataclasses import dataclass, field
from typing import Any, Literal, Self

from agent_server_types_v2.utils import assert_literal_value_valid


@dataclass(frozen=True)
class ObservabilityConfig:
    """Observability config for the agent."""

    type: Literal["langsmith"] = field(
        metadata={"description": "The type of observability config."},
    )
    """The type of observability config."""

    api_key: str | None = field(
        metadata={"description": "The API to use with this observability config."},
        default=None,
    )
    """The API to use with this observability config."""

    api_url: str | None = field(
        metadata={"description": "The API URL to use with this observability config."},
        default=None,
    )
    """The API URL to use with this observability config."""

    settings: dict[str, Any] = field(
        metadata={"description": "The settings for this observability config."},
        default_factory=dict,
    )
    """The settings for this observability config."""

    def __post_init__(self) -> None:
        """Post-initialization checks.

        For LangSmith, we require the API key and URL.

        Raises:
            ValueError: If the type is not valid.
        """
        assert_literal_value_valid(self, "type")

        if self.type == "langsmith":
            if self.api_key is None or self.api_url is None:
                raise ValueError("Langsmith API key and URL are required.")

    def copy(self) -> Self:
        """Returns a deep copy of the observability config."""
        from copy import deepcopy

        return ObservabilityConfig(
            type=self.type,
            api_key=self.api_key,
            api_url=self.api_url,
            settings=deepcopy(self.settings) if self.settings != {} else {},
        )

    def model_dump(self) -> dict:
        """Serializes the observability config to a dictionary.
        Useful for JSON serialization."""
        return {
            "type": self.type,
            "api_key": self.api_key,
            "api_url": self.api_url,
            "settings": self.settings,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ObservabilityConfig":
        """Create an observability config from a dictionary."""
        return cls(**data)
