"""SQLite PyArrow converter implementation."""

from __future__ import annotations

from agent_platform.server.dialect.pyarrow_converter_base import PyArrowConverter


class SQLitePyArrowConverter(PyArrowConverter):
    """PyArrow converter for SQLite databases.

    Currently uses default behavior (no SQLite-specific transformations).
    Override transform_schema() if SQLite-specific handling is needed in the future.
    """

    pass
