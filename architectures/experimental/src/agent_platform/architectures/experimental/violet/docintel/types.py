from dataclasses import dataclass, field
from typing import Any, Literal

from reducto.types.shared import ParseResponse


@dataclass(slots=True)
class DocSampledPage:
    """Metadata for a sampled page within a document card."""

    page: int
    status: Literal["pending", "parsing", "parsed", "error"] = "pending"
    summary: str | None = None
    parse_data: "ParseResponse | None" = None


@dataclass(slots=True)
class DocComment:
    """A comment on a document card."""

    comment: str
    updated_at: str | None = None
    anchor: dict[str, Any] | None = None


@dataclass(slots=True)
class DocCard:
    """Represents a single document that needs user markup."""

    file_ref: str
    file_id: str
    mime_type: str
    size_bytes: int | None = None
    status: Literal["pending_markup", "in_progress", "done", "error"] = "pending_markup"
    sampled_pages: list[DocSampledPage] = field(default_factory=list)
    comments: list[DocComment] = field(default_factory=list)
    json_schema: dict[str, Any] | None = None
    error: str | None = None
    updated_at: str | None = None
    revision: int = 0


@dataclass(slots=True)
class DocIntState:
    """Top-level state for document intelligence UI/markup."""

    revision: int = 0
    cards: list[DocCard] = field(default_factory=list)
    prompt_payload: str = ""
