"""Snowflake PyArrow converter implementation."""

from __future__ import annotations

from agent_platform.server.dialect.pyarrow_converter_base import PyArrowConverter


class SnowflakePyArrowConverter(PyArrowConverter):
    """PyArrow converter for Snowflake databases.

    Currently uses default behavior (no Snowflake-specific transformations).
    Override transform_schema() if Snowflake-specific handling is needed in the future.
    """

    pass
