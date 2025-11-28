"""MySQL backend handler for semantic data models."""

import asyncio
import typing
from typing import Any

import structlog

from agent_platform.server.semantic_data_models.handlers.base import BackendHandler

if typing.TYPE_CHECKING:
    import pyarrow

logger = structlog.get_logger(__name__)


class MySQLBackendHandler(BackendHandler):
    """Handler for MySQL database backend.

    MySQL requires special handling because:
    - JSON columns are automatically deserialized into Python objects (dict/list/bool)
    - Arrow conversion fails with these deserialized objects
    - We need to use raw cursor and pandas to handle JSON serialization
    """

    async def execute_query(self, ibis_expr: Any) -> "pyarrow.Table":
        """Execute query with proper JSON handling for MySQL.

        This function bypasses ibis's default Arrow conversion which automatically
        deserializes MySQL JSON columns into Python objects that Arrow cannot convert.
        Instead, it:
        1. Compiles the ibis expression to SQL
        2. Executes it using MySQL's raw cursor
        3. Fetches results as plain Python objects (JSON stays as Python objects)
        4. Manually constructs a pandas DataFrame (which handles JSON serialization)
        5. Converts to Arrow table
        """

        def _execute_query():
            # Get the backend and compile to SQL
            backend = ibis_expr._find_backend()
            sql_query = backend.compile(ibis_expr)

            # Execute with raw cursor
            cursor = backend.con.cursor()
            try:
                cursor.execute(str(sql_query))
                # Use fetchall() to get raw data
                # For MySQL, JSON columns will be deserialized Python objects
                rows = cursor.fetchall()
                column_names: list[str] = [
                    desc[0]
                    for desc in cursor.description  # type: ignore[misc]
                ]

                # Manually create pandas DataFrame from raw data
                # pandas will handle JSON serialization automatically
                import pandas
                import pyarrow

                df = pandas.DataFrame(
                    rows,
                    columns=column_names,  # type: ignore[arg-type]
                )

                # Convert to Arrow table
                # pandas converts complex objects (dict/list) to strings during Arrow conversion
                return pyarrow.Table.from_pandas(df)
            finally:
                cursor.close()

        return await asyncio.to_thread(_execute_query)

    @property
    def backend_name(self) -> str:
        return "mysql"
