from dataclasses import dataclass, field

from agent_platform.core.utils import SecretString


@dataclass(frozen=True)
class ActionServerConfigPayload:
    url: str = field(
        metadata={
            "description": ("The URL of the action server."),
        },
    )
    """The URL of the action server."""

    api_key: str | SecretString = field(
        metadata={
            "description": ("The API key of the action server."),
        },
    )
    """The API key of the action server."""
