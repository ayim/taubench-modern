"""DuckDB-specific PyArrow conversion logic."""

from __future__ import annotations

from agent_platform.server.dialect.pyarrow_converter_base import PyArrowConverter


class DuckDBPyArrowConverter(PyArrowConverter):
    """PyArrow converter for DuckDB.

    Currently uses default behavior (no DuckDB-specific transformations).
    Override transform_schema() if DuckDB-specific handling is needed in the future.
    """

    pass
