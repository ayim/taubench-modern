import json
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from typing import Any

from agent_platform.core.thread.content.base import ThreadMessageContent


@dataclass
class ThreadThoughtContent(ThreadMessageContent):
    """Represents a thought content item in a thread message.

    This class handles thought content, ensuring that the thought is non-empty
    and properly typed.
    """

    thought: str = field(
        metadata={"description": "The actual text content of the thought"},
    )
    """The actual text content of the thought"""

    extras: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Extra information about related to the thought"},
    )
    """Extra information about related to the thought"""

    kind: str = field(
        default="thought",
        metadata={"description": "Content kind: always 'thought'"},
        init=False,
    )
    """Content kind: always 'thought'"""

    def __post_init__(self) -> None:
        """Validates the content type and text content after initialization.

        Raises:
            AssertionError: If the type field doesn't match the literal "thought".
        """
        assert self.kind == "thought"

        # We used to check for empty thoughts, but there's a few valid use
        # cases for empty thoughts... like when we're streaming and we just
        # started and know thoughts are coming, but we don't have any yet

        # Record start time for duration tracking (only if not already set from deserialization)
        if isinstance(self.extras, dict) and "started_at" not in self.extras:
            self.extras["started_at"] = datetime.now(UTC).isoformat()

    def mark_complete(self) -> None:
        """Used to indicate that the content has finished streaming.

        Also calculates and stores the thinking duration in extras.
        """
        # Calculate duration BEFORE setting complete so both are available in same stream update
        started_at_str = self.extras.get("started_at")
        if started_at_str and "duration_seconds" not in self.extras:
            try:
                started_at = datetime.fromisoformat(started_at_str)
                duration = (datetime.now(UTC) - started_at).total_seconds()
                self.extras["duration_seconds"] = round(duration)
            except (ValueError, TypeError):
                pass  # Invalid timestamp, skip duration calculation

        self.complete = True

    def as_text_content(self) -> str:
        """Converts the text content to a text content component."""
        return self.thought

    def model_dump(self) -> dict:
        """Serializes the thought content to a dictionary.
        Useful for JSON serialization."""
        return {
            **super().model_dump(),
            "thought": self.thought,
            "extras": self.extras,
        }

    def model_dump_json(self) -> str:
        """Serializes the thought content to a JSON string."""
        return json.dumps(self.model_dump())

    @classmethod
    def model_validate(cls, data: dict) -> "ThreadThoughtContent":
        """Create a thread thought content from a dictionary."""
        allowed = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in allowed}
        return cls(**data)


ThreadMessageContent.register_content_kind("thought", ThreadThoughtContent)
