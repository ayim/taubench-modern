"""Utility functions for Snowflake-specific operations."""

import asyncio
from typing import TYPE_CHECKING, Any

from structlog import get_logger

if TYPE_CHECKING:
    import pyarrow

logger = get_logger(__name__)


def is_snowflake_backend(ibis_expr: Any) -> bool:
    """
    Check if an ibis expression is backed by a Snowflake connection.

    Args:
        ibis_expr: An ibis expression or result object

    Returns:
        True if the backend is Snowflake, False otherwise
    """
    try:
        if hasattr(ibis_expr, "_find_backend"):
            backend = ibis_expr._find_backend()
            return hasattr(backend, "name") and backend.name == "snowflake"
        elif hasattr(ibis_expr, "get_backend"):
            backend = ibis_expr.get_backend()
            return hasattr(backend, "name") and backend.name == "snowflake"
        elif hasattr(ibis_expr, "name"):
            # Direct backend object
            return ibis_expr.name == "snowflake"
        return False
    except Exception as e:
        logger.error(
            "Error checking if backend is Snowflake",
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


async def execute_snowflake_query_raw(ibis_expr: Any) -> "pyarrow.Table":
    """
    Execute an ibis expression against Snowflake using raw cursor to avoid Arrow format issues.

    This function bypasses ibis's Arrow conversion which is not compatible with
    Snowflake's VARIANT, OBJECT, and ARRAY types. Instead, it:
    1. Compiles the ibis expression to SQL
    2. Executes it using Snowflake's raw cursor (in a thread pool)
    3. Fetches results as plain Python objects
    4. Manually constructs a pandas DataFrame
    5. Converts to Arrow table

    Args:
        ibis_expr: An ibis expression to execute (must be backed by Snowflake)

    Returns:
        A pyarrow.Table containing the query results

    Raises:
        ValueError: If the expression is not backed by Snowflake
        Exception: If query execution fails
    """
    if not is_snowflake_backend(ibis_expr):
        raise ValueError("This function only works with Snowflake-backed ibis expressions")

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
