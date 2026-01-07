"""Databricks PyArrow converter implementation."""

from __future__ import annotations

from agent_platform.server.dialect.pyarrow_converter_base import PyArrowConverter


class DatabricksPyArrowConverter(PyArrowConverter):
    """PyArrow converter for Databricks databases.

    Currently uses default behavior (no Databricks-specific transformations).
    Override transform_schema() if Databricks-specific handling is needed in the future.
    """

    pass
