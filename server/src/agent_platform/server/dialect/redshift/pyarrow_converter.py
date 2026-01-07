"""Redshift PyArrow converter implementation."""

from __future__ import annotations

from agent_platform.server.dialect.pyarrow_converter_base import PyArrowConverter


class RedshiftPyArrowConverter(PyArrowConverter):
    """PyArrow converter for Redshift databases.

    Currently uses default behavior (no Redshift-specific transformations).
    Override transform_schema() if Redshift-specific handling is needed in the future.
    """

    pass
