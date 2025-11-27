"""Redshift backend handler for semantic data models."""

import asyncio
import typing
from typing import Any

import structlog

from agent_platform.server.semantic_data_models.handlers.base import BackendHandler

if typing.TYPE_CHECKING:
    import pyarrow

logger = structlog.get_logger(__name__)


class RedshiftBackendHandler(BackendHandler):
    """Handler for Redshift database backend.

    Redshift requires special handling because:
    - Single-node clusters have a maximum fetch size of 1000
    - Multi-node clusters support larger fetch sizes
    - We need to use raw cursor with appropriate arraysize
    """

    async def execute_query(self, ibis_expr: Any) -> "pyarrow.Table":
        """Execute query with proper fetch size for Redshift.

        Redshift single-node configurations have a maximum fetch size of 1000.
        Multi-node clusters support larger fetch sizes.
        This function bypasses ibis's default Arrow conversion which uses a
        fetch size of 1,000,000. Instead, it:
        1. Compiles the ibis expression to SQL
        2. Uses cached arraysize (determined during connection setup)
        3. Executes query using a cursor with optimal fetch size
        4. Fetches results as plain Python objects
        5. Manually constructs a pandas DataFrame
        6. Converts to Arrow table
        """

        def _execute_query():
            # Get the backend and compile to SQL
            backend = ibis_expr._find_backend()
            sql_query = backend.compile(ibis_expr)

            # Execute with cursor that has appropriate arraysize
            cursor = backend.con.cursor()
            try:
                # Get cached optimal arraysize for this cluster
                arraysize = self._get_redshift_arraysize(backend)
                cursor.arraysize = arraysize

                cursor.execute(str(sql_query))
                # Use fetchall() to get raw data with controlled fetch size
                rows = cursor.fetchall()
                column_names: list[str] = [
                    desc[0]
                    for desc in cursor.description  # type: ignore[misc]
                ]

                # Manually create pandas DataFrame from raw data
                import pandas
                import pyarrow

                df = pandas.DataFrame(
                    rows,
                    columns=column_names,  # type: ignore[arg-type]
                )

                # Convert to Arrow table
                return pyarrow.Table.from_pandas(df)
            finally:
                cursor.close()

        return await asyncio.to_thread(_execute_query)

    def _get_redshift_arraysize(self, backend: Any) -> int:
        """Get the cached optimal arraysize for a Redshift backend.

        This retrieves the arraysize that was determined and cached during
        connection patching. All Redshift connections go through
        patch_redshift_connection() which sets this value.

        Args:
            backend: The Ibis backend connection object

        Returns:
            Optimal arraysize for the cluster type (default: 1000 if not set)
        """
        return getattr(backend, "_redshift_arraysize", 1000)

    @property
    def backend_name(self) -> str:
        return "redshift"
