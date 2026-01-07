"""PostgreSQL PyArrow converter implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

from agent_platform.server.dialect.pyarrow_converter_base import PyArrowConverter

if TYPE_CHECKING:
    from ibis.expr.schema import Schema as IbisSchema

    from agent_platform.server.kernel.ibis_async_proxy import AsyncIbisTable

logger = get_logger(__name__)


class PostgresPyArrowConverter(PyArrowConverter):
    """PyArrow converter for PostgreSQL databases.

    Handles PostgreSQL-specific transformations when converting to PyArrow:
    - DECIMAL/NUMERIC columns containing NaN values are converted to float64
      to avoid PyArrow errors (PyArrow's Decimal type doesn't support NaN)
    """

    async def transform_schema(self, table: AsyncIbisTable, schema: IbisSchema) -> AsyncIbisTable:
        """Apply PostgreSQL-specific transformations for PyArrow conversion.

        PostgreSQL's NUMERIC type (mapped to Ibis DECIMAL) can contain the
        special value NaN. PyArrow's Decimal128 type does not support NaN values,
        which causes conversion errors. We solve this by casting DECIMAL columns
        to float64, which properly supports NaN.

        Args:
            table: The Ibis table to transform
            schema: The table's schema

        Returns:
            Transformed table with DECIMAL → float64 conversions applied
        """
        import ibis.expr.datatypes as dt

        # Build list of column expressions, converting DECIMAL to float64
        select_cols = []
        has_decimal = False

        for col_name, col_type in schema.items():
            if isinstance(col_type, dt.Decimal):
                # Postgres NUMERIC can have NaN, convert to float64 for proper handling
                select_cols.append(table[col_name].cast("float64").name(col_name))
                has_decimal = True
            else:
                select_cols.append(table[col_name])

        # If we found decimal columns, apply transformation
        if has_decimal:
            raw_expressions = [col._column for col in select_cols]
            return table.select(raw_expressions)

        return table
