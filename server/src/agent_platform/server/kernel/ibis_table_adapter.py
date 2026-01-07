"""High-level adapter for Ibis table transformations.

This module provides a wrapper around AsyncIbisTable that handles
dialect-specific transformations and edge cases when converting to PyArrow.

The adapter uses the dialect factory pattern to apply database-specific
transformations based on the table's engine/dialect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow

    from agent_platform.server.kernel.ibis_async_proxy import AsyncIbisTable


class IbisTableAdapter:
    """
    High-level adapter for Ibis table transformations.

    The adapter handles dialect-specific conversions and edge cases by
    delegating to database-specific PyArrowConverter implementations.

    Example:
        >>> adapter = IbisTableAdapter(async_ibis_table)
        >>> pyarrow_table = await adapter.to_pyarrow()
    """

    def __init__(self, table: AsyncIbisTable) -> None:
        """Initialize adapter with an Ibis table proxy.

        Args:
            table: The Ibis table wrapped in async proxy
        """
        self._table = table

    async def to_pyarrow(self) -> pyarrow.Table:
        """
        Convert to PyArrow with dialect-specific transformations.

        This method uses the PyArrowConverterFactory to get a dialect-specific
        converter that handles database-specific edge cases:

        - Postgres: DECIMAL columns → float64 (for NaN handling)
        - MySQL: (currently no special handling)
        - Snowflake: (currently no special handling)
        - etc.

        The conversion logic is extensible per-dialect. See dialect/postgres/
        pyarrow_converter.py for an example of dialect-specific handling.

        Returns:
            PyArrow table ready for JSON/dict conversion
        """
        from agent_platform.server.dialect import PyArrowConverterFactory

        # Get dialect-specific converter based on table's engine
        converter = PyArrowConverterFactory.create(self._table._engine)

        # Fetch schema for converter to inspect
        schema = await self._table.schema()

        # Apply dialect-specific transformations
        transformed_table = await converter.transform_schema(self._table, schema)

        # Convert to PyArrow
        return await transformed_table.to_pyarrow_unsafe()
