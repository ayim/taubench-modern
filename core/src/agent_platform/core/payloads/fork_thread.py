from dataclasses import dataclass, field


@dataclass
class ForkThreadPayload:
    """Payload for forking a thread at a specific message."""

    message_id: str = field(
        metadata={"description": "The ID of the message to fork from."},
    )
    """The ID of the message to fork from."""

    name: str | None = field(
        default=None,
        metadata={"description": "Optional custom name for the forked thread"},
    )
    """Optional custom name for the forked thread."""
