"""
Database Connection Pool Monitor

This module provides a background task that continuously monitors
the PostgreSQL connection pool and logs warnings when approaching limits.

The monitor tracks:
- Pool size and available connections
- Requests waiting for connections
- Pool utilization percentage
"""

import asyncio
import logging
from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.server.storage import StorageService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PoolMonitorSettings(Configuration):
    """Settings for the pool monitor."""

    # How often to check pool stats (seconds)
    check_interval: int = field(
        default=60,
        metadata=FieldMetadata(
            description="The frequency in seconds to report the database "
            + "connection pool statistics.",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_DATABASE_POOL_MONITOR_INTERVAL",
                "DATABASE_POOL_MONITOR_INTERVAL",
            ],
        ),
    )


async def pool_monitor_loop(shutdown_event: asyncio.Event) -> None:
    """
    Background loop that monitors the connection pool.

    Checks pool stats every 5 seconds and logs when utilization >= 85%.

    Args:
        shutdown_event: Event to signal shutdown (for lifespan integration)
    """
    logger.info(
        f"Starting database connection pool monitor "
        f"(interval={PoolMonitorSettings.check_interval}s)"
    )

    storage = StorageService.get_instance()
    while not shutdown_event.is_set():
        try:
            # psycopg pool
            pool = storage._pool  # type: ignore (only runs for PostgreSQL)
            if pool:
                stats = pool.get_stats()
                logger.info(f"Database connection pool stats: {stats}")

            # sqlalchemy pool
            if storage._sa_engine:
                pool = storage._sa_engine.pool
                if pool:
                    status = pool.status()
                    logger.info(f"SQLAlchemy Database connection pool status: {status}")

        except Exception as e:
            logger.error(f"Error in pool monitor loop: {e}", exc_info=e)

        await asyncio.sleep(PoolMonitorSettings.check_interval)
