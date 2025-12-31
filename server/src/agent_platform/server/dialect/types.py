"""Shared types for dialect implementations."""

from __future__ import annotations

from typing import TypedDict


class ConstraintData(TypedDict):
    """Intermediate data structure for grouping foreign key constraint information."""

    source_table: str
    target_table: str
    source_columns: list[str]
    target_columns: list[str]
    on_delete: str | None
    on_update: str | None
