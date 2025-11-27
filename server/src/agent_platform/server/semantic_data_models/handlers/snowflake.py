"""Snowflake backend handler for semantic data models."""

import asyncio
import typing
from typing import Any

import structlog

from agent_platform.server.semantic_data_models.handlers.base import BackendHandler

if typing.TYPE_CHECKING:
    import pyarrow

logger = structlog.get_logger(__name__)


class SnowflakeBackendHandler(BackendHandler):
    """Handler for Snowflake database backend.

    Snowflake requires special handling because:
    - VARIANT, OBJECT, and ARRAY types are not compatible with Arrow format
    - We need to use raw cursor to fetch results as Python objects
    - Then manually convert to pandas DataFrame and finally to Arrow
    """

    async def execute_query(self, ibis_expr: Any) -> "pyarrow.Table":
        """Execute query using raw cursor to avoid Arrow format issues.

        This function bypasses ibis's Arrow conversion which is not compatible with
        Snowflake's VARIANT, OBJECT, and ARRAY types. Instead, it:
        1. Compiles the ibis expression to SQL
        2. Executes it using Snowflake's raw cursor (in a thread pool)
        3. Fetches results as plain Python objects
        4. Manually constructs a pandas DataFrame
        5. Converts to Arrow table
        """
        # Get the backend and compile to SQL (these are fast, non-blocking operations)
        backend = ibis_expr._find_backend()
        sql_query = backend.compile(ibis_expr)

        # Define a function to execute the blocking cursor operations
        def _execute_cursor():
            cursor = backend.con.cursor()
            try:
                cursor.execute(str(sql_query))
                # Use fetchall() to get raw data, avoiding Arrow conversion
                rows = cursor.fetchall()
                column_names: list[str] = [desc[0] for desc in cursor.description]  # type: ignore[misc]

                # Manually create pandas DataFrame from raw data
                import pandas
                import pyarrow

                df = pandas.DataFrame(rows, columns=column_names)  # type: ignore[arg-type]

                # Convert to Arrow table
                return pyarrow.Table.from_pandas(df)
            finally:
                cursor.close()

        # Execute all the blocking cursor operations in a thread pool
        return await asyncio.to_thread(_execute_cursor)

    @property
    def backend_name(self) -> str:
        return "snowflake"
