"""Backend-specific query execution handlers for semantic data models.

This package provides a pluggable architecture for handling database-specific
query execution logic. Each database backend can have its own handler that
implements special logic for executing queries and converting results to
PyArrow.

Usage:
    from agent_platform.server.semantic_data_models.handlers import (
        execute_query_with_backend_handler,
    )

    # Execute a query with automatic backend detection
    result = await execute_query_with_backend_handler(ibis_expr)
"""

from agent_platform.server.semantic_data_models.handlers.base import (
    BackendHandler,
    DefaultBackendHandler,
    execute_count_with_backend_handler,
    execute_query_with_backend_handler,
)
from agent_platform.server.semantic_data_models.handlers.redshift import (
    RedshiftBackendHandler,
)
from agent_platform.server.semantic_data_models.handlers.snowflake import (
    SnowflakeBackendHandler,
)

__all__ = [
    "BackendHandler",
    "DefaultBackendHandler",
    "RedshiftBackendHandler",
    "SnowflakeBackendHandler",
    "execute_count_with_backend_handler",
    "execute_query_with_backend_handler",
]
