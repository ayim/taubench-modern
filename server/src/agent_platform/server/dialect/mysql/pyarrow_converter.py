"""MySQL PyArrow converter implementation."""

from __future__ import annotations

from agent_platform.server.dialect.pyarrow_converter_base import PyArrowConverter


class MySQLPyArrowConverter(PyArrowConverter):
    """PyArrow converter for MySQL databases.

    Currently uses default behavior (no MySQL-specific transformations).
    Override transform_schema() if MySQL-specific handling is needed in the future.
    """

    pass
