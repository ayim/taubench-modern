"""Base classes and registry for backend handlers."""

import asyncio
import functools
import typing
from abc import ABC, abstractmethod
from typing import Any

import structlog

if typing.TYPE_CHECKING:
    import pyarrow

logger = structlog.get_logger(__name__)


class BackendHandler(ABC):
    """Abstract base class for database backend handlers.

    Each backend handler encapsulates the logic for:
    - Executing queries with backend-specific optimizations
    - Converting results to PyArrow format
    """

    @abstractmethod
    async def execute_query(self, ibis_expr: Any) -> "pyarrow.Table":
        """Execute an ibis expression and return results as PyArrow table.

        Args:
            ibis_expr: An ibis expression to execute

        Returns:
            A pyarrow.Table containing the query results

        Raises:
            Exception: If query execution fails
        """

    async def execute_count(self, count_expr: Any) -> int:
        """Execute a count expression and return the count as an integer.

        This method handles backend-specific differences in how count()
        is returned. Some backends return a table, others return a scalar.

        Args:
            count_expr: An ibis count expression (result of .count())

        Returns:
            The count as an integer

        Raises:
            Exception: If query execution fails
        """
        # Default implementation: execute as query and extract count from table
        table = await self.execute_query(count_expr)
        return table.to_pylist()[0][table.column_names[0]]

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the name of this backend for logging/debugging."""


class DefaultBackendHandler(BackendHandler):
    """Default handler for standard databases (SQLite, PostgreSQL, etc.).

    Uses ibis's standard to_pyarrow() method which works for most databases.
    """

    async def execute_query(self, ibis_expr: Any) -> "pyarrow.Table":
        """Execute query using standard ibis to_pyarrow() in a thread pool.

        This works for databases that don't require special handling:
        - SQLite (read operations don't create new connections)
        - PostgreSQL (standard Arrow conversion works)
        - Most other SQL databases
        """
        return await asyncio.to_thread(ibis_expr.to_pyarrow)

    async def execute_count(self, count_expr: Any) -> int:
        """Execute a count expression and return the count as an integer.

        For most databases, count() returns a scalar that can be directly
        converted to a Python int via Arrow.
        """
        arrow_result = await asyncio.to_thread(count_expr.to_pyarrow)
        return arrow_result.as_py()

    @property
    def backend_name(self) -> str:
        return "default"


def _get_backend_from_expr(ibis_expr: Any) -> Any:
    """Extract the backend from an ibis expression.

    Args:
        ibis_expr: An ibis expression or result object

    Returns:
        The backend object

    Raises:
        ValueError: If no backend is found in the ibis expression
        ValueError: If the backend cannot be extracted from the ibis expression
    """
    try:
        if hasattr(ibis_expr, "_find_backend"):
            return ibis_expr._find_backend()
        elif hasattr(ibis_expr, "get_backend"):
            return ibis_expr.get_backend()
        raise ValueError("No backend found in ibis expression")
    except Exception as e:
        logger.warning("Failed to get backend from ibis expression", error=str(e))
        raise ValueError("Failed to get backend from ibis expression") from e


def _get_engine_name(ibis_expr: Any) -> str:
    """Get the engine name from an ibis expression.

    Args:
        ibis_expr: An ibis expression or result object

    Returns:
        The engine name from database backend or "default" if not found

    """
    backend = _get_backend_from_expr(ibis_expr)

    # Check for our custom __s4engine__ attribute
    if hasattr(backend, "__s4engine__"):
        return backend.__s4engine__

    return "default"


@functools.cache
def _get_backend_registry() -> dict[str, BackendHandler]:
    """Get the global backend handler registry.

    The registry is lazily initialized with handlers on first access.
    Handlers are stored by engine name for fast lookup.

    Returns:
        A dict mapping engine names to BackendHandler instances
    """
    # Import handlers here to avoid circular imports
    from agent_platform.server.semantic_data_models.handlers.redshift import (
        RedshiftBackendHandler,
    )
    from agent_platform.server.semantic_data_models.handlers.snowflake import (
        SnowflakeBackendHandler,
    )

    registry = {
        "snowflake": SnowflakeBackendHandler(),
        "redshift": RedshiftBackendHandler(),
        "default": DefaultBackendHandler(),
    }

    logger.debug(f"Initialized backend handler registry with {len(registry)} handlers")
    return registry


def _get_handler(ibis_expr: Any) -> BackendHandler:
    """Get the appropriate handler for an ibis expression.

    Args:
        ibis_expr: An ibis expression or result object

    Returns:
        The handler for the expression's backend, or default handler
        if not found
    """
    registry = _get_backend_registry()
    engine_name = _get_engine_name(ibis_expr)

    handler = registry.get(engine_name, registry["default"])
    logger.debug(f"Using backend handler: {handler.backend_name} for engine: {engine_name}")
    return handler


async def execute_query_with_backend_handler(
    ibis_expr: Any,
) -> "pyarrow.Table":
    """Execute an ibis query using the appropriate backend handler.

    This is the main entry point for executing queries with
    backend-specific logic.

    Args:
        ibis_expr: An ibis expression to execute

    Returns:
        A pyarrow.Table containing the query results
    """
    handler = _get_handler(ibis_expr)
    return await handler.execute_query(ibis_expr)


async def execute_count_with_backend_handler(count_expr: Any) -> int:
    """Execute a count expression using the appropriate backend handler.

    This handles backend-specific differences in how count() results
    are returned.

    Args:
        count_expr: An ibis count expression (result of .count())

    Returns:
        The count as an integer
    """
    handler = _get_handler(count_expr)
    return await handler.execute_count(count_expr)
