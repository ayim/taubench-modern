"""PyArrow conversion base interface.

This module provides the base interface for database-specific converters to handle
dialect-specific transformations when converting Ibis tables to PyArrow format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

if TYPE_CHECKING:
    from ibis.expr.schema import Schema as IbisSchema

    from agent_platform.server.kernel.ibis import AsyncIbisTable

logger = get_logger(__name__)


class PyArrowConverter:
    """Base class for dialect-specific PyArrow conversion logic.

    Subclasses can override transform_schema to apply database-specific
    transformations before converting to PyArrow format. This is useful for
    handling dialect-specific quirks that would otherwise cause errors or
    data loss during conversion.

    Example use cases:
    - Postgres NUMERIC (DECIMAL) columns containing NaN values
    - MySQL-specific data type conversions
    - Snowflake-specific type handling
    """

    async def transform_schema(self, table: AsyncIbisTable, schema: IbisSchema) -> AsyncIbisTable:
        """Apply dialect-specific transformations before PyArrow conversion.

        This method is called before converting an Ibis table to PyArrow format.
        The default implementation returns the table unchanged. Subclasses should
        override this method to apply database-specific transformations.

        Args:
            table: The Ibis table to transform
            schema: The table's schema (already fetched for convenience)

        Returns:
            Transformed table (or original if no transformations needed)
        """
        return table
