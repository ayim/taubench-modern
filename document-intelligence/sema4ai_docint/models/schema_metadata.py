"""Schema metadata models for internal tracking."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SchemaWithMetadata(BaseModel):
    """Schema with internal metadata for tracking.

    This model is used internally to store schemas along with metadata
    like the user prompt that was used to generate them.
    """

    extract_schema: dict[str, Any]
    user_prompt: str | None = None
