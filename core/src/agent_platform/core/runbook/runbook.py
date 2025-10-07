from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from agent_platform.core.runbook.content import (
    AnyRunbookContent,
    RunbookContent,
)


@dataclass
class Runbook:
    """This class represents a runbook, which is textual
    specification of how an agent should operate."""

    raw_text: str = field(
        metadata={
            "description": "The raw text of the runbook",
        },
    )
    """The raw text of the runbook"""

    # There is some dynamic validation here, we can only have up to
    # ONE steps content; any number of text content components are
    # allowed. By default, we'll make this an empty list.
    content: list[AnyRunbookContent] = field(
        metadata={
            "description": "The content of the runbook",
        },
    )
    """The content of the runbook"""

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={
            "description": "Timestamp of the last update to the runbook",
        },
    )
    """Timestamp of the last update to the runbook"""

    def copy(self) -> "Runbook":
        """Returns a deep copy of the runbook."""
        return Runbook(
            raw_text=self.raw_text,
            content=[content.copy() for content in self.content],
            updated_at=self.updated_at,
        )

    def model_dump(self) -> dict:
        """Serializes the runbook to a dictionary. Useful for JSON serialization."""
        return {
            "raw_text": self.raw_text,
            "content": [content.model_dump() for content in self.content],
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def model_validate(
        cls,
        data: dict,
        fallback_updated_at: datetime,
    ) -> "Runbook":
        """Create a runbook from a dictionary.

        Args:
            data: Raw runbook payload to validate.
            fallback_updated_at: Timestamp to use when the payload omits or
                provides an invalid ``updated_at``.

        Returns:
            Runbook: A runbook with all timestamp fields normalised to UTC.
        """
        data = data.copy()

        raw_updated_at = data.pop("updated_at", None)
        parsed_updated_at = cls._normalise_updated_at(raw_updated_at)
        updated_at = parsed_updated_at or fallback_updated_at

        content = cast(
            list[AnyRunbookContent],
            [RunbookContent.model_validate(content) for content in data.pop("content", [])],
        )
        return cls(**data, content=content, updated_at=updated_at)

    @staticmethod
    def _normalise_updated_at(value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return None
